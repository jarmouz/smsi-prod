from flask import current_app

from app.extensions import db
from app.models import Setting
from app.services.tenancy import current_org_id

GLOBAL = "global"


def _row(key, org_id):
    return Setting.query.filter(Setting.key == key, Setting.organization_id.is_(None) if org_id is None
                                else Setting.organization_id == org_id).first()


def get(key, default=None, inherit=True):
    """Valeur pour l'organisation courante ; si elle est vide (et inherit) la
    valeur globale de la plateforme ; sinon default."""
    oid = current_org_id()
    s = _row(key, oid) if oid is not None else None
    if (s is None or s.value in (None, "")) and inherit:
        s = _row(key, None) or s
    return s.value if s and s.value is not None else default


def get_bool(key, default=False):
    val = get(key)
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "on", "yes")


def get_int(key, default=0):
    try:
        return int(get(key, default))
    except (TypeError, ValueError):
        return default


def set_many(mapping, scope=None):
    """Enregistre pour l'organisation courante, ou globalement si scope=GLOBAL."""
    oid = None if scope == GLOBAL else current_org_id()
    if oid is None and scope != GLOBAL:
        raise RuntimeError("Aucune organisation courante.")
    for key, value in mapping.items():
        s = _row(key, oid)
        if s is None:
            s = Setting(key=key, organization_id=oid)
            db.session.add(s)
        s.value = "" if value is None else str(value)
    db.session.commit()


def get_smtp_config():
    """Retourne la config SMTP si l'hôte est renseigné, sinon None.
    Une organisation qui renseigne son propre serveur utilise toute sa propre
    configuration ; sinon c'est la configuration globale de la plateforme."""
    oid = current_org_id()
    own = oid is not None and bool(get("smtp_host", inherit=False))
    scope = oid if own else None

    def val(key, default=None):
        s = _row(key, scope)
        return s.value if s and s.value not in (None, "") else default

    def flag(key, default):
        v = val(key)
        return default if v is None else str(v).lower() in ("1", "true", "on", "yes")

    host = val("smtp_host")
    if not host:
        return None
    try:
        port = int(val("smtp_port", 587))
    except (TypeError, ValueError):
        port = 587
    return {
        "host": host,
        "port": port,
        "username": val("smtp_username", ""),
        "password": val("smtp_password", ""),
        "use_tls": flag("smtp_use_tls", True),
        "use_ssl": flag("smtp_use_ssl", False),
        "from_address": val("smtp_from_address", val("smtp_username", "")),
        "from_name": val("smtp_from_name", "Suivi des demandes"),
    }


def notifications_enabled():
    return get_bool("notifications_enabled", True) and get_smtp_config() is not None


def get_base_url():
    """URL publique pour les liens des e-mails (sans slash final)."""
    url = get("app_base_url") or current_app.config.get("APP_BASE_URL", "")
    return (url or "").rstrip("/")
