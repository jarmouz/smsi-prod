"""Qualité (ISO 9001:2015) : cartographie des processus (4.4), satisfaction client (9.1.2),
réclamations clients. Accessible quand l'organisation a activé l'ISO 9001."""
from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import User, Risk, Document, Indicator, NonConformity
from app.services.risk_links import risk_choices
from app.models.quality import (QmsProcess, ProcessType, QmsProcessStatus, CustomerSurvey, SurveyMethod, Complaint,
                                ComplaintStatus, ComplaintSeverity)
from app.services import attachments as att_svc
from app.services import frameworks as fw_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("quality", __name__, url_prefix="/qualite")
CODE = "ISO9001"


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _float(s):
    try:
        return float((s or "").replace(",", ".").replace("%", "").strip())
    except ValueError:
        return None


def _tri(s):
    return {"oui": True, "non": False}.get(s)


def norm_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not fw_svc.is_enabled(CODE):
            abort(404)
        return fn(*a, **k)
    return w


def _users():
    return User.query.filter_by(is_active_flag=True).order_by(User.name).all()


def _ids(name):
    return [int(x) for x in request.form.getlist(name) if x.isdigit()]


# --- Cartographie des processus ----------------------------------------------
@bp.route("/processus")
@login_required
@norm_required
def index():
    procs = QmsProcess.query.order_by(QmsProcess.sort_order, QmsProcess.ref).all()
    bands = {t: [p for p in procs if p.process_type == t and p.status != QmsProcessStatus.RETIRE] for t in ProcessType}
    live = [p for p in procs if p.status != QmsProcessStatus.RETIRE]
    stats = {"live": len(live), "no_pilot": sum(not p.pilot_id for p in live),
             "no_kpi": sum(not p.indicators for p in live), "gaps": sum(bool(p.gaps) for p in live)}
    return render_template("quality/index.html", bands=bands, procs=procs, stats=stats, ProcessType=ProcessType)


@bp.route("/processus/<int:pid>")
@login_required
@norm_required
def process_detail(pid):
    p = db.session.get(QmsProcess, pid) or abort(404)
    upstream = [x for x in QmsProcess.query.all() if p in x.next_processes]
    return render_template("quality/process_detail.html", p=p, upstream=upstream,
                           attachments=att_svc.get_for("qmsprocess", p.id))


@bp.route("/processus/nouveau", methods=["GET", "POST"])
@editor_required
@norm_required
def process_create():
    return _process_form(None)


@bp.route("/processus/<int:pid>/modifier", methods=["GET", "POST"])
@editor_required
@norm_required
def process_edit(pid):
    return _process_form(db.session.get(QmsProcess, pid) or abort(404))


