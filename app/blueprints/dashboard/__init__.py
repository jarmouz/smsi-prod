"""Tableau de bord du système de management intégré (3.9).

Vue d'ensemble multi-normes : préparation à la certification par norme (mise en œuvre et
preuves), points à traiter tous modules confondus, risques (matrice, priorités, plan de
traitement), pilotage (indicateurs, objectifs, fournisseurs, exigences) et tâches de
l'utilisateur. Calculs : app/services/readiness.py et governance.summary().
"""
from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import ManagementReview, Incident, IncidentStatus, CorrectiveAction, ReviewAction, RiskAction

bp = Blueprint("dashboard", __name__)


@bp.route("/tableau-de-bord")
@login_required
def home():
    from app.services import governance, readiness, reminders
    pilot = governance.summary()
    cards = readiness.norm_cards()
    risk = readiness.risk_summary()
    attention = readiness.attention(pilot)

    # actions en retard, tous plans confondus (correctives, revue de direction, traitement des risques)
    late = {"correctives": sum(a.is_overdue for a in CorrectiveAction.query.all()),
            "revue": sum(a.is_overdue for a in ReviewAction.query.all()),
            "traitement": sum(a.is_overdue for a in RiskAction.query.all())}

    my_tasks = [(title, items) for title, items in reminders.collect(current_user) if items]
    next_review = (ManagementReview.query.filter(ManagementReview.review_date >= date.today())
                   .order_by(ManagementReview.review_date).first())
    return render_template(
        "dashboard/home.html", cards=cards, overall=readiness.overall(cards), risk=risk, attention=attention,
        pilot=pilot, late=late, late_total=sum(late.values()),
        open_incidents=Incident.query.filter(Incident.status != IncidentStatus.CLOTURE).count(),
        my_tasks=my_tasks, my_tasks_n=sum(len(i) for _, i in my_tasks), next_review=next_review,
    )
