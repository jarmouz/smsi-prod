from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    User, Risk, Audit, Finding, CorrectiveAction, ManagementReview,
    ReviewAction, Document, Evidence, Role,
)
from app.services.access import rssi_required
from app.services import settings as settings_svc
from app.services import mailer
from app.services import storage as storage_svc

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@rssi_required
def home():
    return render_template("admin/home.html",
                           nb_users=User.query.count(),
                           smtp_ok=settings_svc.get_smtp_config() is not None,
                           org_name=settings_svc.get("org_name", "Mon entreprise"))


# --- Utilisateurs --------------------------------------------------------
@bp.route("/utilisateurs")
@rssi_required
def users():
    people = User.query.order_by(User.name).all()
    return render_template("admin/users.html", people=people, Role=Role)


@bp.route("/utilisateurs/creer", methods=["POST"])
@rssi_required
def create_user():
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    if not email or not name:
        flash("Nom et e-mail obligatoires.", "danger")
    elif User.query.execution_options(all_tenants=True).filter_by(email=email).first():
        flash("Cet e-mail existe déjà.", "danger")
    else:
        try:
            role = Role(request.form.get("role"))
        except ValueError:
            role = Role.LECTEUR
        from app.services import totp
        pwd = request.form.get("password") or ""
        problem = totp.password_problem(pwd, email) if pwd else None
        if problem:
            flash(problem, "danger")
            return redirect(url_for("admin.users"))
        temp = pwd or totp.temporary_password()
        u = User(email=email, name=name, role=role,
                 job_title=(request.form.get("job_title") or "").strip() or None)
        u.set_password(temp)
        u.must_change_password = True
        db.session.add(u)
        db.session.commit()
        flash(f"Utilisateur {u.name} créé." + ("" if pwd else f" Mot de passe temporaire : {temp}") +
              " Il devra le changer à sa première connexion.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/utilisateurs/<int:user_id>/modifier", methods=["POST"])
@rssi_required
def update_user(user_id):
    u = db.session.get(User, user_id) or abort(404)
    u.name = (request.form.get("name") or u.name).strip()
    u.job_title = (request.form.get("job_title") or "").strip() or None
    try:
        u.role = Role(request.form.get("role"))
    except ValueError:
        pass
    pwd = request.form.get("password")
    msg = ""
    if pwd:
        from app.services import totp
        problem = totp.password_problem(pwd, u.email)
        if problem:
            flash(problem, "danger")
            return redirect(url_for("admin.users"))
        u.set_password(pwd)
        u.must_change_password = True
        msg = " Nouveau mot de passe à changer à la prochaine connexion."
    db.session.commit()
    flash(f"{u.name} mis à jour.{msg}", "success")
    return redirect(url_for("admin.users"))


@bp.route("/utilisateurs/<int:user_id>/reinitialiser-acces", methods=["POST"])
@rssi_required
def reset_access(user_id):
    """Mot de passe temporaire + suppression de la double authentification (perte du téléphone)."""
    from app.services import totp
    from app.services.audit_trail import log_event
    u = db.session.get(User, user_id) or abort(404)
    temp = totp.temporary_password()
    u.set_password(temp)
    u.must_change_password = True
    u.totp_secret = u.totp_last_step = u.recovery_codes = None
    u.reset_failures()
    db.session.commit()
    log_event("mfa", f"Accès réinitialisé par l'administrateur (mot de passe temporaire, double authentification à reconfigurer)",
              entity=u)
    flash(f"Accès de {u.name} réinitialisé. Mot de passe temporaire : {temp} (à transmettre par un canal sûr).", "success")
    return redirect(url_for("admin.users"))


@bp.route("/utilisateurs/<int:user_id>/etat", methods=["POST"])
@rssi_required
def toggle_user(user_id):
    u = db.session.get(User, user_id) or abort(404)
    if u.id == current_user.id:
        flash("Vous ne pouvez pas vous désactiver vous-même.", "warning")
    else:
        u.is_active_flag = not u.is_active_flag
        db.session.commit()
        flash(f"{u.name} : {'activé' if u.is_active_flag else 'désactivé'}.", "success")
    return redirect(url_for("admin.users"))


