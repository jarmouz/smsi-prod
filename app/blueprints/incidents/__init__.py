from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import (Incident, Control, User,
                        IncidentCategory, IncidentSeverity, IncidentStatus)
from app.services.access import editor_required
from app.services.refs import next_ref
from app.services import attachments as att_svc

bp = Blueprint("incidents", __name__, url_prefix="/incidents")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
@login_required
def index():
    f_status = request.args.get("statut")
    f_sev = request.args.get("gravite")
    q = Incident.query
    if f_status in [x.value for x in IncidentStatus]:
        q = q.filter(Incident.status == IncidentStatus(f_status))
    if f_sev in [x.value for x in IncidentSeverity]:
        q = q.filter(Incident.severity == IncidentSeverity(f_sev))
    incidents = q.order_by(Incident.created_at.desc()).all()
    stats = {"ouverts": Incident.query.filter(Incident.status != IncidentStatus.CLOTURE).count(),
             "critiques": Incident.query.filter(Incident.severity == IncidentSeverity.CRITIQUE,
                                                 Incident.status != IncidentStatus.CLOTURE).count(),
             "total": Incident.query.count()}
    return render_template("incidents/index.html", incidents=incidents, stats=stats,
                           f_status=f_status, f_sev=f_sev,
                           IncidentStatus=IncidentStatus, IncidentSeverity=IncidentSeverity)


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    controls = Control.query.order_by(Control.theme, Control.id).all()
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre de l'incident est obligatoire.", "danger")
        else:
            inc = Incident(
                ref=next_ref(Incident, "INC"), title=title,
                description=request.form.get("description"),
                category=IncidentCategory(request.form.get("category", "AUTRE")),
                severity=IncidentSeverity(request.form.get("severity", "MINEUR")),
                status=IncidentStatus(request.form.get("status", "NOUVEAU")),
                detected_at=_date(request.form.get("detected_at")),
                reporter=request.form.get("reporter"),
                assignee_id=request.form.get("assignee_id", type=int) or None,
                control_id=request.form.get("control_id", type=int) or None,
                impact=request.form.get("impact"))
            db.session.add(inc)
            db.session.commit()
            att_svc.save_many(request.files.getlist("attachments"), "incident", inc.id, None)
            flash(f"Incident {inc.ref} enregistré.", "success")
            return redirect(url_for("incidents.detail", incident_id=inc.id))
    return render_template("incidents/form.html", inc=None, controls=controls, users=users,
                           IncidentCategory=IncidentCategory, IncidentSeverity=IncidentSeverity,
                           IncidentStatus=IncidentStatus)


@bp.route("/<int:incident_id>")
@login_required
def detail(incident_id):
    inc = db.session.get(Incident, incident_id) or abort(404)
    return render_template("incidents/detail.html", inc=inc,
                           attachments=att_svc.get_for("incident", inc.id),
                           IncidentStatus=IncidentStatus)


@bp.route("/<int:incident_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(incident_id):
    inc = db.session.get(Incident, incident_id) or abort(404)
    controls = Control.query.order_by(Control.theme, Control.id).all()
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        inc.title = (request.form.get("title") or inc.title).strip()
        inc.description = request.form.get("description")
        inc.category = IncidentCategory(request.form.get("category", inc.category.value))
        inc.severity = IncidentSeverity(request.form.get("severity", inc.severity.value))
        new_status = IncidentStatus(request.form.get("status", inc.status.value))
        if new_status == IncidentStatus.CLOTURE and inc.status != IncidentStatus.CLOTURE:
            inc.closed_at = datetime.utcnow()
        inc.status = new_status
        inc.detected_at = _date(request.form.get("detected_at"))
        inc.reporter = request.form.get("reporter")
        inc.assignee_id = request.form.get("assignee_id", type=int) or None
        inc.control_id = request.form.get("control_id", type=int) or None
        inc.impact = request.form.get("impact")
        inc.resolution = request.form.get("resolution")
        db.session.commit()
        flash(f"Incident {inc.ref} mis à jour.", "success")
        return redirect(url_for("incidents.detail", incident_id=inc.id))
    return render_template("incidents/form.html", inc=inc, controls=controls, users=users,
                           IncidentCategory=IncidentCategory, IncidentSeverity=IncidentSeverity,
                           IncidentStatus=IncidentStatus)
