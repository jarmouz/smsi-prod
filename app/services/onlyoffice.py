"""Intégration OnlyOffice Document Server pour l'édition en ligne des fichiers
du module Docs (stockés dans Nextcloud via WebDAV).

Le SMSI est l'« application hôte » : il fournit le fichier au Document Server,
génère la configuration signée (JWT) de l'éditeur, et reçoit le callback de
sauvegarde pour réécrire le fichier dans Nextcloud."""
import hashlib

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.services import webdav

# Extension -> type de document OnlyOffice
_WORD = {"doc", "docx", "odt", "rtf", "txt", "dotx", "fodt"}
_CELL = {"xls", "xlsx", "ods", "csv", "fods"}
_SLIDE = {"ppt", "pptx", "odp", "fodp"}


def enabled():
    c = current_app.config
    return bool(c.get("ONLYOFFICE_URL")) and webdav.enabled()


def ext_of(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def doc_type(name):
    e = ext_of(name)
    if e in _WORD:
        return "word"
    if e in _CELL:
        return "cell"
    if e in _SLIDE:
        return "slide"
    return None


def is_editable(name):
    return doc_type(name) is not None


# --- Jetons d'accès pour le Document Server (non authentifié) --------------
def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="onlyoffice")


def make_token(rel, purpose):
    from app.services.tenancy import current_org_id
    return _serializer().dumps({"rel": rel, "p": purpose, "o": current_org_id()})


def read_token(token, purpose, max_age=86400):
    """Retourne (rel, organization_id) ou (None, None) si le jeton est invalide."""
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None, None
    if data.get("p") != purpose or not data.get("o"):
        return None, None
    return data.get("rel"), data.get("o")


# --- JWT OnlyOffice --------------------------------------------------------
def sign(payload):
    secret = current_app.config.get("ONLYOFFICE_JWT_SECRET")
    if not secret:
        return None
    import jwt
    return jwt.encode(payload, secret, algorithm="HS256")


def verify(token):
    secret = current_app.config.get("ONLYOFFICE_JWT_SECRET")
    if not secret:
        return {}
    import jwt
    return jwt.decode(token, secret, algorithms=["HS256"])


def _base_url():
    c = current_app.config
    base = c.get("ONLYOFFICE_CALLBACK_BASE") or c.get("APP_BASE_URL") or ""
    return base.rstrip("/")


def document_key(rel):
    """Clé de version : change quand le fichier change (basée sur date de modif)."""
    from app.services.tenancy import current_org_id
    org_rel = f"{current_org_id()}:{rel}"
    try:
        st = webdav.stat(rel)
        seed = f"{org_rel}|{st.get('mtime') or ''}|{st.get('size') or ''}"
    except Exception:  # noqa: BLE001
        seed = org_rel
    return hashlib.md5(seed.encode()).hexdigest()[:24]


def build_config(rel, user, can_edit):
    """Configuration de l'éditeur OnlyOffice pour un fichier donné."""
    name = rel.split("/")[-1]
    base = _base_url()
    cfg = {
        "document": {
            "fileType": ext_of(name),
            "key": document_key(rel),
            "title": name,
            "url": f"{base}/office/fichier/{make_token(rel, 'dl')}",
            "permissions": {"edit": bool(can_edit), "download": True},
        },
        "documentType": doc_type(name),
        "editorConfig": {
            "mode": "edit" if can_edit else "view",
            "lang": "fr",
            "callbackUrl": f"{base}/office/callback/{make_token(rel, 'cb')}",
            "user": {"id": str(getattr(user, "id", "0")), "name": getattr(user, "name", "Utilisateur")},
            "customization": {"forcesave": True, "autosave": True, "chat": False},
        },
        "type": "desktop",
        "width": "100%",
        "height": "100%",
    }
    tok = sign(cfg)
    if tok:
        cfg["token"] = tok
    return cfg


# --- Conversion (ex. docx -> pdf) via le Document Server ----------------------
def _tmp_dir():
    import os
    d = os.path.join(current_app.config.get("UPLOAD_DIR") or "/tmp", ".convert")
    os.makedirs(d, exist_ok=True)
    return d


def read_temp(token):
    """Fichier temporaire servi au Document Server (jeton signé, 5 min, usage unique)."""
    import os
    try:
        key = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="oo-convert").loads(token, max_age=300)
    except (BadSignature, SignatureExpired):
        return None
    path = os.path.join(_tmp_dir(), os.path.basename(key))
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


def convert(data, filetype, outputtype="pdf"):
    """Convertit un fichier via OnlyOffice. Retourne les octets convertis, ou lève RuntimeError."""
    import os
    import uuid
    import requests
    if not current_app.config.get("ONLYOFFICE_URL"):
        raise RuntimeError("OnlyOffice n'est pas configuré.")
    key = uuid.uuid4().hex
    with open(os.path.join(_tmp_dir(), key), "wb") as f:
        f.write(data)
    token = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="oo-convert").dumps(key)
    payload = {"async": False, "filetype": filetype, "outputtype": outputtype, "key": key,
               "title": f"export.{filetype}", "url": f"{_base_url()}/office/temp/{token}"}
    tok = sign(payload)
    if tok:
        payload["token"] = tok
    try:
        r = requests.post(current_app.config["ONLYOFFICE_URL"].rstrip("/") + "/ConvertService.ashx",
                          json=payload, headers={"Accept": "application/json"}, timeout=90)
        res = r.json()
        if res.get("error") or not res.get("fileUrl"):
            raise RuntimeError(f"conversion refusée (code {res.get('error')})")
        out = requests.get(res["fileUrl"], timeout=90)
        out.raise_for_status()
        return out.content
    finally:
        path = os.path.join(_tmp_dir(), key)
        if os.path.exists(path):
            os.remove(path)
