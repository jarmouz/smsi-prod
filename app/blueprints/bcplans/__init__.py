"""Plans de continuité, de reprise et de gestion de crise (ISO 22301 8.4).
Accessible quand l'organisation a activé l'ISO 22301."""
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import User, Document, BusinessProcess, ContinuityTest
from app.models.service_mgmt import ContinuityPlan, PlanType, PlanStatus
from app.services import attachments as att_svc
from app.services import frameworks as fw_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("bcplans", __name__, url_prefix="/continuite/plans")
CODE = "ISO22301"


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def norm_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not fw_svc.is_enabled(CODE):
            abort(404)
        return fn(*a, **k)
    return w


@bp.route("/")
@login_required
@norm_required
def index():
    order = {"VALIDE": 0, "BROUILLON": 1, "OBSOLETE": 2}
    plans = sorted(ContinuityPlan.query.all(), key=lambda p: (order[p.status.value], p.ref))
    live = [p for p in plans if p.status != PlanStatus.OBSOLETE]
    covered = {pr.id for p in live for pr in p.processes}
    critical = [pr for pr in BusinessProcess.query.all() if pr.criticality >= 3]
    stats = {"plans": len(live), "valid": sum(p.status == PlanStatus.VALIDE for p in live),
             "uncovered": [pr for pr in critical if pr.id not in covered],
             "not_exercised": sum("jamais exercé" in p.gaps or any("exercice" in g for g in p.gaps) for p in live)}
    return render_template("bcplans/index.html", plans=plans, stats=stats)


@bp.route("/<int:pid>")
@login_required
@norm_required
def detail(pid):
    p = db.session.get(ContinuityPlan, pid) or abort(404)
    return render_template("bcplans/detail.html", p=p, attachments=att_svc.get_for("bcplan", p.id))


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
@norm_required
def create():
    return _form(None)


@bp.route("/<int:pid>/modifier", methods=["GET", "POST"])
@editor_required
@norm_required
def edit(pid):
    return _form(db.session.get(ContinuityPlan, pid) or abort(404))


def _form(p):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre du plan est obligatoire.", "danger")
        else:
            if p is None:
                p = ContinuityPlan(ref=next_ref(ContinuityPlan, "PLAN", width=3, yearly=False))
                db.session.add(p)
            p.title = title
            for f in ("scope", "activation", "response_team", "alerting", "procedures", "resources", "notes"):
                setattr(p, f, (request.form.get(f) or "").strip() or None)
            p.version = (request.form.get("version") or "").strip()[:16] or None
            p.plan_type = PlanType(request.form.get("plan_type", "PCA"))
            p.status = PlanStatus(request.form.get("status", "BROUILLON"))
            p.document_id = request.form.get("document_id", type=int) or None
            p.owner_id = request.form.get("owner_id", type=int) or None
            p.last_review = _date(request.form.get("last_review"))
            p.next_review = _date(request.form.get("next_review")) or (p.default_next(p.last_review) if p.last_review else None)
            ids = [int(x) for x in request.form.getlist("process_ids") if x.isdigit()]
            p.processes = BusinessProcess.query.filter(BusinessProcess.id.in_(ids)).all() if ids else []
            ids = [int(x) for x in request.form.getlist("test_ids") if x.isdigit()]
            p.tests = ContinuityTest.query.filter(ContinuityTest.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Plan {p.ref} enregistré.", "success")
            return redirect(url_for("bcplans.detail", pid=p.id))
    return render_template("bcplans/form.html", p=p, PlanType=PlanType, PlanStatus=PlanStatus,
                           users=User.query.filter_by(is_active_flag=True).order_by(User.name).all(),
                           processes=BusinessProcess.query.order_by(BusinessProcess.ref).all(),
                           tests=ContinuityTest.query.order_by(ContinuityTest.test_date.desc().nullslast()).all(),
                           documents=Document.query.order_by(Document.ref).all())
