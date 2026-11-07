from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.services import risk_criteria, governance
from app.models import (
    ManagementReview, ReviewAction, Control, Risk, Finding, User,
    ReviewStatus, ActionStatus, ControlStatus, RiskStatus, FindingType,
)
from app.services.access import rssi_required, editor_required
from app.services.refs import next_ref
from app.services import attachments as att_svc

bp = Blueprint("reviews", __name__, url_prefix="/revue-direction")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
@login_required
def index():
    reviews = ManagementReview.query.order_by(ManagementReview.created_at.desc()).all()
    return render_template("reviews/index.html", reviews=reviews)


@bp.route("/nouvelle", methods=["GET", "POST"])
@rssi_required
def create():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre est obligatoire.", "danger")
        else:
            r = ManagementReview(
                ref=next_ref(ManagementReview, "RD", width=2),
                title=title, review_date=_date(request.form.get("review_date")),
                status=ReviewStatus(request.form.get("status", "PLANIFIEE")),
                participants=request.form.get("participants"),
                inputs=request.form.get("inputs"),
                decisions=request.form.get("decisions"))
            db.session.add(r)
            db.session.commit()
            att_svc.save_many(request.files.getlist("attachments"), "review", r.id, current_user)
            flash(f"Revue {r.ref} créée.", "success")
            return redirect(url_for("reviews.detail", review_id=r.id))
    # Aide à la préparation : synthèse pour les données d'entrée (clause 9.3.2)
    return render_template("reviews/form.html", review=None, ReviewStatus=ReviewStatus,
                           digest=_digest())


@bp.route("/<int:review_id>")
@login_required
def detail(review_id):
    r = db.session.get(ManagementReview, review_id) or abort(404)
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    attachments = att_svc.get_for("review", r.id)
    return render_template("reviews/detail.html", r=r, users=users, ActionStatus=ActionStatus,
                           attachments=attachments)


@bp.route("/<int:review_id>/modifier", methods=["GET", "POST"])
@rssi_required
def edit(review_id):
    r = db.session.get(ManagementReview, review_id) or abort(404)
    if request.method == "POST":
        r.title = (request.form.get("title") or r.title).strip()
        r.review_date = _date(request.form.get("review_date"))
        r.status = ReviewStatus(request.form.get("status", r.status.value))
        r.participants = request.form.get("participants")
        r.inputs = request.form.get("inputs")
        r.decisions = request.form.get("decisions")
        db.session.commit()
        flash(f"Revue {r.ref} mise à jour.", "success")
        return redirect(url_for("reviews.detail", review_id=r.id))
    return render_template("reviews/form.html", review=r, ReviewStatus=ReviewStatus, digest=_digest())


@bp.route("/<int:review_id>/action", methods=["POST"])
@editor_required
def add_action(review_id):
    r = db.session.get(ManagementReview, review_id) or abort(404)
    desc = (request.form.get("description") or "").strip()
    if desc:
        db.session.add(ReviewAction(
            review_id=r.id, description=desc,
            owner_id=request.form.get("owner_id", type=int) or None,
            due_date=_date(request.form.get("due_date")), status=ActionStatus.OUVERTE))
        db.session.commit()
        flash("Décision / action ajoutée.", "success")
    return redirect(url_for("reviews.detail", review_id=r.id))


@bp.route("/action/<int:action_id>/statut", methods=["POST"])
@editor_required
def action_status(action_id):
    ac = db.session.get(ReviewAction, action_id) or abort(404)
    try:
        ac.status = ActionStatus(request.form.get("status"))
        db.session.commit()
    except ValueError:
        pass
    return redirect(url_for("reviews.detail", review_id=ac.review_id))


def _digest():
    """Synthèse automatique pour préparer les données d'entrée (clause 9.3.2)."""
    controls = Control.of().all()
    appl = [c for c in controls if c.applicable]
    impl = [c for c in appl if c.status == ControlStatus.IMPLEMENTE]
    risks = Risk.query.all()
    open_ncs = Finding.query.filter(
        Finding.type.in_([FindingType.NC_MAJEURE, FindingType.NC_MINEURE]),
        Finding.closed.is_(False)).count()
    return {
        "soa_rate": round(100 * len(impl) / len(appl)) if appl else 0,
        "applicable": len(appl),
        "risks_open": len([r for r in risks if r.status.is_open]),
        "risks_high": len([r for r in risks if r.effective_score >= risk_criteria.high_threshold() and r.status.is_open]),
        "open_ncs": open_ncs,
        **governance.summary(),
    }
