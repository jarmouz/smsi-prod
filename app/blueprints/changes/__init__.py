"""Gestion des changements (6.3 modifications du SMSI, A.8.32 changements techniques) :
demande et analyse d'impact, approbation avec séparation des tâches, réalisation,
revue post-changement."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import ChangeRequest, Asset, ChangeKind, ChangeRisk, ChangeStatus, Role
from app.services import attachments as att_svc
from app.services.access import editor_required
from app.services.audit_trail import log_event
from app.services.refs import next_ref

bp = Blueprint("changes", __name__, url_prefix="/changements")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def can_approve(c):
    """RSSI ; pour un risque moyen ou élevé, jamais le demandeur (séparation des tâches)."""
    if not current_user.is_authenticated or current_user.is_readonly or current_user.role != Role.RSSI:
        return False
    return c.risk_level == ChangeRisk.FAIBLE or c.requested_by_id != current_user.id


def _can_review():
    return current_user.is_authenticated and not current_user.is_readonly and \
        current_user.role in (Role.RSSI, Role.AUDITEUR)


@bp.route("/")
@login_required
def index():
    f_status = request.args.get("statut")
    q = ChangeRequest.query
    if f_status in [s.value for s in ChangeStatus]:
        q = q.filter(ChangeRequest.status == ChangeStatus(f_status))
    elif f_status == "en_cours":
        q = q.filter(ChangeRequest.status.in_([ChangeStatus.DEMANDE, ChangeStatus.APPROUVE, ChangeStatus.REALISE]))
    changes = q.order_by(ChangeRequest.created_at.desc()).all()
    allc = ChangeRequest.query.all()
    stats = {s: sum(c.status == ChangeStatus(s) for c in allc) for s in ("DEMANDE", "APPROUVE", "REALISE")}
    stats["emergency"] = sum(c.emergency and c.status != ChangeStatus.CLOTURE for c in allc)
    return render_template("changes/index.html", changes=changes, stats=stats, f_status=f_status, ChangeStatus=ChangeStatus)


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:change_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(change_id):
    c = db.session.get(ChangeRequest, change_id) or abort(404)
    if c.status != ChangeStatus.DEMANDE:
        flash("Seule une demande non encore décidée est modifiable.", "warning")
        return redirect(url_for("changes.detail", change_id=c.id))
    return _form(c)


def _form(c):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        impact = (request.form.get("security_impact") or "").strip()
        if not title or not impact:
            flash("L'intitulé et l'analyse d'impact sur la sécurité sont obligatoires.", "danger")
        else:
            if c is None:
                c = ChangeRequest(ref=next_ref(ChangeRequest, "CHG", width=3), requested_by_id=current_user.id)
                db.session.add(c)
            c.title, c.security_impact = title, impact
            c.kind = ChangeKind(request.form.get("kind", "TECHNIQUE"))
            c.risk_level = ChangeRisk(request.form.get("risk_level", "FAIBLE"))
            c.description = request.form.get("description")
            c.reason = request.form.get("reason")
            c.rollback = request.form.get("rollback")
            c.emergency = bool(request.form.get("emergency"))
            c.planned_date = _date(request.form.get("planned_date"))
            ids = request.form.getlist("assets", type=int)
            c.assets = Asset.query.filter(Asset.id.in_(ids)).all() if ids else []
            if c.risk_level != ChangeRisk.FAIBLE and not (c.rollback or "").strip() and c.kind == ChangeKind.TECHNIQUE:
                flash("Un plan de retour arrière est requis pour un changement technique à risque moyen ou élevé.", "danger")
                db.session.rollback()
                return render_template("changes/form.html", c=c, assets=Asset.query.order_by(Asset.ref).all(),
                                       ChangeKind=ChangeKind, ChangeRisk=ChangeRisk)
            db.session.commit()
            flash(f"Demande de changement {c.ref} enregistrée.", "success")
            return redirect(url_for("changes.detail", change_id=c.id))
    return render_template("changes/form.html", c=c, assets=Asset.query.order_by(Asset.ref).all(),
                           ChangeKind=ChangeKind, ChangeRisk=ChangeRisk)


@bp.route("/<int:change_id>")
@login_required
def detail(change_id):
    c = db.session.get(ChangeRequest, change_id) or abort(404)
    return render_template("changes/detail.html", c=c, can_approve=can_approve(c), can_review=_can_review(),
                           attachments=att_svc.get_for("change", c.id))


@bp.route("/<int:change_id>/decision", methods=["POST"])
@login_required
def decide(change_id):
    c = db.session.get(ChangeRequest, change_id) or abort(404)
    if not can_approve(c):
        abort(403)
    if c.status != ChangeStatus.DEMANDE:
        flash("Décision déjà prise.", "warning")
        return redirect(url_for("changes.detail", change_id=c.id))
    approve = request.form.get("decision") == "approuver"
    note = (request.form.get("decision_note") or "").strip()
    if not approve and not note:
        flash("Motivez le refus.", "danger")
        return redirect(url_for("changes.detail", change_id=c.id))
    c.status = ChangeStatus.APPROUVE if approve else ChangeStatus.REFUSE
    c.approved_by_id, c.approved_at, c.decision_note = current_user.id, datetime.utcnow(), note or None
    db.session.commit()
    log_event("workflow", f"Changement {'approuvé' if approve else 'refusé'}" + (f" : {note}" if note else ""), entity=c)
    flash(f"{c.ref} {'approuvé' if approve else 'refusé'}.", "success")
    return redirect(url_for("changes.detail", change_id=c.id))


@bp.route("/<int:change_id>/realise", methods=["POST"])
@editor_required
def done(change_id):
    c = db.session.get(ChangeRequest, change_id) or abort(404)
    if c.status != ChangeStatus.APPROUVE:
        flash("Seul un changement approuvé peut être déclaré réalisé.", "warning")
    else:
        c.status, c.done_at = ChangeStatus.REALISE, datetime.utcnow()
        db.session.commit()
        log_event("workflow", "Changement réalisé", entity=c)
        flash(f"{c.ref} réalisé : la revue post-changement reste à faire.", "success")
    return redirect(url_for("changes.detail", change_id=c.id))


@bp.route("/<int:change_id>/revue", methods=["POST"])
@login_required
def review(change_id):
    c = db.session.get(ChangeRequest, change_id) or abort(404)
    if not _can_review():
        abort(403)
    note = (request.form.get("review_note") or "").strip()
    if c.status != ChangeStatus.REALISE:
        flash("La revue suit la réalisation du changement.", "warning")
    elif not note:
        flash("Décrivez le résultat de la revue post-changement.", "danger")
    else:
        c.status, c.review_note, c.reviewed_at = ChangeStatus.CLOTURE, note, datetime.utcnow()
        db.session.commit()
        log_event("workflow", f"Revue post-changement : {note}", entity=c)
        flash(f"{c.ref} clôturé.", "success")
    return redirect(url_for("changes.detail", change_id=c.id))


@bp.route("/<int:change_id>/annuler", methods=["POST"])
@editor_required
def cancel(change_id):
    c = db.session.get(ChangeRequest, change_id) or abort(404)
    if c.status not in (ChangeStatus.DEMANDE, ChangeStatus.APPROUVE):
        flash("Ce changement ne peut plus être annulé.", "warning")
    elif current_user.id != c.requested_by_id and current_user.role != Role.RSSI:
        abort(403)
    else:
        c.status = ChangeStatus.ANNULE
        db.session.commit()
        log_event("workflow", "Changement annulé", entity=c)
        flash(f"{c.ref} annulé.", "success")
    return redirect(url_for("changes.detail", change_id=c.id))
