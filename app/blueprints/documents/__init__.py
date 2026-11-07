from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Document, DocumentVersion, User, DocType, DocStatus
from app.services.access import editor_required, rssi_required
from app.services.audit_trail import log_event
from app.services.refs import next_ref
from app.services import attachments as att_svc

from app.services import frameworks as fw_svc

bp = Blueprint("documents", __name__, url_prefix="/documents")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
@login_required
def index():
    f_type = request.args.get("type")
    f_status = request.args.get("statut")
    q = Document.query
    if f_type in [t.value for t in DocType]:
        q = q.filter(Document.doc_type == DocType(f_type))
    if f_status in [s.value for s in DocStatus]:
        q = q.filter(Document.status == DocStatus(f_status))
    docs = q.order_by(Document.ref).all()
    to_review = [d for d in Document.query.all() if d.review_overdue or d.review_soon]
    att_counts = att_svc.counts_for("document", [d.id for d in docs])
    return render_template("documents/index.html", docs=docs, to_review=to_review,
                           att_counts=att_counts, f_type=f_type, f_status=f_status)


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre est obligatoire.", "danger")
        else:
            d = Document(
                ref=(request.form.get("ref") or "").strip() or next_ref(Document, "DOC", width=3, yearly=False),
                title=title,
                doc_type=DocType(request.form.get("doc_type", "PROCEDURE")),
                version=(request.form.get("version") or "1.0").strip()[:16],
                status=DocStatus.BROUILLON,
                owner_id=request.form.get("owner_id", type=int) or None,
                location=request.form.get("location"),
                next_review_at=_date(request.form.get("next_review_at")),
                note=request.form.get("note"))
            db.session.add(d)
            db.session.commit()
            fw_svc.links_from_form(d, request.form)
            db.session.commit()
            att_svc.save_many(request.files.getlist("attachments"), "document", d.id, current_user)
            flash(f"Document {d.ref} créé en brouillon. Soumettez-le pour approbation une fois rédigé.", "success")
            return redirect(url_for("documents.detail", doc_id=d.id))
    return render_template("documents/form.html", users=users, doc=None,
                           DocType=DocType, DocStatus=DocStatus)


