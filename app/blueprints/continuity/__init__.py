"""Continuité d'activité (A.5.29, A.5.30) : analyse d'impact (BIA) des activités,
exercices et tests de continuité / reprise."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import BusinessProcess, ContinuityTest, Asset, Document, User, TestType, TestResult
from app.services import attachments as att_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("continuity", __name__, url_prefix="/continuite")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _hours(s):
    try:
        v = float(str(s).replace(",", ".").strip())
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def _users():
    return User.query.filter_by(is_active_flag=True).order_by(User.name).all()


@bp.route("/")
@login_required
def index():
    processes = sorted(BusinessProcess.query.all(), key=lambda p: (-p.criticality, p.ref))
    tests = ContinuityTest.query.order_by(ContinuityTest.test_date.desc().nullslast()).all()
    stats = {"critical": sum(p.criticality >= 3 for p in processes),
             "overdue": sum(p.test_overdue for p in processes),
             "rto_ko": sum(p.rto_ok is False for p in processes),
             "incoherent": sum(bool(p.rto_hours and p.mtpd_hours and p.rto_hours > p.mtpd_hours) for p in processes)}
    return render_template("continuity/index.html", processes=processes, tests=tests, stats=stats)


@bp.route("/activites/nouvelle", methods=["GET", "POST"])
@editor_required
def create_process():
    return _process_form(None)


@bp.route("/activites/<int:proc_id>", methods=["GET", "POST"])
@editor_required
def edit_process(proc_id):
    return _process_form(db.session.get(BusinessProcess, proc_id) or abort(404))


def _process_form(p):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom de l'activité est obligatoire.", "danger")
        else:
            if p is None:
                p = BusinessProcess(ref=next_ref(BusinessProcess, "PROC", width=3, yearly=False))
                db.session.add(p)
            p.name = name
            for f in ("description", "impacts", "dependencies", "strategy"):
                setattr(p, f, request.form.get(f))
            p.owner_id = request.form.get("owner_id", type=int) or None
            p.criticality = min(max(request.form.get("criticality", type=int) or 2, 1), 4)
            p.mtpd_hours = _hours(request.form.get("mtpd_hours"))
            p.rto_hours = _hours(request.form.get("rto_hours"))
            p.rpo_hours = _hours(request.form.get("rpo_hours"))
            p.plan_id = request.form.get("plan_id", type=int) or None
            ids = request.form.getlist("assets", type=int)
            p.assets = Asset.query.filter(Asset.id.in_(ids)).all() if ids else []
            db.session.commit()
            if p.rto_hours and p.mtpd_hours and p.rto_hours > p.mtpd_hours:
                flash(f"{p.ref} enregistrée, mais le RTO ({p.rto_hours:g} h) dépasse la durée maximale "
                      f"d'interruption admissible ({p.mtpd_hours:g} h) : stratégie à revoir.", "warning")
            else:
                flash(f"Activité {p.ref} enregistrée.", "success")
            return redirect(url_for("continuity.index"))
    return render_template("continuity/process_form.html", p=p, users=_users(),
                           assets=Asset.query.order_by(Asset.ref).all(),
                           documents=Document.query.order_by(Document.ref).all(), levels=BusinessProcess.CRITICALITY)


@bp.route("/exercices/nouveau", methods=["GET", "POST"])
@editor_required
def create_test():
    return _test_form(None)


@bp.route("/exercices/<int:test_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit_test(test_id):
    return _test_form(db.session.get(ContinuityTest, test_id) or abort(404))


@bp.route("/exercices/<int:test_id>")
@login_required
def test_detail(test_id):
    t = db.session.get(ContinuityTest, test_id) or abort(404)
    return render_template("continuity/test_detail.html", t=t, attachments=att_svc.get_for("continuity", t.id))


def _test_form(t):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de l'exercice est obligatoire.", "danger")
        else:
            if t is None:
                t = ContinuityTest(ref=next_ref(ContinuityTest, "EXE", width=2))
                db.session.add(t)
            t.title = title
            t.ttype = TestType(request.form.get("ttype", "TABLE_TOP"))
            t.test_date = _date(request.form.get("test_date"))
            t.objectives = request.form.get("objectives")
            t.result = TestResult(request.form.get("result", "PLANIFIE"))
            t.achieved_rto_hours = _hours(request.form.get("achieved_rto_hours"))
            t.findings = request.form.get("findings")
            t.owner_id = request.form.get("owner_id", type=int) or None
            ids = request.form.getlist("processes", type=int)
            t.processes = BusinessProcess.query.filter(BusinessProcess.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Exercice {t.ref} enregistré.", "success")
            return redirect(url_for("continuity.test_detail", test_id=t.id))
    return render_template("continuity/test_form.html", t=t, users=_users(),
                           processes=BusinessProcess.query.order_by(BusinessProcess.ref).all(),
                           TestType=TestType, TestResult=TestResult)
