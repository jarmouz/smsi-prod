from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Evidence, Control, User
from app.services.access import editor_required
from app.services.refs import next_ref
from app.services import attachments as att_svc

bp = Blueprint("evidence", __name__, url_prefix="/preuves")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
@login_required
def index():
    f_control = request.args.get("mesure", type=int)
    evidences = Evidence.query.order_by(Evidence.ref).all()
    if f_control:
        evidences = [e for e in evidences if any(c.id == f_control for c in e.controls)]
    controls = []
    att_counts = att_svc.counts_for("evidence", [e.id for e in evidences])
    return render_template("evidence/index.html", evidences=evidences,
                           controls=controls, f_control=f_control, att_counts=att_counts)


@bp.route("/nouvelle", methods=["GET", "POST"])
@editor_required
def create():
    from app.services import frameworks as fw_svc
    groups = fw_svc.picker_groups()
    controls = []
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre de la preuve est obligatoire.", "danger")
        else:
            e = Evidence(
                ref=next_ref(Evidence, "PRV", width=4, yearly=False),
                title=title, description=request.form.get("description"),
                collected_at=_date(request.form.get("collected_at")),
                owner_id=request.form.get("owner_id", type=int) or None,
                location=request.form.get("location"))
            e.controls = fw_svc.controls_from_ids([], request.form.getlist("controls", type=int), groups)
            db.session.add(e)
            db.session.commit()
            att_svc.save_many(request.files.getlist("attachments"), "evidence", e.id, current_user)
            flash(f"Preuve {e.ref} enregistrée.", "success")
            return redirect(url_for("evidence.index"))
    return render_template("evidence/form.html", controls=controls, users=users, ev=None)


@bp.route("/<int:ev_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(ev_id):
    e = db.session.get(Evidence, ev_id) or abort(404)
    from app.services import frameworks as fw_svc
    groups = fw_svc.picker_groups()
    controls = []
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        e.title = (request.form.get("title") or e.title).strip()
        e.description = request.form.get("description")
        e.collected_at = _date(request.form.get("collected_at"))
        e.owner_id = request.form.get("owner_id", type=int) or None
        e.location = request.form.get("location")
        e.controls = fw_svc.controls_from_ids(e.controls, request.form.getlist("controls", type=int), groups)
        db.session.commit()
        flash(f"Preuve {e.ref} mise à jour.", "success")
        return redirect(url_for("evidence.index"))
    return render_template("evidence/form.html", controls=controls, users=users, ev=e,
                           attachments=att_svc.get_for("evidence", e.id))
