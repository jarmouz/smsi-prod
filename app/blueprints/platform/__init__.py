"""Administration de la plateforme (super-admin) : organisations clientes,
bascule d'une organisation à l'autre, paramètres SMTP globaux."""
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app.extensions import db
from app.models import Organization, User, Risk, Control
from app.services import settings as settings_svc
from app.services.organizations import create_organization
from app.services.tenancy import switch_org

bp = Blueprint("platform", __name__, url_prefix="/plateforme")

SMTP_KEYS = ["smtp_host", "smtp_port", "smtp_username", "smtp_from_address", "smtp_from_name"]


def superadmin_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            abort(403)
        return fn(*a, **k)
    return w


def _counts(model, *filters):
    rows = (db.session.query(model.organization_id, db.func.count(model.id))
            .execution_options(all_tenants=True).filter(*filters)
            .group_by(model.organization_id).all())
    return dict(rows)


def _ai_key():
    from app.services import ai
    return ai.masked_key()


def platform_view_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not current_user.is_authenticated or not current_user.can_view_platform:
            abort(403)
        return fn(*a, **k)
    return w


@bp.route("/")
@platform_view_required
def home():
    if current_user.is_superadmin:
        orgs = Organization.query.order_by(Organization.name).all()
    else:
        # administrateur en lecture seule : sa seule organisation, sans paramètres plateforme
        orgs = [db.session.get(Organization, current_user.organization_id)]
        return render_template("platform/home.html", orgs=orgs, users=_counts(User), risks=_counts(Risk, Risk.nature.is_(None)),
                               controls=_counts(Control), smtp=None, demo=None, demo_content=None,
                               readonly=True)
    smtp = {k: settings_svc._row(k, None) for k in SMTP_KEYS + ["smtp_use_tls", "smtp_use_ssl"]}
    smtp = {k: (s.value if s else "") for k, s in smtp.items()}
    from app import demo_content
    from app.services import demo
    return render_template("platform/home.html", orgs=orgs, demo=demo.demo_org(), demo_content=demo_content,
                           users=_counts(User), risks=_counts(Risk, Risk.nature.is_(None)), controls=_counts(Control),
                           smtp=smtp, readonly=False, ai_key=_ai_key())


@bp.route("/organisations", methods=["POST"])
@superadmin_required
def create():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("admin_email") or "").strip().lower()
    if not name:
        flash("Le nom de l'organisation est obligatoire.", "danger")
        return redirect(url_for("platform.home"))
    if email and User.query.execution_options(all_tenants=True).filter_by(email=email).first():
        flash("Cet e-mail est déjà utilisé.", "danger")
        return redirect(url_for("platform.home"))
    org, user = create_organization(
        name, slug=request.form.get("slug") or None,
        docs_folder=request.form.get("docs_folder") or None,
        admin_email=email or None, admin_name=request.form.get("admin_name"),
        admin_password=request.form.get("admin_password") or None)
    flash(f"Organisation {org.name} créée" + (f", RSSI : {user.email}, mot de passe temporaire : {user.temp_password} "
                                             "(à changer à la première connexion)." if user else "."), "success")
    return redirect(url_for("platform.home"))


@bp.route("/organisations/<int:org_id>/modifier", methods=["POST"])
@superadmin_required
def update(org_id):
    org = db.session.get(Organization, org_id) or abort(404)
    org.name = (request.form.get("name") or org.name).strip()
    org.docs_folder = (request.form.get("docs_folder") or "").strip("/ ") or None
    db.session.commit()
    flash(f"{org.name} mise à jour.", "success")
    return redirect(url_for("platform.home"))


@bp.route("/organisations/<int:org_id>/etat", methods=["POST"])
@superadmin_required
def toggle(org_id):
    org = db.session.get(Organization, org_id) or abort(404)
    if org.id == current_user.organization_id:
        flash("Impossible de désactiver votre propre organisation.", "warning")
    else:
        org.is_active = not org.is_active
        db.session.commit()
        flash(f"{org.name} : {'activée' if org.is_active else 'désactivée'}.", "success")
    return redirect(url_for("platform.home"))


