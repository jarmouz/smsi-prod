from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required

from app.services import risk_criteria
from app.models import (
    Control, Risk, Audit, Finding, CorrectiveAction, Document, Evidence,
    ManagementReview, Incident, ControlStatus, RiskStatus, FindingType, ActionStatus,
    IncidentStatus,
)

bp = Blueprint("dashboard", __name__)


@bp.route("/tableau-de-bord")
@login_required
def home():
    controls = Control.of().all()
    applicable = [c for c in controls if c.applicable]
    implemented = [c for c in applicable if c.status == ControlStatus.IMPLEMENTE]
    soa_rate = round(100 * len(implemented) / len(applicable)) if applicable else 0

    risks = Risk.query.all()
    # les opportunités (ISO 6.1) ont leur propre lecture : ni dans la matrice ni dans les risques élevés
    open_risks = [r for r in risks if r.status.is_open and not r.is_opportunity]
    high_risks = sorted((r for r in risks if r.is_high), key=lambda r: -r.effective_score)
    open_opps_n = sum(1 for r in risks if r.status.is_open and r.is_opportunity)

    actions = CorrectiveAction.query.all()
    open_actions = [a for a in actions if a.status.is_open]
    overdue_actions = [a for a in actions if a.is_overdue]

    open_ncs = Finding.query.filter(
        Finding.type.in_([FindingType.NC_MAJEURE, FindingType.NC_MINEURE]),
        Finding.closed.is_(False),
    ).count()

    docs = Document.query.all()
    docs_to_review = [d for d in docs if d.review_overdue or d.review_soon]

    # Couverture DdA par thème
    theme_rows = []
    from app.models import Theme
    for th in Theme:
        cs = [c for c in controls if c.theme == th and c.applicable]
        impl = [c for c in cs if c.status == ControlStatus.IMPLEMENTE]
        theme_rows.append({
            "theme": th, "total": len(cs), "impl": len(impl),
            "rate": round(100 * len(impl) / len(cs)) if cs else 0,
        })

    # Matrice des risques (échelles de l'organisation) sur le risque résiduel effectif
    n_l, n_i = risk_criteria.scale("likelihood"), risk_criteria.scale("impact")
    matrix = {(l, i): [] for l in range(1, n_l + 1) for i in range(1, n_i + 1)}
    for r in open_risks:
        l = r.residual_likelihood or r.likelihood
        i = r.residual_impact or r.impact
        if 1 <= l <= n_l and 1 <= i <= n_i:
            matrix[(l, i)].append(r)

    open_incidents = Incident.query.filter(Incident.status != IncidentStatus.CLOTURE).count()

    from app.services import governance
    pilot = governance.summary()
    open_ncs = pilot["nc_open"]

    next_review = (ManagementReview.query
                   .filter(ManagementReview.review_date >= date.today())
                   .order_by(ManagementReview.review_date).first())

    return render_template(
        "dashboard/home.html",
        soa_rate=soa_rate, applicable_n=len(applicable), implemented_n=len(implemented),
        controls_total=len(controls),
        open_risks_n=len(open_risks), high_risks_n=len(high_risks), open_opps_n=open_opps_n,
        open_ncs=open_ncs, open_actions_n=len(open_actions), overdue_actions_n=len(overdue_actions),
        docs_to_review=docs_to_review, evidence_n=Evidence.query.count(),
        theme_rows=theme_rows, matrix=matrix, n_l=n_l, n_i=n_i, high_risks=high_risks[:6],
        next_review=next_review, open_incidents=open_incidents, pilot=pilot,
    )
