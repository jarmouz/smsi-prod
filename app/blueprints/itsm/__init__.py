"""Management des services informatiques (ISO/IEC 20000-1) : catalogue de services et niveaux
de service (8.2.4, 8.3.3, 9.4), problèmes (8.6.3), mises en production (8.5.3).
Accessible quand l'organisation a activé l'ISO/IEC 20000-1."""
import re
from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import User, Asset, Supplier, Incident, ChangeRequest
from app.models.service_mgmt import (ItService, ServiceMeasure, ServiceStatus, Problem, ProblemStatus, Priority,
                                     Release, ReleaseStatus)
from app.services import attachments as att_svc
from app.services import frameworks as fw_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("itsm", __name__, url_prefix="/services")
CODE = "ISO20000"


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


# --- Catalogue de services ----------------------------------------------------
@bp.route("/")
@login_required
@norm_required
def index():
    order = {"ACTIF": 0, "EN_PROJET": 1, "RETIRE": 2}
    services = sorted(ItService.query.all(), key=lambda s: (order[s.status.value], -s.criticality, s.ref))
    live = [s for s in services if s.status == ServiceStatus.ACTIF]
    stats = {"live": len(live), "sla": sum(s.availability_target is not None or bool(s.response_time) for s in live),
             "breach": sum(bool(s.last_measure and s.last_measure.breached) for s in live),
             "problems": Problem.query.filter(Problem.status.notin_([ProblemStatus.RESOLU, ProblemStatus.CLOS])).count()}
    return render_template("itsm/index.html", services=services, stats=stats)


@bp.route("/<int:sid>")
@login_required
@norm_required
def detail(sid):
    s = db.session.get(ItService, sid) or abort(404)
    problems = Problem.query.filter_by(service_id=s.id).order_by(Problem.opened_on.desc()).all()
    releases = Release.query.filter_by(service_id=s.id).order_by(Release.planned_on.desc().nullslast()).all()
    return render_template("itsm/detail.html", s=s, problems=problems, releases=releases,
                           attachments=att_svc.get_for("itservice", s.id), this_month=date.today().strftime("%Y-%m"))


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
@norm_required
def create():
    return _service_form(None)


@bp.route("/<int:sid>/modifier", methods=["GET", "POST"])
@editor_required
@norm_required
def edit(sid):
    return _service_form(db.session.get(ItService, sid) or abort(404))


