import time

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User
from app.services import totp
from app.services.audit_trail import log_event

bp = Blueprint("auth", __name__)

MFA_PENDING = "mfa_pending"      # {uid, remember, next, at} entre les deux étapes
MFA_MAX_AGE = 300                # secondes pour saisir le code


def _safe_next(nxt):
    # n'accepter que des redirections internes
    return nxt if nxt and nxt.startswith("/") and not nxt.startswith("//") else None


def _complete_login(user, remember, nxt, how):
    user.reset_failures()
    db.session.commit()
    session.pop(MFA_PENDING, None)
    login_user(user, remember=remember)
    log_event("login", f"Connexion réussie ({how})", user=user)
    return redirect(_safe_next(nxt) or url_for("dashboard.home"))


def _fail(user, reason):
    user.register_failure(current_app.config["LOGIN_MAX_ATTEMPTS"],
                          current_app.config["LOGIN_LOCKOUT_MINUTES"])
    db.session.commit()
    log_event("login_failed", reason + (" - compte verrouillé" if user.is_locked else ""), user=user)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()

        # Compte verrouillé (anti-force-brute)
        if user and user.is_locked:
            flash("Trop de tentatives. Compte temporairement verrouillé, réessayez plus tard.", "danger")
            return render_template("auth/login.html")

        if user and user.is_active_flag and user.check_password(password):
            if not (user.organization.is_active or user.is_superadmin):
                flash("Votre organisation est désactivée. Contactez l'administrateur de la plateforme.", "danger")
                return render_template("auth/login.html")
            remember = bool(request.form.get("remember"))
            if user.mfa_enabled:
                session[MFA_PENDING] = {"uid": user.id, "remember": remember,
                                        "next": request.args.get("next"), "at": int(time.time())}
                return redirect(url_for("auth.mfa"))
            return _complete_login(user, remember, request.args.get("next"), "mot de passe")

        # Échec : incrémenter le compteur si le compte existe
        if user:
            _fail(user, "Mot de passe incorrect")
        flash("Identifiants incorrects.", "danger")

    return render_template("auth/login.html")


@bp.route("/login/verification", methods=["GET", "POST"])
def mfa():
    """Deuxième étape : code de l'application d'authentification ou code de secours."""
    pending = session.get(MFA_PENDING)
    user = db.session.get(User, pending["uid"]) if pending else None
    if not user or int(time.time()) - pending.get("at", 0) > MFA_MAX_AGE:
        session.pop(MFA_PENDING, None)
        flash("Session de connexion expirée : saisissez à nouveau vos identifiants.", "warning")
        return redirect(url_for("auth.login"))
    if user.is_locked:
        session.pop(MFA_PENDING, None)
        flash("Trop de tentatives. Compte temporairement verrouillé, réessayez plus tard.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        step = totp.verify(user.totp_secret, code, user.totp_last_step)
        if step is not None:
            user.totp_last_step = step
            return _complete_login(user, pending["remember"], pending["next"], "mot de passe + code TOTP")
        remaining = totp.use_recovery_code(user.recovery_codes, code)
        if remaining is not None:
            user.recovery_codes = remaining
            left = totp.remaining(remaining)
            resp = _complete_login(user, pending["remember"], pending["next"], "mot de passe + code de secours")
            flash(f"Code de secours utilisé. Il vous en reste {left} : pensez à les régénérer dans « Mon compte ».",
                  "warning")
            return resp
        _fail(user, "Code de double authentification invalide")
        flash("Code invalide.", "danger")
    return render_template("auth/login.html", mfa_step=True)


@bp.route("/logout")
@login_required
def logout():
    from app.services.tenancy import SESSION_KEY
    log_event("logout", "Déconnexion")
    logout_user()
    session.pop(SESSION_KEY, None)
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for("auth.login"))
