"""Registre des fournisseurs et suivi de leur sécurité (A.5.19 à A.5.22)."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import (Supplier, User, SupplierCategory, Criticality, DataAccess, AssessmentResult,
                        SupplierStatus)
from app.services import attachments as att_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("suppliers", __name__, url_prefix="/fournisseurs")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
@login_required
def index():
    f_crit = request.args.get("criticite")
    f_gap = request.args.get("ecarts")
    q = Supplier.query
    if f_crit in [x.value for x in Criticality]:
        q = q.filter(Supplier.criticality == Criticality(f_crit))
    order = {"CRITIQUE": 0, "IMPORTANT": 1, "STANDARD": 2}
    suppliers = sorted(q.all(), key=lambda s: (s.status != SupplierStatus.ACTIF, order[s.criticality.value], s.name))
    if f_gap:
        suppliers = [s for s in suppliers if s.gaps]
    active = [s for s in Supplier.query.all() if s.status == SupplierStatus.ACTIF]
    stats = {"active": len(active), "critical": sum(s.criticality == Criticality.CRITIQUE for s in active),
             "gaps": sum(bool(s.gaps) for s in active), "overdue": sum(s.assessment_overdue for s in active)}
    return render_template("suppliers/index.html", suppliers=suppliers, stats=stats, f_crit=f_crit, f_gap=f_gap,
                           Criticality=Criticality)


@bp.route("/<int:sup_id>")
@login_required
def detail(sup_id):
    s = db.session.get(Supplier, sup_id) or abort(404)
    return render_template("suppliers/detail.html", s=s, attachments=att_svc.get_for("supplier", s.id))


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:sup_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(sup_id):
    return _form(db.session.get(Supplier, sup_id) or abort(404))


def _form(s):
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom du fournisseur est obligatoire.", "danger")
        else:
            if s is None:
                s = Supplier(ref=next_ref(Supplier, "FRN", width=3, yearly=False))
                db.session.add(s)
            s.name = name
            s.service = request.form.get("service")
            s.category = SupplierCategory(request.form.get("category", "LOGICIEL"))
            s.criticality = Criticality(request.form.get("criticality", "STANDARD"))
            s.data_access = DataAccess(request.form.get("data_access", "AUCUN"))
            s.status = SupplierStatus(request.form.get("status", "ACTIF"))
            s.contact = request.form.get("contact")
            s.contract_ref = request.form.get("contract_ref")
            s.contract_end = _date(request.form.get("contract_end"))
            s.security_clauses = bool(request.form.get("security_clauses"))
            s.dpa = bool(request.form.get("dpa"))
            s.certifications = request.form.get("certifications")
            s.assessment_result = AssessmentResult(request.form.get("assessment_result", "NON_EVALUE"))
            s.last_assessment = _date(request.form.get("last_assessment"))
            s.next_assessment = _date(request.form.get("next_assessment"))
            if s.last_assessment and not s.next_assessment:
                s.next_assessment = s.default_next(s.last_assessment)
            s.owner_id = request.form.get("owner_id", type=int) or None
            s.notes = request.form.get("notes")
            db.session.commit()
            flash(f"Fournisseur {s.ref} enregistré." + (f" Prochaine évaluation : {s.next_assessment:%d/%m/%Y}."
                                                         if s.next_assessment else ""), "success")
            return redirect(url_for("suppliers.detail", sup_id=s.id))
    return render_template("suppliers/form.html", s=s, users=users, SupplierCategory=SupplierCategory,
                           Criticality=Criticality, DataAccess=DataAccess, AssessmentResult=AssessmentResult,
                           SupplierStatus=SupplierStatus, months=Supplier.REVIEW_MONTHS)
