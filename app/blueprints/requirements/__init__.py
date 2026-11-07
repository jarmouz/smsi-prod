"""Registre des exigences légales, réglementaires, contractuelles et normatives (A.5.31, 4.2 b)."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import (Requirement, InterestedParty, Control, User, RequirementType, ComplianceStatus)
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("requirements", __name__, url_prefix="/exigences")


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
    q = Requirement.query
    if f_type in [x.value for x in RequirementType]:
        q = q.filter(Requirement.req_type == RequirementType(f_type))
    if f_status in [x.value for x in ComplianceStatus]:
        q = q.filter(Requirement.status == ComplianceStatus(f_status))
    reqs = q.order_by(Requirement.ref).all()
    all_r = Requirement.query.all()
    stats = {s.value: sum(r.status == s for r in all_r) for s in ComplianceStatus}
    stats["total"] = len(all_r)
    stats["overdue"] = sum(r.review_overdue for r in all_r)
    return render_template("requirements/index.html", reqs=reqs, stats=stats, f_type=f_type, f_status=f_status,
                           RequirementType=RequirementType, ComplianceStatus=ComplianceStatus)


@bp.route("/nouvelle", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:req_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(req_id):
    return _form(db.session.get(Requirement, req_id) or abort(404))


def _form(r):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de l'exigence est obligatoire.", "danger")
        else:
            if r is None:
                r = Requirement(ref=next_ref(Requirement, "EXG", width=3, yearly=False))
                db.session.add(r)
            r.title = title
            r.req_type = RequirementType(request.form.get("req_type", "LEGALE"))
            r.source = request.form.get("source")
            r.issuer = request.form.get("issuer")
            r.obligation = request.form.get("obligation")
            r.response = request.form.get("response")
            r.status = ComplianceStatus(request.form.get("status", "A_EVALUER"))
            r.party_id = request.form.get("party_id", type=int) or None
            r.owner_id = request.form.get("owner_id", type=int) or None
            r.last_review = _date(request.form.get("last_review"))
            r.next_review = _date(request.form.get("next_review"))
            ids = request.form.getlist("controls", type=int)
            r.controls = Control.query.filter(Control.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Exigence {r.ref} enregistrée.", "success")
            return redirect(url_for("requirements.index") + f"#r{r.id}")
    return render_template("requirements/form.html", r=r,
                           users=User.query.filter_by(is_active_flag=True).order_by(User.name).all(),
                           parties=InterestedParty.query.order_by(InterestedParty.ref).all(),
                           controls=Control.of().order_by(Control.id).all(),
                           RequirementType=RequirementType, ComplianceStatus=ComplianceStatus)
