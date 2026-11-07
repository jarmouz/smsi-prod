"""Gestion des pièces jointes : métadonnées en base + stockage délégué
(disque local ou Nextcloud/WebDAV via app.services.storage)."""
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Attachment
from app.services import storage

ALLOWED_EXT = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods",
    "png", "jpg", "jpeg", "gif", "webp", "svg",
    "txt", "csv", "log", "md", "json", "xml", "rtf", "docm", "xlsm", "odp", "vsdx",
    "zip", "7z", "rar", "msg", "eml",
}

ENTITIES = {"audit", "finding", "review", "document", "evidence", "incident", "awareness", "supplier", "competence", "continuity", "change", "processing", "aisystem", "bcplan", "itservice"}


def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXT


def save_upload(file_storage, entity_type, entity_id, user):
    """Enregistre un fichier. Retourne (Attachment|None, message)."""
    if entity_type not in ENTITIES:
        return None, "Type d'objet invalide."
    if not file_storage or not file_storage.filename:
        return None, "Aucun fichier sélectionné."
    original = file_storage.filename
    if not allowed(original):
        return None, "Type de fichier non autorisé."

    return save_data(file_storage.read(), original, file_storage.mimetype, entity_type, entity_id, user)


def save_data(data, original, mimetype, entity_type, entity_id, user, commit=True):
    """Enregistre un contenu déjà lu (dépôt en masse). Retourne (Attachment|None, message)."""
    if entity_type not in ENTITIES:
        return None, "Type d'objet invalide."
    if not allowed(original):
        return None, "Type de fichier non autorisé."
    safe = secure_filename(original) or "fichier"
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    try:
        storage.save_bytes(data, stored)
    except Exception as e:  # noqa: BLE001
        current_app.logger.warning("Échec stockage pièce jointe : %s", e)
        return None, f"Stockage impossible : {e}"

    att = Attachment(
        entity_type=entity_type, entity_id=entity_id,
        filename=original[:300], stored_name=stored,
        content_type=mimetype, size=len(data),
        uploaded_by_id=(user.id if user else None),
    )
    db.session.add(att)
    if commit:
        db.session.commit()
    return att, "Pièce jointe ajoutée."


def save_many(file_list, entity_type, entity_id, user):
    n = 0
    for fs in (file_list or []):
        if fs and fs.filename and allowed(fs.filename):
            att, _ = save_upload(fs, entity_type, entity_id, user)
            if att:
                n += 1
    return n


def get_for(entity_type, entity_id):
    return (Attachment.query
            .filter_by(entity_type=entity_type, entity_id=entity_id)
            .order_by(Attachment.uploaded_at.desc()).all())


def counts_for(entity_type, ids):
    if not ids:
        return {}
    rows = (db.session.query(Attachment.entity_id, db.func.count(Attachment.id))
            .filter(Attachment.entity_type == entity_type,
                    Attachment.entity_id.in_(list(ids)))
            .group_by(Attachment.entity_id).all())
    return {eid: n for eid, n in rows}


def read_bytes(att):
    return storage.read_bytes(att.stored_name)


def delete_attachment(att):
    try:
        storage.delete(att.stored_name)
    except Exception as e:  # noqa: BLE001
        current_app.logger.warning("Suppression fichier stockage : %s", e)
    db.session.delete(att)
    db.session.commit()