def _service_form(s):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom du service est obligatoire.", "danger")
        else:
            if s is None:
                s = ItService(ref=next_ref(ItService, "SRV", width=3, yearly=False))
                db.session.add(s)
            s.name = name
            for f in ("description", "customers", "notes"):
                setattr(s, f, (request.form.get(f) or "").strip() or None)
            for f in ("support_hours", "response_time", "resolution_time", "sla_reference"):
                setattr(s, f, (request.form.get(f) or "").strip()[:200] or None)
            s.status = ServiceStatus(request.form.get("status", "ACTIF"))
            s.criticality = min(4, max(1, request.form.get("criticality", type=int) or 2))
            s.availability_target = _float(request.form.get("availability_target"))
            s.sla_review = _date(request.form.get("sla_review"))
            s.owner_id = request.form.get("owner_id", type=int) or None
            ids = _ids("asset_ids")
            s.assets = Asset.query.filter(Asset.id.in_(ids)).all() if ids else []
            ids = _ids("supplier_ids")
            s.suppliers = Supplier.query.filter(Supplier.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Service {s.ref} enregistré.", "success")
            return redirect(url_for("itsm.detail", sid=s.id))
    return render_template("itsm/form.html", s=s, users=_users(), ServiceStatus=ServiceStatus,
                           assets=Asset.query.order_by(Asset.name).all(),
                           suppliers=Supplier.query.order_by(Supplier.name).all())


@bp.route("/<int:sid>/mesure", methods=["POST"])
@editor_required
@norm_required
def add_measure(sid):
    s = db.session.get(ItService, sid) or abort(404)
    period = (request.form.get("period") or "").strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        flash("Période attendue au format AAAA-MM.", "danger")
        return redirect(url_for("itsm.detail", sid=s.id))
    m = ServiceMeasure.query.filter_by(service_id=s.id, period=period).first()
    if m is None:
        m = ServiceMeasure(service_id=s.id, period=period)
        db.session.add(m)
    m.availability = _float(request.form.get("availability"))
    m.incidents = request.form.get("incidents", type=int)
    m.sla_breaches = request.form.get("sla_breaches", type=int)
    m.comment = (request.form.get("comment") or "").strip() or None
    db.session.commit()
    flash(f"Mesure {period} enregistrée" + (" : objectif non atteint." if m.breached else "."), "warning" if m.breached else "success")
    return redirect(url_for("itsm.detail", sid=s.id))


@bp.route("/mesure/<int:mid>/supprimer", methods=["POST"])
@editor_required
@norm_required
def delete_measure(mid):
    m = db.session.get(ServiceMeasure, mid) or abort(404)
    sid = m.service_id
    db.session.delete(m)
    db.session.commit()
    flash("Mesure supprimée.", "success")
    return redirect(url_for("itsm.detail", sid=sid))


# --- Problèmes --------------------------------------------------------------
@bp.route("/problemes")
@login_required
@norm_required
def problems():
    f_open = request.args.get("ouverts", "1")
    items = Problem.query.order_by(Problem.opened_on.desc(), Problem.id.desc()).all()
    if f_open == "1":
        items = [p for p in items if not p.status.closed]
    return render_template("itsm/problems.html", items=items, f_open=f_open)


@bp.route("/problemes/nouveau", methods=["GET", "POST"])
@editor_required
@norm_required
def problem_create():
    return _problem_form(None)


@bp.route("/problemes/<int:pid>", methods=["GET", "POST"])
@editor_required
@norm_required
def problem_edit(pid):
    return _problem_form(db.session.get(Problem, pid) or abort(404))


def _problem_form(p):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé du problème est obligatoire.", "danger")
        else:
            if p is None:
                p = Problem(ref=next_ref(Problem, "PRB", width=4))
                db.session.add(p)
            p.title = title
            for f in ("description", "root_cause", "workaround", "resolution"):
                setattr(p, f, (request.form.get(f) or "").strip() or None)
            p.service_id = request.form.get("service_id", type=int) or None
            p.priority = Priority(request.form.get("priority", "P3"))
            p.status = ProblemStatus(request.form.get("status", "OUVERT"))
            p.change_id = request.form.get("change_id", type=int) or None
            p.owner_id = request.form.get("owner_id", type=int) or None
            p.opened_on = _date(request.form.get("opened_on")) or p.opened_on or date.today()
            p.resolved_on = (_date(request.form.get("resolved_on")) or p.resolved_on or date.today()) if p.status.closed else None
            ids = _ids("incident_ids")
            p.incidents = Incident.query.filter(Incident.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Problème {p.ref} enregistré.", "success")
            return redirect(url_for("itsm.problems"))
    return render_template("itsm/problem_form.html", p=p, users=_users(), Priority=Priority, ProblemStatus=ProblemStatus,
                           services=ItService.query.order_by(ItService.ref).all(),
                           incidents=Incident.query.order_by(Incident.id.desc()).limit(300).all(),
                           changes=ChangeRequest.query.order_by(ChangeRequest.id.desc()).limit(300).all())


# --- Mises en production ------------------------------------------------------
@bp.route("/mises-en-production")
@login_required
@norm_required
def releases():
    items = Release.query.order_by(Release.planned_on.desc().nullslast(), Release.id.desc()).all()
    return render_template("itsm/releases.html", items=items)


@bp.route("/mises-en-production/nouvelle", methods=["GET", "POST"])
@editor_required
@norm_required
def release_create():
    return _release_form(None)


@bp.route("/mises-en-production/<int:rid>", methods=["GET", "POST"])
@editor_required
@norm_required
def release_edit(rid):
    return _release_form(db.session.get(Release, rid) or abort(404))


def _release_form(r):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de la mise en production est obligatoire.", "danger")
        else:
            if r is None:
                r = Release(ref=next_ref(Release, "MEP", width=4))
                db.session.add(r)
            r.title = title
            for f in ("content", "tests", "rollback_plan", "result"):
                setattr(r, f, (request.form.get(f) or "").strip() or None)
            r.service_id = request.form.get("service_id", type=int) or None
            r.status = ReleaseStatus(request.form.get("status", "PLANIFIEE"))
            r.planned_on = _date(request.form.get("planned_on"))
            r.deployed_on = _date(request.form.get("deployed_on")) or (
                (r.deployed_on or date.today()) if r.status in (ReleaseStatus.DEPLOYEE, ReleaseStatus.RETOUR_ARRIERE) else None)
            r.owner_id = request.form.get("owner_id", type=int) or None
            ids = _ids("change_ids")
            r.changes = ChangeRequest.query.filter(ChangeRequest.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Mise en production {r.ref} enregistrée.", "success")
            return redirect(url_for("itsm.releases"))
    return render_template("itsm/release_form.html", r=r, users=_users(), ReleaseStatus=ReleaseStatus,
                           services=ItService.query.order_by(ItService.ref).all(),
                           changes=ChangeRequest.query.order_by(ChangeRequest.id.desc()).limit(300).all())