# --- Paramètres (SMTP + organisation) ------------------------------------
@bp.route("/parametres", methods=["GET"])
@rssi_required
def settings_page():
    keys = ["org_name", "smtp_host", "smtp_port", "smtp_username", "smtp_password",
            "smtp_from_address", "smtp_from_name", "app_base_url"]
    # valeurs propres à l'organisation ; vide = valeur globale de la plateforme
    v = {k: settings_svc.get(k, "", inherit=False) for k in keys}
    v["smtp_inherited"] = not v["smtp_host"] and settings_svc.get("smtp_host") is not None
    v["smtp_use_tls"] = settings_svc.get_bool("smtp_use_tls", True)
    v["smtp_use_ssl"] = settings_svc.get_bool("smtp_use_ssl", False)
    v["notifications_enabled"] = settings_svc.get_bool("notifications_enabled", True)
    v["mfa_required"] = settings_svc.get_bool("mfa_required", False)
    v["storage_backend"] = storage_svc.backend()
    v["nextcloud_url"] = settings_svc.get("app_base_url") and "" or ""  # placeholder
    from flask import current_app
    v["nc_url"] = current_app.config.get("NEXTCLOUD_URL", "")
    v["nc_user"] = current_app.config.get("NEXTCLOUD_USER", "")
    from app.services import webdav
    from app.services.tenancy import current_org
    v["nc_folder"] = storage_svc.attachments_folder(current_org())
    v["docs_root"] = webdav.docs_root(current_org())
    v["org_name"] = v["org_name"] or "Mon entreprise"
    return render_template("admin/settings.html", v=v)


@bp.route("/parametres", methods=["POST"])
@rssi_required
def save_settings():
    if request.form.get("mfa_required") and not settings_svc.get_bool("mfa_required", False) \
            and not current_user.mfa_enabled:
        flash("Activez d'abord votre propre double authentification (Mon compte) avant de l'imposer à l'organisation.",
              "danger")
        return redirect(url_for("admin.settings_page"))
    org_name = request.form.get("org_name", "").strip()
    if org_name:
        from app.services.tenancy import current_org
        current_org().name = org_name
    settings_svc.set_many({
        "org_name": org_name,
        "smtp_host": request.form.get("smtp_host", "").strip(),
        "smtp_port": request.form.get("smtp_port", "587").strip(),
        "smtp_username": request.form.get("smtp_username", "").strip(),
        "smtp_from_address": request.form.get("smtp_from_address", "").strip(),
        "smtp_from_name": request.form.get("smtp_from_name", "").strip(),
        "smtp_use_tls": "1" if request.form.get("smtp_use_tls") else "0",
        "smtp_use_ssl": "1" if request.form.get("smtp_use_ssl") else "0",
        "notifications_enabled": "1" if request.form.get("notifications_enabled") else "0",
        "mfa_required": "1" if request.form.get("mfa_required") else "0",
        "app_base_url": request.form.get("app_base_url", "").strip(),
    })
    pwd = request.form.get("smtp_password", "")
    if pwd:
        settings_svc.set_many({"smtp_password": pwd})
    flash("Paramètres enregistrés.", "success")
    return redirect(url_for("admin.settings_page"))


@bp.route("/parametres/test", methods=["POST"])
@rssi_required
def test_email():
    to = (request.form.get("test_to") or current_user.email).strip()
    html = ("<div style='font-family:sans-serif;padding:20px'>"
            "<h2>Test SMSI</h2><p>La configuration SMTP fonctionne.</p></div>")
    ok, msg = mailer.send_test(to, html)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("admin.settings_page"))


@bp.route("/parametres/test-nextcloud", methods=["POST"])
@rssi_required
def test_nextcloud():
    ok, msg = storage_svc.test_connection()
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("admin.settings_page"))


