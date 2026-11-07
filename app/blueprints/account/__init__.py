"""Mon compte : mot de passe, double authentification (TOTP), codes de secours.
Contient aussi l'application des obligations (changement de mot de passe
initial, double authentification exigée par l'organisation)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.services import totp, settings as settings_svc
from app.services.audit_trail import log_event

bp = Blueprint("account", __name__, url_prefix="/compte")

SETUP_KEY = "mfa_setup_secret"
ISSUER = "SMSI Kaizen"


def mfa_required_for(user):
    return not user.is_readonly and settings_svc.get_bool("mfa_required", False)


def enforce():
    """before_request : mot de passe à changer, puis double authentification exigée."""
    if not current_user.is_authenticated or current_user.is_readonly:
        return None
    ep = request.endpoint or ""
    if ep.startswith("account.") or ep in ("auth.logout", "static"):
        return None
    if current_user.must_change_password:
        flash("Veuillez définir votre propre mot de passe avant de continuer.", "warning")
        return redirect(url_for("account.home"))
    if not current_user.mfa_enabled and mfa_required_for(current_user):
        flash("Votre organisation exige la double authentification : activez-la pour continuer.", "warning")
        return redirect(url_for("account.mfa_setup"))
    return None


@bp.route("/")
@login_required
def home():
    return render_template("account/home.html", recovery_left=totp.remaining(current_user.recovery_codes),
                           mfa_required=mfa_required_for(current_user))


@bp.route("/mot-de-passe", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current") or ""
    new = request.form.get("new") or ""
    if not current_user.check_password(current):
        flash("Mot de passe actuel incorrect.", "danger")
    elif new != (request.form.get("confirm") or ""):
        flash("La confirmation ne correspond pas au nouveau mot de passe.", "danger")
    elif new == current:
        flash("Le nouveau mot de passe doit être différent de l'actuel.", "danger")
    elif (problem := totp.password_problem(new, current_user.email)):
        flash(problem, "danger")
    else:
        current_user.set_password(new)
        current_user.must_change_password = False
        db.session.commit()
        log_event("password", "Mot de passe modifié par l'utilisateur", entity=current_user)
        flash("Mot de passe modifié.", "success")
        if not current_user.mfa_enabled and mfa_required_for(current_user):
            return redirect(url_for("account.mfa_setup"))
    return redirect(url_for("account.home"))


@bp.route("/double-authentification", methods=["GET"])
@login_required
def mfa_setup():
    if current_user.mfa_enabled:
        return redirect(url_for("account.home"))
    secret = session.get(SETUP_KEY) or totp.new_secret()
    session[SETUP_KEY] = secret
    return render_template("account/mfa_setup.html", secret=secret,
                           uri=totp.uri(secret, current_user.email, ISSUER))


@bp.route("/double-authentification/activer", methods=["POST"])
@login_required
def mfa_enable():
    secret = session.get(SETUP_KEY)
    step = totp.verify(secret, request.form.get("code")) if secret else None
    if step is None:
        flash("Code invalide : vérifiez l'heure de votre téléphone et saisissez le code affiché.", "danger")
        return redirect(url_for("account.mfa_setup"))
    codes, stored = totp.new_recovery_codes()
    current_user.totp_secret = secret
    current_user.totp_last_step = step
    current_user.recovery_codes = stored
    db.session.commit()
    session.pop(SETUP_KEY, None)
    log_event("mfa", "Double authentification activée", entity=current_user)
    return render_template("account/recovery_codes.html", codes=codes, first=True)


@bp.route("/double-authentification/codes", methods=["POST"])
@login_required
def mfa_codes():
    step = totp.verify(current_user.totp_secret, request.form.get("code"), current_user.totp_last_step)
    if step is None:
        flash("Code invalide.", "danger")
        return redirect(url_for("account.home"))
    codes, stored = totp.new_recovery_codes()
    current_user.totp_last_step = step
    current_user.recovery_codes = stored
    db.session.commit()
    log_event("mfa", "Codes de secours régénérés", entity=current_user)
    return render_template("account/recovery_codes.html", codes=codes, first=False)


@bp.route("/double-authentification/desactiver", methods=["POST"])
@login_required
def mfa_disable():
    if mfa_required_for(current_user):
        flash("Votre organisation exige la double authentification : elle ne peut pas être désactivée.", "warning")
        return redirect(url_for("account.home"))
    if not current_user.check_password(request.form.get("password") or "") or \
            totp.verify(current_user.totp_secret, request.form.get("code"), current_user.totp_last_step) is None:
        flash("Mot de passe ou code invalide.", "danger")
        return redirect(url_for("account.home"))
    current_user.totp_secret = current_user.totp_last_step = current_user.recovery_codes = None
    db.session.commit()
    log_event("mfa", "Double authentification désactivée par l'utilisateur", entity=current_user)
    flash("Double authentification désactivée.", "success")
    return redirect(url_for("account.home"))


@bp.route("/rappels", methods=["POST"])
@login_required
def digest_preference():
    from app.models import DigestFrequency
    try:
        current_user.digest_frequency = DigestFrequency(request.form.get("digest_frequency")).value
    except ValueError:
        abort(400)
    db.session.commit()
    flash("Préférence de récapitulatif enregistrée.", "success")
    return redirect(url_for("account.home"))