def _process_form(p):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom du processus est obligatoire.", "danger")
        else:
            if p is None:
                p = QmsProcess(ref=next_ref(QmsProcess, "PRC", width=2, yearly=False))
                db.session.add(p)
            p.name = name
            for f in ("purpose", "inputs", "outputs", "beneficiaries", "resources", "activities", "notes"):
                setattr(p, f, (request.form.get(f) or "").strip() or None)
            p.process_type = ProcessType(request.form.get("process_type", "REALISATION"))
            p.status = QmsProcessStatus(request.form.get("status", "ACTIF"))
            p.pilot_id = request.form.get("pilot_id", type=int) or None
            p.sort_order = request.form.get("sort_order", type=int) or 0
            p.last_review = _date(request.form.get("last_review"))
            p.next_review = _date(request.form.get("next_review")) or (
                date(p.last_review.year + 1, p.last_review.month, min(p.last_review.day, 28)) if p.last_review else None)
            ids = _ids("indicator_ids")
            p.indicators = Indicator.query.filter(Indicator.id.in_(ids)).all() if ids else []
            ids = _ids("risk_ids")
            p.risks = Risk.query.filter(Risk.id.in_(ids)).all() if ids else []
            ids = _ids("document_ids")
            p.documents = Document.query.filter(Document.id.in_(ids)).all() if ids else []
            db.session.flush()
            ids = [i for i in _ids("next_ids") if i != p.id]
            p.next_processes = QmsProcess.query.filter(QmsProcess.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Processus {p.ref} enregistré.", "success")
            return redirect(url_for("quality.process_detail", pid=p.id))
    others = [x for x in QmsProcess.query.order_by(QmsProcess.ref).all() if p is None or x.id != p.id]
    return render_template("quality/process_form.html", p=p, users=_users(), ProcessType=ProcessType,
                           QmsProcessStatus=QmsProcessStatus, others=others,
                           indicators=Indicator.query.order_by(Indicator.ref).all(),
                           risks=risk_choices("QUALITE"), documents=Document.query.order_by(Document.ref).all())


# --- Satisfaction client ------------------------------------------------------
@bp.route("/satisfaction")
@login_required
@norm_required
def surveys():
    items = CustomerSurvey.query.order_by(CustomerSurvey.conducted_on.desc().nullslast(), CustomerSurvey.id.desc()).all()
    scored = [s for s in items if s.score is not None and s.conducted_on]
    last = scored[0] if scored else None
    prev = scored[1] if len(scored) > 1 else None
    stats = {"count": len(items), "last": last, "trend": (last.score - prev.score) if last and prev else None,
             "below": sum(s.below_target for s in items)}
    return render_template("quality/surveys.html", items=items, stats=stats)


@bp.route("/satisfaction/nouvelle", methods=["GET", "POST"])
@editor_required
@norm_required
def survey_create():
    return _survey_form(None)


@bp.route("/satisfaction/<int:sid>", methods=["GET", "POST"])
@editor_required
@norm_required
def survey_edit(sid):
    return _survey_form(db.session.get(CustomerSurvey, sid) or abort(404))


def _survey_form(s):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé est obligatoire.", "danger")
        else:
            if s is None:
                s = CustomerSurvey(ref=next_ref(CustomerSurvey, "SAT", width=2))
                db.session.add(s)
            s.title = title
            for f in ("scope", "strengths", "improvements", "actions"):
                setattr(s, f, (request.form.get(f) or "").strip() or None)
            s.method = SurveyMethod(request.form.get("method", "ENQUETE"))
            s.conducted_on = _date(request.form.get("conducted_on"))
            s.respondents = request.form.get("respondents", type=int)
            s.score = _float(request.form.get("score"))
            s.target = _float(request.form.get("target"))
            s.owner_id = request.form.get("owner_id", type=int) or None
            db.session.commit()
            flash(f"Mesure {s.ref} enregistrée." + (" Résultat sous l'objectif : prévoyez des actions." if s.below_target else ""),
                  "warning" if s.below_target else "success")
            return redirect(url_for("quality.surveys"))
    return render_template("quality/survey_form.html", s=s, users=_users(), SurveyMethod=SurveyMethod)


# --- Réclamations clients -------------------------------------------------------
@bp.route("/reclamations")
@login_required
@norm_required
def complaints():
    f_open = request.args.get("ouvertes", "1")
    items = Complaint.query.order_by(Complaint.received_on.desc(), Complaint.id.desc()).all()
    allc = list(items)
    if f_open == "1":
        items = [c for c in items if not c.status.closed]
    year = date.today().year
    closed = [c for c in allc if c.status.closed]
    stats = {"open": sum(not c.status.closed for c in allc), "overdue": sum(c.overdue for c in allc),
             "year": sum(c.received_on.year == year for c in allc if c.received_on),
             "justified": sum(bool(c.justified) for c in closed), "closed": len(closed)}
    return render_template("quality/complaints.html", items=items, stats=stats, f_open=f_open)


@bp.route("/reclamations/nouvelle", methods=["GET", "POST"])
@editor_required
@norm_required
def complaint_create():
    return _complaint_form(None)


@bp.route("/reclamations/<int:cid>", methods=["GET", "POST"])
@editor_required
@norm_required
def complaint_edit(cid):
    return _complaint_form(db.session.get(Complaint, cid) or abort(404))


def _complaint_form(c):
    if request.method == "POST":
        customer = (request.form.get("customer") or "").strip()
        if not customer:
            flash("Indiquez le client.", "danger")
        else:
            if c is None:
                c = Complaint(ref=next_ref(Complaint, "REC", width=4))
                db.session.add(c)
            c.customer = customer[:200]
            c.channel = (request.form.get("channel") or "").strip()[:120] or None
            c.product = (request.form.get("product") or "").strip()[:300] or None
            for f in ("description", "analysis", "response"):
                setattr(c, f, (request.form.get(f) or "").strip() or None)
            c.received_on = _date(request.form.get("received_on")) or c.received_on or date.today()
            c.due_on = _date(request.form.get("due_on")) or c.default_due(c.received_on)
            c.severity = ComplaintSeverity(request.form.get("severity", "MINEURE"))
            c.status = ComplaintStatus(request.form.get("status", "RECUE"))
            c.justified = _tri(request.form.get("justified"))
            c.customer_satisfied = _tri(request.form.get("customer_satisfied"))
            c.nonconformity_id = request.form.get("nonconformity_id", type=int) or None
            c.owner_id = request.form.get("owner_id", type=int) or None
            c.closed_on = (_date(request.form.get("closed_on")) or c.closed_on or date.today()) if c.status.closed else None
            db.session.commit()
            flash(f"Réclamation {c.ref} enregistrée." + (f" Réponse attendue avant le {c.due_on:%d/%m/%Y}."
                                                         if not c.status.closed else ""), "success")
            return redirect(url_for("quality.complaint_edit", cid=c.id))
    return render_template("quality/complaint_form.html", c=c, users=_users(), ComplaintStatus=ComplaintStatus,
                           ComplaintSeverity=ComplaintSeverity, days=Complaint.RESPONSE_DAYS,
                           ncs=NonConformity.query.order_by(NonConformity.id.desc()).limit(300).all())