# --- Critères de risque (6.1.2) --------------------------------------------
@bp.route("/criteres-risque", methods=["GET", "POST"])
@rssi_required
def risk_criteria_page():
    from app.services import risk_criteria
    from app.services.audit_trail import log_event
    crit = risk_criteria.get()
    if request.method == "POST":
        top = risk_criteria.max_score()
        levels = {}
        for k in risk_criteria.LEVEL_KEYS:
            levels[k] = {"label": (request.form.get(f"label_{k}") or crit["levels"][k]["label"]).strip()[:30],
                         "min": 1 if k == "faible" else request.form.get(f"min_{k}", type=int) or 0}
        acceptance = request.form.get("acceptance", type=int) or 0
        error = risk_criteria.validate(levels, acceptance, top)
        if error:
            flash(error, "danger")
        else:
            new = {"scale": crit["scale"], "levels": levels, "acceptance": acceptance,
                   "likelihood": [(request.form.get(f"likelihood_{i}") or "").strip()[:200]
                                  for i in range(1, crit["scale"]["likelihood"] + 1)],
                   "impact": [(request.form.get(f"impact_{i}") or "").strip()[:200]
                              for i in range(1, crit["scale"]["impact"] + 1)]}
            risk_criteria.save(new)
            log_event("admin", "Critères d'appréciation et d'acceptation des risques modifiés",
                      changes={"criteres": [None, f"échelle {crit['scale']['likelihood']}×{crit['scale']['impact']}, "
                                                  f"seuils {[levels[k]['min'] for k in risk_criteria.LEVEL_KEYS]}, "
                                                  f"acceptation <= {acceptance}"]})
            flash("Critères de risque enregistrés.", "success")
            return redirect(url_for("admin.risk_criteria_page"))
    from app.models import Risk
    return render_template("admin/risk_criteria.html", crit=crit, keys=risk_criteria.LEVEL_KEYS,
                           top=risk_criteria.max_score(), sizes=range(risk_criteria.SCALE_MIN, risk_criteria.SCALE_MAX + 1),
                           nb_risks=Risk.query.count())


@bp.route("/criteres-risque/echelles", methods=["POST"])
@rssi_required
def risk_scale():
    from app.services import risk_criteria
    from app.services.audit_trail import log_event
    crit = risk_criteria.get()
    old_l, old_i = crit["scale"]["likelihood"], crit["scale"]["impact"]
    new_l = request.form.get("scale_likelihood", type=int) or old_l
    new_i = request.form.get("scale_impact", type=int) or old_i
    sizes = range(risk_criteria.SCALE_MIN, risk_criteria.SCALE_MAX + 1)
    if new_l not in sizes or new_i not in sizes:
        flash("Taille d'échelle invalide (3 à 6 niveaux).", "danger")
    elif (new_l, new_i) == (old_l, old_i):
        flash("Échelles inchangées.", "warning")
    else:
        n, error = risk_criteria.change_scale(new_l, new_i, bool(request.form.get("rescale")))
        if error:
            flash(error, "danger")
        else:
            log_event("admin", f"Échelles de risque passées de {old_l}×{old_i} à {new_l}×{new_i}"
                               f"{f' ({n} risque(s) recotés par conversion proportionnelle)' if n else ''}",
                      changes={"echelle": [f"{old_l}×{old_i}", f"{new_l}×{new_i}"]})
            flash(f"Échelles passées à {new_l}×{new_i}." + (f" {n} risque(s) recotés automatiquement : vérifiez-les "
                  "et faites ré-accepter les risques résiduels concernés." if n else "") +
                  " Seuils et descriptions réinitialisés : ajustez-les puis enregistrez.", "success")
    return redirect(url_for("admin.risk_criteria_page"))


# --- Rappels par e-mail ------------------------------------------------------
@bp.route("/rappels")
@rssi_required
def reminders_page():
    from app.services import reminders
    people = []
    for u in User.query.filter_by(is_active_flag=True, is_readonly=False).order_by(User.name):
        sections = reminders.collect(u)
        people.append((u, sections, sum(len(v) for _, v in sections)))
    return render_template("admin/reminders.html", people=people, enabled=settings_svc.notifications_enabled(),
                           smtp=settings_svc.get_smtp_config() is not None)


@bp.route("/rappels/test", methods=["POST"])
@rssi_required
def reminders_test():
    """Envoie immédiatement à l'administrateur son propre récapitulatif."""
    from app.services import reminders, mailer
    from app.services.tenancy import current_org
    sections = reminders.collect(current_user)
    if not sections:
        flash("Vous n'avez aucune échéance à signaler : rien à envoyer.", "warning")
    else:
        ok, msg = mailer.send_now(current_user.email, "SMSI - votre récapitulatif (test)",
                                  reminders.render(current_user, current_org(), sections, settings_svc.get_base_url()))
        flash(f"Récapitulatif envoyé à {current_user.email}." if ok else f"Échec de l'envoi : {msg}",
              "success" if ok else "danger")
    return redirect(url_for("admin.reminders_page"))


