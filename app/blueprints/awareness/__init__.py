from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import AwarenessAction, AwarenessType, AwarenessStatus
from app.services.access import editor_required
from app.services.refs import next_ref
from app.services import attachments as att_svc

bp = Blueprint("awareness", __name__, url_prefix="/sensibilisation")


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
    q = AwarenessAction.query
    if f_type in [x.value for x in AwarenessType]:
        q = q.filter(AwarenessAction.atype == AwarenessType(f_type))
    if f_status in [x.value for x in AwarenessStatus]:
        q = q.filter(AwarenessAction.status == AwarenessStatus(f_status))
    actions = q.order_by(AwarenessAction.action_date.desc().nullslast()).all()
    done = [a for a in AwarenessAction.query.filter_by(status=AwarenessStatus.TERMINEE).all() if a.completion_rate]
    avg = round(sum(a.completion_rate for a in done) / len(done)) if done else None
    stats = {"total": AwarenessAction.query.count(),
             "terminees": AwarenessAction.query.filter_by(status=AwarenessStatus.TERMINEE).count(),
             "avg": avg}
    return render_template("awareness/index.html", actions=actions, stats=stats,
                           f_type=f_type, f_status=f_status,
                           AwarenessType=AwarenessType, AwarenessStatus=AwarenessStatus)


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:action_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(action_id):
    return _form(db.session.get(AwarenessAction, action_id) or abort(404))


def _form(a):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre est obligatoire.", "danger")
        else:
            creating = a is None
            if creating:
                a = AwarenessAction(ref=next_ref(AwarenessAction, "SENS"))
                db.session.add(a)
            a.title = title
            a.atype = AwarenessType(request.form.get("atype", "FORMATION"))
            a.status = AwarenessStatus(request.form.get("status", "PLANIFIEE"))
            a.action_date = _date(request.form.get("action_date"))
            a.audience = request.form.get("audience")
            a.participants = request.form.get("participants", type=int)
            a.completion_rate = request.form.get("completion_rate", type=int)
            a.notes = request.form.get("notes")
            db.session.commit()
            att_svc.save_many(request.files.getlist("attachments"), "awareness", a.id, None)
            flash(f"Action {a.ref} enregistrée.", "success")
            return redirect(url_for("awareness.index"))
    return render_template("awareness/form.html", a=a,
                           attachments=att_svc.get_for("awareness", a.id) if a else [],
                           AwarenessType=AwarenessType, AwarenessStatus=AwarenessStatus)
