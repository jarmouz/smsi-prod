"""Compétences (7.2) : compétences requises, preuves par personne, écarts."""
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import CompetenceRequirement, CompetenceRecord, User, CompetenceType
from app.services import attachments as att_svc
from app.services.access import editor_required

bp = Blueprint("competences", __name__, url_prefix="/competences")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _users():
    return User.query.filter_by(is_active_flag=True, is_readonly=False).order_by(User.name).all()


@bp.route("/")
@login_required
def index():
    reqs = CompetenceRequirement.query.order_by(CompetenceRequirement.title).all()
    records = CompetenceRecord.query.order_by(CompetenceRecord.expires_at.is_(None), CompetenceRecord.expires_at).all()
    stats = {"reqs": len(reqs), "gaps": sum(len(r.gaps) for r in reqs),
             "expired": sum(r.expired for r in records), "soon": sum(r.expires_soon for r in records)}
    return render_template("competences/index.html", reqs=reqs, records=records, stats=stats)


@bp.route("/exigences/nouvelle", methods=["GET", "POST"])
@editor_required
def create_requirement():
    return _req_form(None)


@bp.route("/exigences/<int:req_id>", methods=["GET", "POST"])
@editor_required
def edit_requirement(req_id):
    return _req_form(db.session.get(CompetenceRequirement, req_id) or abort(404))


def _req_form(r):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de la compétence est obligatoire.", "danger")
        else:
            if r is None:
                r = CompetenceRequirement()
                db.session.add(r)
            r.title = title
            r.description = request.form.get("description")
            r.validity_months = request.form.get("validity_months", type=int) or None
            ids = request.form.getlist("users", type=int)
            r.users = User.query.filter(User.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash("Compétence requise enregistrée.", "success")
            return redirect(url_for("competences.index"))
    return render_template("competences/requirement_form.html", r=r, users=_users())


@bp.route("/preuves/nouvelle", methods=["GET", "POST"])
@editor_required
def create_record():
    return _record_form(None)


@bp.route("/preuves/<int:rec_id>", methods=["GET", "POST"])
@editor_required
def edit_record(rec_id):
    return _record_form(db.session.get(CompetenceRecord, rec_id) or abort(404))


def _record_form(rec):
    reqs = CompetenceRequirement.query.order_by(CompetenceRequirement.title).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        user_id = request.form.get("user_id", type=int)
        if not title or not user_id or not db.session.get(User, user_id):
            flash("La personne et l'intitulé sont obligatoires.", "danger")
        else:
            if rec is None:
                rec = CompetenceRecord()
                db.session.add(rec)
            rec.user_id = user_id
            rec.title = title
            rec.requirement_id = request.form.get("requirement_id", type=int) or None
            rec.ctype = CompetenceType(request.form.get("ctype", "FORMATION"))
            rec.provider = request.form.get("provider")
            rec.obtained_at = _date(request.form.get("obtained_at"))
            rec.expires_at = _date(request.form.get("expires_at"))
            if not rec.expires_at and rec.obtained_at and rec.requirement_id:
                req = db.session.get(CompetenceRequirement, rec.requirement_id)
                if req and req.validity_months:
                    rec.expires_at = rec.obtained_at + timedelta(days=round(req.validity_months * 30.44))
            rec.note = request.form.get("note")
            db.session.commit()
            flash("Preuve de compétence enregistrée. Joignez l'attestation ci-dessous.", "success")
            return redirect(url_for("competences.edit_record", rec_id=rec.id))
    return render_template("competences/record_form.html", rec=rec, reqs=reqs, users=_users(),
                           CompetenceType=CompetenceType, preset_user=request.args.get("user", type=int),
                           preset_req=request.args.get("exigence", type=int),
                           attachments=att_svc.get_for("competence", rec.id) if rec else [])
