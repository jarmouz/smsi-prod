"""Non-conformités et actions correctives (10.2), quelle que soit leur origine :
audit, incident, réclamation, revue de direction, indicateur hors cible..."""
from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (NonConformity, CorrectiveAction, Control, User, Finding, Incident, Indicator, ContinuityTest,
                        NcSource, NcSeverity, NcStatus, ActionStatus, FindingType, Role)
from app.services.access import editor_required
from app.services.audit_trail import log_event
from app.services.refs import next_ref

bp = Blueprint("nonconformities", __name__, url_prefix="/non-conformites")

CAUSE_METHODS = ["5 pourquoi", "Ishikawa (5M)", "Arbre des causes", "Analyse de processus", "Autre"]


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _can_verify():
    """Vérification d'efficacité : RSSI ou auditeur (regard indépendant)."""
    return current_user.is_authenticated and not current_user.is_readonly and \
        current_user.role in (Role.RSSI, Role.AUDITEUR)


def _refresh_status(nc):
    """Fait progresser le statut selon l'avancement (jamais la clôture : elle exige la vérification)."""
    if nc.status == NcStatus.CLOTUREE:
        return
    if nc.actions and nc.actions_done and nc.root_cause:
        nc.status = NcStatus.A_VERIFIER
    elif nc.root_cause or nc.actions or nc.correction:
        nc.status = NcStatus.EN_TRAITEMENT
    else:
        nc.status = NcStatus.OUVERTE


@bp.route("/")
@login_required
def index():
    f_status = request.args.get("statut")
    f_source = request.args.get("source")
    q = NonConformity.query
    if f_status in [s.value for s in NcStatus]:
        q = q.filter(NonConformity.status == NcStatus(f_status))
    elif f_status == "ouvertes":
        q = q.filter(NonConformity.status != NcStatus.CLOTUREE)
    if f_source in [s.value for s in NcSource]:
        q = q.filter(NonConformity.source == NcSource(f_source))
    ncs = q.order_by(NonConformity.created_at.desc()).all()
    all_ncs = NonConformity.query.all()
    stats = {"open": sum(n.status != NcStatus.CLOTUREE for n in all_ncs),
             "major": sum(n.status != NcStatus.CLOTUREE and n.severity == NcSeverity.MAJEURE for n in all_ncs),
             "verify": sum(n.status == NcStatus.A_VERIFIER for n in all_ncs),
             "overdue": sum(n.status != NcStatus.CLOTUREE and n.is_overdue for n in all_ncs),
             "closed": sum(n.status == NcStatus.CLOTUREE for n in all_ncs)}
    return render_template("nonconformities/index.html", ncs=ncs, stats=stats, f_status=f_status, f_source=f_source,
                           NcStatus=NcStatus, NcSource=NcSource)