@bp.route("/<int:doc_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        d.title = (request.form.get("title") or d.title).strip()
        d.doc_type = DocType(request.form.get("doc_type", d.doc_type.value))
        if d.status == DocStatus.BROUILLON:
            d.version = (request.form.get("version") or d.version).strip()[:16]
        d.owner_id = request.form.get("owner_id", type=int) or None
        d.location = request.form.get("location")
        d.next_review_at = _date(request.form.get("next_review_at"))
        d.note = request.form.get("note")
        fw_svc.links_from_form(d, request.form)
        db.session.commit()
        flash(f"Document {d.ref} mis à jour.", "success")
        return redirect(url_for("documents.detail", doc_id=d.id))
    return render_template("documents/form.html", users=users, doc=d,
                           attachments=att_svc.get_for("document", d.id),
                           DocType=DocType, DocStatus=DocStatus)


@bp.route("/<int:doc_id>")
@login_required
def detail(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    return render_template("documents/detail.html", d=d, attachments=att_svc.get_for("document", d.id))


# --- Circuit d'approbation (7.5.2 / 7.5.3) ---------------------------------
def _workflow(d, expected, message):
    if d.status not in expected:
        flash(message, "warning")
        return False
    return True


@bp.route("/<int:doc_id>/soumettre", methods=["POST"])
@editor_required
def submit(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    if _workflow(d, (DocStatus.BROUILLON,), "Seul un brouillon peut être soumis pour approbation."):
        summary = (request.form.get("change_summary") or "").strip()
        if not summary:
            flash("Décrivez les modifications apportées dans cette version.", "danger")
            return redirect(url_for("documents.detail", doc_id=d.id))
        d.change_summary = summary
        d.submitted_by_id = current_user.id
        d.submitted_at = datetime.utcnow()
        d.status = DocStatus.EN_REVUE
        db.session.commit()
        log_event("workflow", f"Version {d.version} soumise pour approbation", entity=d)
        flash(f"{d.ref} v{d.version} soumis pour approbation.", "success")
    return redirect(url_for("documents.detail", doc_id=d.id))


@bp.route("/<int:doc_id>/approuver", methods=["POST"])
@rssi_required
def approve(doc_id):
    from datetime import date, timedelta
    d = db.session.get(Document, doc_id) or abort(404)
    if _workflow(d, (DocStatus.EN_REVUE,), "Seul un document soumis peut être approuvé."):
        now = datetime.utcnow()
        for v in d.versions:
            if v.retired_at is None:
                v.retired_at = now
        db.session.add(DocumentVersion(document_id=d.id, version=d.version, change_summary=d.change_summary,
                                       submitted_by_id=d.submitted_by_id, submitted_at=d.submitted_at,
                                       approved_by_id=current_user.id, approved_at=now))
        d.status = DocStatus.APPROUVE
        d.approved_by_id = current_user.id
        d.approved_at = now.date()
        if not d.next_review_at or d.next_review_at <= date.today():
            d.next_review_at = date.today() + timedelta(days=365)
        db.session.commit()
        log_event("workflow", f"Version {d.version} approuvée", entity=d)
        flash(f"{d.ref} v{d.version} approuvé. Prochaine revue le {d.next_review_at.strftime('%d/%m/%Y')}.", "success")
    return redirect(url_for("documents.detail", doc_id=d.id))


@bp.route("/<int:doc_id>/refuser", methods=["POST"])
@rssi_required
def reject(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    if _workflow(d, (DocStatus.EN_REVUE,), "Seul un document soumis peut être renvoyé en brouillon."):
        comment = (request.form.get("comment") or "").strip()
        d.status = DocStatus.BROUILLON
        db.session.commit()
        log_event("workflow", f"Version {d.version} renvoyée en brouillon" + (f" : {comment}" if comment else ""), entity=d)
        flash(f"{d.ref} renvoyé en brouillon.", "success")
    return redirect(url_for("documents.detail", doc_id=d.id))


def _bump(version, major):
    try:
        parts = [int(p) for p in version.split(".")[:2]] + [0]
        return f"{parts[0] + 1}.0" if major else f"{parts[0]}.{parts[1] + 1}"
    except ValueError:
        return version + "-r"


@bp.route("/<int:doc_id>/nouvelle-version", methods=["POST"])
@editor_required
def new_version(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    if _workflow(d, (DocStatus.APPROUVE,), "Une nouvelle version se crée à partir d'un document approuvé."):
        previous = d.version
        d.version = _bump(d.version, request.form.get("kind") == "majeure")
        d.status = DocStatus.BROUILLON
        d.change_summary = d.submitted_by_id = d.submitted_at = None
        db.session.commit()
        log_event("workflow", f"Nouvelle version {d.version} ouverte (la version {previous} reste en vigueur jusqu'à approbation)", entity=d)
        flash(f"Version {d.version} créée en brouillon. La version {previous} reste la version approuvée de référence.", "success")
    return redirect(url_for("documents.detail", doc_id=d.id))


@bp.route("/<int:doc_id>/obsolete", methods=["POST"])
@rssi_required
def retire(doc_id):
    d = db.session.get(Document, doc_id) or abort(404)
    if _workflow(d, (DocStatus.APPROUVE, DocStatus.BROUILLON, DocStatus.EN_REVUE), "Document déjà obsolète."):
        now = datetime.utcnow()
        for v in d.versions:
            if v.retired_at is None:
                v.retired_at = now
        d.status = DocStatus.OBSOLETE
        db.session.commit()
        log_event("workflow", "Document rendu obsolète (retiré de la diffusion)", entity=d)
        flash(f"{d.ref} rendu obsolète.", "success")
    return redirect(url_for("documents.detail", doc_id=d.id))