# --- Journal d'activité ----------------------------------------------------
def _journal_query():
    from datetime import datetime as _dt, timedelta
    from app.models import ActivityLog
    q = ActivityLog.query
    f = {k: (request.args.get(k) or "").strip() for k in ("type", "action", "user", "du", "au", "q")}
    if f["type"]:
        q = q.filter(ActivityLog.entity_type == f["type"])
    if f["action"]:
        q = q.filter(ActivityLog.action == f["action"])
    if f["user"]:
        q = q.filter(ActivityLog.user_name == f["user"])
    for key, op in (("du", "ge"), ("au", "lt")):
        try:
            d = _dt.strptime(f[key], "%Y-%m-%d")
            d = d + timedelta(days=1) if key == "au" else d
            q = q.filter(getattr(ActivityLog.created_at, f"__{op}__")(d))
        except ValueError:
            pass
    if f["q"]:
        like = f"%{f['q']}%"
        q = q.filter(db.or_(ActivityLog.entity_ref.ilike(like), ActivityLog.summary.ilike(like)))
    return q.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()), f


@bp.route("/journal")
@rssi_required
def journal():
    from app.models import ActivityLog
    q, f = _journal_query()
    page = max(request.args.get("page", 1, type=int), 1)
    per = 100
    total = q.count()
    logs = q.offset((page - 1) * per).limit(per).all()
    users = [u for (u,) in db.session.query(ActivityLog.user_name).distinct().order_by(ActivityLog.user_name) if u]
    types = [t for (t,) in db.session.query(ActivityLog.entity_type).distinct() if t]
    return render_template("admin/journal.html", logs=logs, f=f, page=page, pages=max((total - 1) // per + 1, 1),
                           total=total, users=users, types=sorted(types), actions=ActivityLog.ACTION_LABELS)


@bp.route("/journal/export.csv")
@rssi_required
def journal_export():
    import csv
    import io
    from flask import Response
    from app.services.audit_trail import ENTITY_LABELS, FIELD_LABELS, log_event
    q, _ = _journal_query()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Date (UTC)", "Utilisateur", "Action", "Type", "Objet", "Détail", "Adresse IP"])
    for l in q.limit(50000):
        detail = l.summary or "; ".join(f"{FIELD_LABELS.get(k, k)} : {v[0] or '-'} -> {v[1] or '-'}"
                                        for k, v in (l.changes or {}).items())
        w.writerow([l.created_at.strftime("%Y-%m-%d %H:%M:%S"), l.user_name or "", l.action_label,
                    ENTITY_LABELS.get(l.entity_type, l.entity_type or ""), l.entity_ref or "", detail, l.ip or ""])
    log_event("export", "Export du journal d'activité (CSV)")
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=journal_activite.csv"})


# --- Maintenance ---------------------------------------------------------
@bp.route("/maintenance")
@rssi_required
def maintenance():
    counts = {
        "risks": Risk.query.count(),
        "audits": Audit.query.count(),
        "reviews": ManagementReview.query.count(),
        "documents": Document.query.count(),
        "evidence": Evidence.query.count(),
    }
    return render_template("admin/maintenance.html", counts=counts, total=sum(counts.values()))


@bp.route("/maintenance/reinitialiser-donnees", methods=["POST"])
@rssi_required
def reset_operational():
    """Supprime les données opérationnelles (démo comprise). Conserve le
    catalogue Annexe A, les utilisateurs et les paramètres."""
    if (request.form.get("confirm") or "").strip().upper() != "REINITIALISER":
        flash("Saisissez REINITIALISER pour confirmer.", "warning")
        return redirect(url_for("admin.maintenance"))
    CorrectiveAction.query.delete()
    Finding.query.delete()
    Audit.query.delete()
    ReviewAction.query.delete()
    ManagementReview.query.delete()
    Document.query.delete()
    # dissocier les preuves de leurs mesures puis supprimer
    for e in Evidence.query.all():
        e.controls = []
    db.session.flush()
    Evidence.query.delete()
    for r in Risk.query.all():
        r.controls = []
    db.session.flush()
    Risk.query.delete()
    db.session.commit()
    from app.services.audit_trail import log_event
    log_event("admin", "Réinitialisation des données opérationnelles (maintenance)")
    flash("Données opérationnelles réinitialisées. Catalogue Annexe A et utilisateurs conservés.", "success")
    return redirect(url_for("admin.maintenance"))


# --- Assistance IA -----------------------------------------------------------
@bp.route("/ia", methods=["GET", "POST"])
@rssi_required
def ai_page():
    from datetime import datetime as _dt
    from app.services import ai
    from app.services.audit_trail import log_event
    if request.method == "POST":
        if request.form.get("action") == "enable":
            if not ai.platform_configured():
                flash("La plateforme n'a pas de clé d'API : contactez l'administrateur de la plateforme.", "danger")
            elif not request.form.get("consent"):
                flash("Cochez l'accord sur la transmission des données pour activer l'assistance.", "danger")
            else:
                settings_svc.set_many({ai.FLAG: "1", "ai_enabled_by": current_user.name,
                                       "ai_enabled_at": _dt.utcnow().strftime("%d/%m/%Y %H:%M")})
                log_event("parametres", "Assistance IA activée (accord sur la transmission des données à Anthropic)")
                flash("Assistance IA activée pour l'organisation.", "success")
        elif request.form.get("action") == "disable":
            settings_svc.set_many({ai.FLAG: "0"})
            log_event("parametres", "Assistance IA désactivée")
            flash("Assistance IA désactivée : plus aucune donnée n'est transmise.", "success")
        return redirect(url_for("admin.ai_page"))
    months = []
    now = _dt.utcnow()
    for i in range(3):
        y, m = divmod(now.year * 12 + now.month - 1 - i, 12)
        when = _dt(y, m + 1, 1)
        months.append((when, ai.usage(when)))
    return render_template("admin/ai.html", configured=ai.platform_configured(), enabled=ai.org_enabled(),
                           by=settings_svc.get("ai_enabled_by", "", inherit=False),
                           at=settings_svc.get("ai_enabled_at", "", inherit=False), months=months, model=ai.MODEL)


# --- Référentiels (normes activées par l'organisation) ------------------------
@bp.route("/referentiels", methods=["GET", "POST"])
@rssi_required
def frameworks_page():
    from datetime import date as _date
    from app.models import OrgFramework
    from app.services import frameworks as fw_svc
    from app.services.audit_trail import log_event

    def _d(v):
        try:
            return _date.fromisoformat(v) if v else None
        except ValueError:
            return None

    if request.method == "POST":
        code, action = request.form.get("code", ""), request.form.get("action")
        fw = fw_svc.get(code)
        if fw is None or not fw.available:
            abort(404)
        try:
            if action == "enable":
                fw_svc.enable(code)
                log_event("parametres", f"Référentiel activé : {fw.name}")
                flash(f"{fw.name} activée : son catalogue a été ajouté à l'organisation.", "success")
            elif action == "disable":
                fw_svc.disable(code)
                log_event("parametres", f"Référentiel désactivé : {fw.name} (données conservées)")
                flash(f"{fw.name} désactivée. Ses données sont conservées et réapparaîtront à la réactivation.", "success")
            elif action == "save":
                of = OrgFramework.query.filter_by(framework_id=fw.id).first() or abort(404)
                of.scope = (request.form.get("scope") or "").strip() or None
                of.certifier = (request.form.get("certifier") or "").strip()[:200] or None
                of.target_date = _d(request.form.get("target_date"))
                of.certified_on = _d(request.form.get("certified_on"))
                flash(f"{fw.name} : informations enregistrées.", "success")
            db.session.commit()
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
        return redirect(url_for("admin.frameworks_page"))

    rows = []
    states = {of.framework_id: of for of in OrgFramework.query.all()}
    for fw in fw_svc.all_frameworks():
        if not fw.available:
            continue
        of = states.get(fw.id)
        rows.append({"fw": fw, "of": of, "on": bool(of and of.enabled), "core": fw.code == fw_svc.CORE,
                     "n_items": len([i for i in fw.items if i.kind == "control"])})
    return render_template("admin/frameworks.html", rows=rows)
