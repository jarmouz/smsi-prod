from datetime import datetime, date

from flask import Flask, redirect, url_for
from flask_login import current_user

from app.config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Derrière un reverse proxy (kit sur site : Caddy) : schéma et IP réels
    import os
    if os.environ.get("TRUST_PROXY") == "1":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    _register_login(app)
    from app.services import tenancy, audit_trail, risk_criteria, charts
    tenancy.init_app(app)
    audit_trail.init_app(app)
    risk_criteria.init_app(app)
    charts.init_app(app)
    _register_blueprints(app)
    from app.blueprints.account import enforce as _enforce_account
    app.before_request(_enforce_account)
    _register_jinja(app)
    _register_cli(app)

    from app.blueprints.onlyoffice import bp as _oo_bp
    csrf.exempt(_oo_bp)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.route("/healthz")
    def healthz():
        """Sonde de supervision (sans authentification) : application et base joignables."""
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception:  # noqa: BLE001
            db.session.rollback()
            return {"status": "db-unavailable"}, 503

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.home"))
        return redirect(url_for("auth.login"))

    return app


def _register_login(app):
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        # Cookie d'un autre format (ex. « id:jeton » posé par la version 1.0.x) : nouvelle connexion
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None


def _register_blueprints(app):
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.dashboard import bp as dash_bp
    from app.blueprints.soa import bp as soa_bp
    from app.blueprints.risks import bp as risks_bp
    from app.blueprints.audits import bp as audits_bp
    from app.blueprints.reviews import bp as reviews_bp
    from app.blueprints.documents import bp as documents_bp
    from app.blueprints.evidence import bp as evidence_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.attachments import bp as attachments_bp
    from app.blueprints.docs import bp as docs_bp
    from app.blueprints.onlyoffice import bp as onlyoffice_bp
    from app.blueprints.assets import bp as assets_bp
    from app.blueprints.incidents import bp as incidents_bp
    from app.blueprints.awareness import bp as awareness_bp
    from app.blueprints.platform import bp as platform_bp
    from app.blueprints.account import bp as account_bp
    from app.blueprints.context import bp as context_bp
    from app.blueprints.objectives import bp as objectives_bp
    from app.blueprints.nonconformities import bp as nonconformities_bp
    from app.blueprints.suppliers import bp as suppliers_bp
    from app.blueprints.requirements import bp as requirements_bp
    from app.blueprints.competences import bp as competences_bp
    from app.blueprints.continuity import bp as continuity_bp
    from app.blueprints.changes import bp as changes_bp
    from app.blueprints.imports import bp as imports_bp

    for b in (auth_bp, dash_bp, soa_bp, risks_bp, audits_bp,
              reviews_bp, documents_bp, evidence_bp, admin_bp, attachments_bp, docs_bp, onlyoffice_bp,
              assets_bp, incidents_bp, awareness_bp, platform_bp, account_bp, context_bp, objectives_bp,
              nonconformities_bp, suppliers_bp, requirements_bp, competences_bp, continuity_bp, changes_bp, imports_bp):
        app.register_blueprint(b)


def _register_jinja(app):
    from app.models import (Theme, ControlStatus, RiskStatus, Treatment,
                            FindingType, ActionStatus, DocStatus, DocType, AuditStatus)

    @app.template_filter("dt")
    def _dt(value, fmt="%d/%m/%Y %H:%M"):
        return value.strftime(fmt) if value else "-"

    @app.template_filter("d")
    def _d(value, fmt="%d/%m/%Y"):
        return value.strftime(fmt) if value else "-"

    from app.services import webdav
    from app.services import onlyoffice as oo

    @app.context_processor
    def _inject():
        try:
            docs_on = webdav.enabled()
            oo_on = oo.enabled()
        except Exception:
            docs_on = False
            oo_on = False
        return {
            "docs_enabled": docs_on,
            "oo_enabled": oo_on,
            "oo_editable": oo.is_editable,
            "APP_NAME": app.config["APP_NAME"],
            "Theme": Theme, "ControlStatus": ControlStatus, "RiskStatus": RiskStatus,
            "Treatment": Treatment, "FindingType": FindingType, "ActionStatus": ActionStatus,
            "DocStatus": DocStatus, "DocType": DocType, "AuditStatus": AuditStatus,
            "today": date.today(),
        }


def _register_cli(app):
    from app.seed import register_seed_command
    register_seed_command(app)
