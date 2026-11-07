from flask import Blueprint, request, redirect, url_for, flash, abort, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Attachment
from app.services import attachments as svc
from app.services.access import editor_required

bp = Blueprint("attachments", __name__, url_prefix="/pieces-jointes")

# Où revenir après upload/suppression, selon le type d'objet
def _back(entity_type, entity_id):
    return {
        "audit": lambda: url_for("audits.detail", audit_id=entity_id),
        "finding": lambda: url_for("audits.detail", audit_id=request.form.get("audit_id", type=int) or entity_id),
        "review": lambda: url_for("reviews.detail", review_id=entity_id),
        "document": lambda: url_for("documents.detail", doc_id=entity_id),
        "evidence": lambda: url_for("evidence.edit", ev_id=entity_id),
        "supplier": lambda: url_for("suppliers.detail", sup_id=entity_id),
        "competence": lambda: url_for("competences.edit_record", rec_id=entity_id),
        "continuity": lambda: url_for("continuity.test_detail", test_id=entity_id),
        "change": lambda: url_for("changes.detail", change_id=entity_id),
    }.get(entity_type, lambda: url_for("dashboard.home"))()


@bp.route("/<entity_type>/<int:entity_id>", methods=["POST"])
@editor_required
def upload(entity_type, entity_id):
    att, msg = svc.save_upload(request.files.get("file"), entity_type, entity_id, current_user)
    flash(msg, "success" if att else "danger")
    return redirect(request.form.get("next") or _back(entity_type, entity_id))


@bp.route("/<int:att_id>/telecharger")
@login_required
def download(att_id):
    att = db.session.get(Attachment, att_id) or abort(404)
    import io
    try:
        data = svc.read_bytes(att)
    except Exception:  # noqa: BLE001
        abort(404)
    return send_file(io.BytesIO(data), as_attachment=True, download_name=att.filename,
                     mimetype=att.content_type or "application/octet-stream")


@bp.route("/<int:att_id>/supprimer", methods=["POST"])
@editor_required
def delete(att_id):
    att = db.session.get(Attachment, att_id) or abort(404)
    back = _back(att.entity_type, att.entity_id)
    svc.delete_attachment(att)
    flash("Pièce jointe supprimée.", "success")
    return redirect(request.form.get("next") or back)
