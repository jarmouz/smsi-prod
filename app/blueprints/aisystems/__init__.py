"""Intelligence artificielle (ISO/IEC 42001) : inventaire des systèmes d'IA et études d'impact.
Accessible quand l'organisation a activé l'ISO 42001."""
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import User, Asset, Supplier
from app.models.ai_system import (AiSystem, AiImpactAssessment, AiRole, AiType, AiRiskLevel, AiLifecycle,
                                  ImpactLevel, ImpactDecision)
from app.services import attachments as att_svc
from app.services import frameworks as fw_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("aisystems", __name__, url_prefix="/systemes-ia")
CODE = "ISO42001"


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


def _users():
    return User.query.filter_by(is_active_flag=True).order_by(User.name).all()


def _processings():
    if not fw_svc.is_enabled("ISO27701"):
        return []
    from app.models.privacy import ProcessingActivity
    return ProcessingActivity.query.order_by(ProcessingActivity.ref).all()


@bp.route("/")
@login_required
@norm_required
def index():
    f_risk = request.args.get("risque")
    f_gap = request.args.get("ecarts")
    q = AiSystem.query
    if f_risk in [x.value for x in AiRiskLevel]:
        q = q.filter(AiSystem.risk_level == AiRiskLevel(f_risk))
    order = {"INACCEPTABLE": 0, "ELEVE": 1, "LIMITE": 2, "FAIBLE": 3}
    items = sorted(q.all(), key=lambda s: (s.lifecycle == AiLifecycle.RETIRE, order[s.risk_level.value], s.ref))
    if f_gap:
        items = [s for s in items if s.gaps]
    live = [s for s in AiSystem.query.all() if s.lifecycle != AiLifecycle.RETIRE]
    stats = {"live": len(live), "prod": sum(s.lifecycle == AiLifecycle.PRODUCTION for s in live),
             "high": sum(s.risk_level in (AiRiskLevel.ELEVE, AiRiskLevel.INACCEPTABLE) for s in live),
             "todo": sum(any("étude d'impact" in g for g in s.gaps) for s in live)}
    return render_template("aisystems/index.html", items=items, stats=stats, f_risk=f_risk, f_gap=f_gap,
                           AiRiskLevel=AiRiskLevel)


@bp.route("/<int:sid>")
@login_required
@norm_required
def detail(sid):
    s = db.session.get(AiSystem, sid) or abort(404)
    return render_template("aisystems/detail.html", s=s, attachments=att_svc.get_for("aisystem", s.id),
                           privacy_on=fw_svc.is_enabled("ISO27701"))


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
@norm_required
def create():
    return _form(None)


@bp.route("/<int:sid>/modifier", methods=["GET", "POST"])
@editor_required
@norm_required
def edit(sid):
    return _form(db.session.get(AiSystem, sid) or abort(404))


def _form(s):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom du système d'IA est obligatoire.", "danger")
        else:
            if s is None:
                s = AiSystem(ref=next_ref(AiSystem, "IA", width=3, yearly=False))
                db.session.add(s)
            s.name = name
            for f in ("description", "intended_use", "provider", "data_used", "affected_parties", "human_oversight",
                      "notes"):
                setattr(s, f, (request.form.get(f) or "").strip() or None)
            s.role = AiRole(request.form.get("role", "DEPLOYEUR"))
            s.ai_type = AiType(request.form.get("ai_type", "GENERATIVE"))
            s.risk_level = AiRiskLevel(request.form.get("risk_level", "LIMITE"))
            s.lifecycle = AiLifecycle(request.form.get("lifecycle", "PRODUCTION"))
            s.personal_data = bool(request.form.get("personal_data"))
            s.automated_decisions = bool(request.form.get("automated_decisions"))
            s.supplier_id = request.form.get("supplier_id", type=int) or None
            s.processing_id = (request.form.get("processing_id", type=int) or None) if s.personal_data else None
            s.owner_id = request.form.get("owner_id", type=int) or None
            ids = [int(x) for x in request.form.getlist("asset_ids") if x.isdigit()]
            s.assets = Asset.query.filter(Asset.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Système d'IA {s.ref} enregistré.", "success")
            return redirect(url_for("aisystems.detail", sid=s.id))
    return render_template("aisystems/form.html", s=s, users=_users(), AiRole=AiRole, AiType=AiType,
                           AiRiskLevel=AiRiskLevel, AiLifecycle=AiLifecycle,
                           suppliers=Supplier.query.order_by(Supplier.name).all(),
                           assets=Asset.query.order_by(Asset.name).all(), processings=_processings())


@bp.route("/<int:sid>/etude-impact/nouvelle", methods=["GET", "POST"])
@editor_required
@norm_required
def assessment_create(sid):
    s = db.session.get(AiSystem, sid) or abort(404)
    return _assessment_form(s, None)


@bp.route("/etude-impact/<int:aid>", methods=["GET", "POST"])
@editor_required
@norm_required
def assessment_edit(aid):
    a = db.session.get(AiImpactAssessment, aid) or abort(404)
    return _assessment_form(a.system, a)


def _assessment_form(s, a):
    if request.method == "POST":
        if a is None:
            a = AiImpactAssessment(ref=next_ref(AiImpactAssessment, "EIA", width=4), ai_system_id=s.id)
            db.session.add(a)
        a.assessed_on = _date(request.form.get("assessed_on")) or datetime.utcnow().date()
        a.assessor_id = request.form.get("assessor_id", type=int) or None
        for f in ("impacts_individuals", "impacts_society", "measures", "residual", "notes"):
            setattr(a, f, (request.form.get(f) or "").strip() or None)
        a.impact_level = ImpactLevel(request.form.get("impact_level", "MOYEN"))
        a.decision = ImpactDecision(request.form.get("decision", "EN_COURS"))
        a.next_review = _date(request.form.get("next_review")) or a.default_next(a.assessed_on)
        db.session.commit()
        flash(f"Étude d'impact {a.ref} enregistrée. Prochaine revue : {a.next_review:%d/%m/%Y}.", "success")
        return redirect(url_for("aisystems.detail", sid=s.id))
    return render_template("aisystems/assessment_form.html", s=s, a=a, users=_users(), ImpactLevel=ImpactLevel,
                           ImpactDecision=ImpactDecision)