@bp.route("/nouvelle", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:nc_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(nc_id):
    nc = db.session.get(NonConformity, nc_id) or abort(404)
    if nc.status == NcStatus.CLOTUREE:
        flash("Non-conformité clôturée : elle n'est plus modifiable.", "warning")
        return redirect(url_for("nonconformities.detail", nc_id=nc.id))
    return _form(nc)


def _prefill():
    """Pré-remplissage depuis un constat d'audit, un incident ou un indicateur hors cible."""
    nc = NonConformity(source=NcSource.AUTRE, severity=NcSeverity.MINEURE, detected_at=date.today())
    if (fid := request.args.get("finding", type=int)) and (f := db.session.get(Finding, fid)):
        nc.finding_id, nc.source = f.id, NcSource.AUDIT_INTERNE
        nc.severity = NcSeverity.MAJEURE if f.type == FindingType.NC_MAJEURE else NcSeverity.MINEURE
        nc.title, nc.description = f.title, f.description
        nc.control_id, nc.clause = f.control_id, f.clause
        nc.detected_by = f"Audit {f.audit.ref}" + (f" ({f.audit.lead_auditor.name})" if f.audit.lead_auditor else "")
        nc.detected_at = f.audit.planned_date or date.today()
    elif (iid := request.args.get("incident", type=int)) and (i := db.session.get(Incident, iid)):
        nc.incident_id, nc.source = i.id, NcSource.INCIDENT
        nc.title = f"Écart révélé par l'incident {i.ref} : {i.title}"[:300]
        nc.description, nc.control_id, nc.detected_at = i.impact or i.description, i.control_id, i.detected_at
        nc.correction = i.resolution
    elif (kid := request.args.get("indicateur", type=int)) and (k := db.session.get(Indicator, kid)):
        nc.source = NcSource.SURVEILLANCE
        nc.title = f"Indicateur {k.ref} hors cible : {k.name}"[:300]
        nc.description = (f"Dernière mesure {k.fmt(k.last.value)} pour une cible de {k.fmt(k.target)}"
                          f" ({k.last.period:%d/%m/%Y})." if k.last else "")
        nc.control_id = k.control_id
    elif (tid := request.args.get("exercice", type=int)) and (t := db.session.get(ContinuityTest, tid)):
        nc.source = NcSource.CONTROLE
        nc.title = f"Exercice {t.ref} {t.result.label.lower()} : {t.title}"[:300]
        nc.description, nc.detected_at = t.findings, t.test_date or date.today()
        nc.control_id = (Control.query.filter_by(ref="5.30").first() or Control()).id
    return nc


def _form(nc):
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    controls = Control.query.order_by(Control.id).all()
    draft = nc or _prefill()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de la non-conformité est obligatoire.", "danger")
        else:
            creating = nc is None
            if creating:
                nc = NonConformity(ref=next_ref(NonConformity, "NC", width=3))
                nc.finding_id = request.form.get("finding_id", type=int) or None
                nc.incident_id = request.form.get("incident_id", type=int) or None
                db.session.add(nc)
            nc.title = title
            nc.description = request.form.get("description")
            nc.source = NcSource(request.form.get("source", "AUTRE"))
            nc.severity = NcSeverity(request.form.get("severity", "MINEURE"))
            nc.detected_at = _date(request.form.get("detected_at"))
            nc.detected_by = request.form.get("detected_by")
            nc.clause = (request.form.get("clause") or "").strip() or None
            nc.control_id = request.form.get("control_id", type=int) or None
            nc.owner_id = request.form.get("owner_id", type=int) or None
            nc.correction = request.form.get("correction")
            nc.cause_method = request.form.get("cause_method") or None
            nc.root_cause = request.form.get("root_cause")
            nc.extent = request.form.get("extent")
            nc.isms_changes = request.form.get("isms_changes")
            nc.effectiveness_due = _date(request.form.get("effectiveness_due"))
            db.session.flush()
            _refresh_status(nc)
            db.session.commit()
            flash(f"Non-conformité {nc.ref} enregistrée.", "success")
            return redirect(url_for("nonconformities.detail", nc_id=nc.id))
    return render_template("nonconformities/form.html", nc=nc, draft=draft, users=users, controls=controls,
                           NcSource=NcSource, NcSeverity=NcSeverity, methods=CAUSE_METHODS)


@bp.route("/<int:nc_id>")
@login_required
def detail(nc_id):
    nc = db.session.get(NonConformity, nc_id) or abort(404)
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    return render_template("nonconformities/detail.html", nc=nc, users=users, ActionStatus=ActionStatus,
                           can_verify=_can_verify())


@bp.route("/<int:nc_id>/action", methods=["POST"])
@editor_required
def add_action(nc_id):
    nc = db.session.get(NonConformity, nc_id) or abort(404)
    desc = (request.form.get("description") or "").strip()
    if nc.status == NcStatus.CLOTUREE:
        flash("Non-conformité clôturée.", "warning")
    elif desc:
        db.session.add(CorrectiveAction(nonconformity_id=nc.id, description=desc,
                                        owner_id=request.form.get("owner_id", type=int) or None,
                                        due_date=_date(request.form.get("due_date"))))
        db.session.flush()
        db.session.refresh(nc)
        _refresh_status(nc)
        db.session.commit()
        flash("Action corrective ajoutée.", "success")
    return redirect(url_for("nonconformities.detail", nc_id=nc.id))


@bp.route("/action/<int:action_id>/statut", methods=["POST"])
@editor_required
def action_status(action_id):
    ac = db.session.get(CorrectiveAction, action_id) or abort(404)
    if ac.nonconformity is None:
        abort(404)
    try:
        ac.status = ActionStatus(request.form.get("status"))
    except ValueError:
        abort(400)
    ac.completed_at = datetime.utcnow() if ac.status in (ActionStatus.REALISEE, ActionStatus.VERIFIEE) else None
    db.session.flush()
    _refresh_status(ac.nonconformity)
    db.session.commit()
    return redirect(url_for("nonconformities.detail", nc_id=ac.nonconformity_id))


@bp.route("/<int:nc_id>/efficacite", methods=["POST"])
@login_required
def verify(nc_id):
    """10.2 d) : revue de l'efficacité des actions correctives."""
    nc = db.session.get(NonConformity, nc_id) or abort(404)
    if not _can_verify():
        abort(403)
    note = (request.form.get("effectiveness_note") or "").strip()
    effective = request.form.get("effective") == "oui"
    if nc.status != NcStatus.A_VERIFIER:
        flash("La vérification se fait une fois les causes analysées et les actions réalisées.", "warning")
    elif not note:
        flash("Décrivez les éléments qui démontrent (ou non) l'efficacité.", "danger")
    elif effective:
        nc.effectiveness_at = nc.closed_at = datetime.utcnow()
        nc.effectiveness_by_id = current_user.id
        nc.effectiveness_note = note
        nc.status = NcStatus.CLOTUREE
        for a in nc.actions:
            if a.status == ActionStatus.REALISEE:
                a.status = ActionStatus.VERIFIEE
        db.session.commit()
        log_event("workflow", f"Efficacité vérifiée : non-conformité clôturée. {note}", entity=nc)
        flash(f"{nc.ref} clôturée : actions jugées efficaces.", "success")
    else:
        nc.status = NcStatus.EN_TRAITEMENT
        db.session.commit()
        log_event("workflow", f"Actions jugées non efficaces : nouvelle analyse requise. {note}", entity=nc)
        flash("Actions jugées non efficaces : complétez l'analyse et ajoutez des actions.", "warning")
    return redirect(url_for("nonconformities.detail", nc_id=nc.id))