@bp.route("/organisations/<int:org_id>/acceder", methods=["POST"])
@superadmin_required
def enter(org_id):
    org = db.session.get(Organization, org_id) or abort(404)
    switch_org(org.id)
    flash(f"Vous travaillez maintenant dans « {org.name} ».", "success")
    return redirect(url_for("dashboard.home"))


@bp.route("/basculer", methods=["POST"])
@superadmin_required
def switch():
    """Sélecteur d'organisation de la barre latérale."""
    return enter(request.form.get("org_id", type=int) or 0)


@bp.route("/demo", methods=["POST"])
@superadmin_required
def load_demo():
    """Crée ou réinitialise l'organisation de démonstration."""
    from app.services import demo
    try:
        org = demo.load(lambda msg: None)
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("platform.home"))
    flash(f"Organisation de démo « {org.name} » prête (données réinitialisées).", "success")
    return redirect(url_for("platform.home"))


@bp.route("/smtp", methods=["POST"])
@superadmin_required
def save_smtp():
    data = {k: (request.form.get(k) or "").strip() for k in SMTP_KEYS}
    data["smtp_use_tls"] = "1" if request.form.get("smtp_use_tls") else "0"
    data["smtp_use_ssl"] = "1" if request.form.get("smtp_use_ssl") else "0"
    if request.form.get("smtp_password"):
        data["smtp_password"] = request.form["smtp_password"]
    settings_svc.set_many(data, scope=settings_svc.GLOBAL)
    flash("SMTP de la plateforme enregistré.", "success")
    return redirect(url_for("platform.home"))


@bp.route("/ia", methods=["POST"])
@superadmin_required
def save_ai():
    from app.services import ai
    action = request.form.get("action")
    if action == "remove":
        settings_svc.set_many({ai.KEY: ""}, scope=settings_svc.GLOBAL)
        flash("Clé d'API supprimée : l'assistance IA est désactivée pour toutes les organisations.", "success")
    else:
        key = (request.form.get("ai_api_key") or "").strip()
        if not key:
            ok, msg = (ai.check_key(ai.api_key()) if ai.platform_configured() else (False, "Aucune clé enregistrée."))
            flash(msg, "success" if ok else "danger")
        else:
            ok, msg = ai.check_key(key)
            if ok:
                settings_svc.set_many({ai.KEY: key}, scope=settings_svc.GLOBAL)
                flash("Clé d'API enregistrée. " + msg + " Chaque organisation doit encore activer l'assistance.", "success")
            else:
                flash("Clé non enregistrée : " + msg, "danger")
    return redirect(url_for("platform.home"))


@bp.route("/referentiels")
@platform_view_required
def frameworks():
    """Catalogues des référentiels de la plateforme et organisations qui les utilisent."""
    from sqlalchemy import func
    from app.models import Framework, FrameworkItem, OrgFramework, ItemMapping
    counts = dict(db.session.query(FrameworkItem.framework_id, func.count()).group_by(FrameworkItem.framework_id).all())
    users = dict(db.session.query(OrgFramework.framework_id, func.count())
                 .execution_options(all_tenants=True).filter(OrgFramework.enabled.is_(True))
                 .group_by(OrgFramework.framework_id).all())
    fws = Framework.query.order_by(Framework.sort_order, Framework.id).all()
    from app.services.catalogue_data import COMMON
    return render_template("platform/frameworks.html", fws=fws, counts=counts, users=users,
                           mappings=ItemMapping.query.count(),
                           with_clauses={f.code for f in fws if f.kind == "controls"
                                         and any(i.kind == "clause" for i in f.items)},
                           common={k: (len(v), sum(r == "commune" for _, r in v.values())) for k, v in COMMON.items()})
