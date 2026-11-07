"""Multi-organisation (multi-tenant) en base partagée.

Chaque modèle héritant de TenantMixin porte un organization_id. Une fois
l'organisation courante fixée (g.org_id, par requête), toutes les requêtes ORM
(SELECT, UPDATE et DELETE en masse, Session.get) sont automatiquement
restreintes à cette organisation, et les nouveaux objets y sont rattachés à
l'insertion. Les blueprints n'ont donc rien à filtrer eux-mêmes.

Hors contexte d'organisation (connexion, CLI), aucun filtre n'est appliqué.
Pour une requête volontairement transverse en contexte d'organisation :
    Model.query.execution_options(all_tenants=True)
"""
from contextlib import contextmanager
from urllib.parse import urlparse

from flask import g, has_app_context, session, abort, request, flash, redirect, url_for
from flask_login import current_user, logout_user
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.extensions import db
from app.models import Organization, TenantMixin

SESSION_KEY = "org_id"


def current_org_id():
    return g.get("org_id") if has_app_context() else None


def current_org():
    oid = current_org_id()
    if oid is None:
        return None
    org = g.get("org")
    if org is None or org.id != oid:
        org = db.session.get(Organization, oid)
        g.org = org
    return org


def set_current_org(org_id):
    g.org_id = org_id
    g.pop("org", None)


@contextmanager
def tenant_scope(org_id):
    """Exécute un bloc dans le contexte d'une organisation (CLI, callbacks)."""
    prev = g.get("org_id")
    set_current_org(org_id)
    try:
        yield
    finally:
        set_current_org(prev)


def switch_org(org_id):
    """Super-admin : change l'organisation de travail (mémorisée en session)."""
    session[SESSION_KEY] = org_id


def _resolve_request_org():
    """before_request : organisation de l'utilisateur connecté, ou celle choisie
    par un super-admin. Déconnecte si l'organisation est désactivée."""
    set_current_org(None)
    if not current_user.is_authenticated:
        return
    oid = current_user.organization_id
    if current_user.is_superadmin and session.get(SESSION_KEY):
        oid = session[SESSION_KEY]
    org = db.session.get(Organization, oid)
    if org is None or (not org.is_active and not current_user.is_superadmin):
        logout_user()
        session.pop(SESSION_KEY, None)
        abort(403)
    set_current_org(org.id)
    g.org = org


def _filter_by_tenant(state):
    oid = current_org_id()
    if oid is None or state.execution_options.get("all_tenants"):
        return
    # Les chargements de relations sont filtrés aussi : une clé étrangère vers
    # une autre organisation (formulaire forgé) se résout en None.
    if (state.is_select and not state.is_column_load) or state.is_update or state.is_delete:
        state.statement = state.statement.options(
            with_loader_criteria(TenantMixin, lambda cls: cls.organization_id == oid,
                                 include_aliases=True))


def _stamp_new_objects(sess, flush_context, instances):
    for obj in sess.new:
        if isinstance(obj, TenantMixin) and obj.organization_id is None:
            oid = current_org_id()
            if oid is None:
                raise RuntimeError(f"{obj!r} créé hors contexte d'organisation.")
            obj.organization_id = oid


def _block_readonly_writes():
    """Compte en lecture seule : toute requête de modification est refusée."""
    if request.method in ("GET", "HEAD", "OPTIONS") or not current_user.is_authenticated:
        return None
    if not current_user.is_readonly:
        return None
    if request.endpoint in ("auth.login", "auth.logout"):
        return None
    flash("Compte de démonstration en lecture seule : aucune modification n'est possible.", "warning")
    back = request.referrer
    if not back or urlparse(back).netloc != request.host:
        back = url_for("dashboard.home")
    return redirect(back, code=303)


def init_app(app):
    event.listen(Session, "do_orm_execute", _filter_by_tenant)
    event.listen(Session, "before_flush", _stamp_new_objects)
    app.before_request(_resolve_request_org)
    app.before_request(_block_readonly_writes)

    @app.context_processor
    def _inject_org():
        org = current_org()
        orgs = []
        if org is not None and current_user.is_authenticated and current_user.is_superadmin:
            orgs = Organization.query.order_by(Organization.name).all()
        return {"current_org": org, "all_orgs": orgs}
