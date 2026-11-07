from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Audit, Finding, CorrectiveAction, Control, User,
    AuditStatus, FindingType, ActionStatus,
)
from app.services.access import auditor_required, editor_required
from app.services.refs import next_ref
from app.services import attachments as att_svc

bp = Blueprint("audits", __name__, url_prefix="/audits")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.route("/")
@login_required
def index():
    audits = Audit.query.order_by(Audit.created_at.desc()).all()
    # Actions correctives ouvertes (vue transversale)
    open_actions = (CorrectiveAction.query
                    .filter(CorrectiveAction.status != ActionStatus.VERIFIEE,
                            CorrectiveAction.finding_id.isnot(None))   # celles des NC : module Non-conformités
                    .all())
    open_actions.sort(key=lambda a: (a.due_date or datetime.max.date()))
    return render_template("audits/index.html", audits=audits, open_actions=open_actions)


@bp.route("/nouveau", methods=["GET", "POST"])
@auditor_required
def create():
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre de l'audit est obligatoire.", "danger")
        else:
            a = Audit(ref=next_ref(Audit, "AUD", width=2),
                      title=title, scope=request.form.get("scope"),
                      planned_date=_date(request.form.get("planned_date")),
                      status=AuditStatus(request.form.get("status", "PLANIFIE")),
                      lead_auditor_id=request.form.get("lead_auditor_id", type=int) or None)
            db.session.add(a)
            db.session.commit()
            att_svc.save_many(request.files.getlist("attachments"), "audit", a.id, current_user)
            flash(f"Audit {a.ref} créé.", "success")
            return redirect(url_for("audits.detail", audit_id=a.id))
    return render_template("audits/form.html", users=users, AuditStatus=AuditStatus)


@bp.route("/<int:audit_id>")
@login_required
def detail(audit_id):
    a = db.session.get(Audit, audit_id) or abort(404)
    controls = Control.of().order_by(Control.theme, Control.id).all()
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    attachments = att_svc.get_for("audit", a.id)
    from app.models import NonConformity
    ncs = {nc.finding_id: nc for nc in NonConformity.query.filter(
        NonConformity.finding_id.in_([f.id for f in a.findings] or [0]))}
    return render_template("audits/detail.html", a=a, controls=controls, users=users,
                           attachments=attachments, ncs=ncs,
                           FindingType=FindingType, ActionStatus=ActionStatus)


@bp.route("/<int:audit_id>/statut", methods=["POST"])
@auditor_required
def set_status(audit_id):
    a = db.session.get(Audit, audit_id) or abort(404)
    try:
        a.status = AuditStatus(request.form.get("status"))
        a.summary = request.form.get("summary", a.summary)
        db.session.commit()
        flash("Audit mis à jour.", "success")
    except ValueError:
        flash("Statut invalide.", "danger")
    return redirect(url_for("audits.detail", audit_id=a.id))


@bp.route("/<int:audit_id>/constat", methods=["POST"])
@auditor_required
def add_finding(audit_id):
    a = db.session.get(Audit, audit_id) or abort(404)
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Le libellé du constat est obligatoire.", "danger")
        return redirect(url_for("audits.detail", audit_id=a.id))
    ref = f"C-{len(a.findings) + 1:02d}"
    f = Finding(audit_id=a.id, ref=ref,
                type=FindingType(request.form.get("type", "OBSERVATION")),
                title=title, description=request.form.get("description"),
                control_id=request.form.get("control_id", type=int) or None,
                clause=(request.form.get("clause") or "").strip() or None)
    db.session.add(f)
    db.session.commit()
    flash(f"Constat {ref} ajouté.", "success")
    return redirect(url_for("audits.detail", audit_id=a.id))


@bp.route("/constat/<int:finding_id>/cloturer", methods=["POST"])
@auditor_required
def close_finding(finding_id):
    f = db.session.get(Finding, finding_id) or abort(404)
    f.closed = not f.closed
    db.session.commit()
    flash(f"Constat {f.ref} : {'clôturé' if f.closed else 'rouvert'}.", "success")
    return redirect(url_for("audits.detail", audit_id=f.audit_id))


@bp.route("/constat/<int:finding_id>/action", methods=["POST"])
@editor_required
def add_action(finding_id):
    f = db.session.get(Finding, finding_id) or abort(404)
    desc = (request.form.get("description") or "").strip()
    if desc:
        db.session.add(CorrectiveAction(
            finding_id=f.id, description=desc,
            owner_id=request.form.get("owner_id", type=int) or None,
            due_date=_date(request.form.get("due_date")),
            status=ActionStatus.OUVERTE))
        db.session.commit()
        flash("Action corrective ajoutée.", "success")
    return redirect(url_for("audits.detail", audit_id=f.audit_id))


@bp.route("/action/<int:action_id>/statut", methods=["POST"])
@editor_required
def action_status(action_id):
    ac = db.session.get(CorrectiveAction, action_id) or abort(404)
    try:
        ac.status = ActionStatus(request.form.get("status"))
        if ac.status == ActionStatus.VERIFIEE and not ac.completed_at:
            ac.completed_at = datetime.utcnow()
        db.session.commit()
        flash("Action mise à jour.", "success")
    except ValueError:
        flash("Statut invalide.", "danger")
    return redirect(url_for("audits.detail", audit_id=ac.finding.audit_id))


# --- Programme d'audit pluriannuel (9.2.2) -----------------------------------
THEME_OF_DOMAIN = {"A5": "ORGANISATIONNELLE", "A6": "HUMAINE", "A7": "PHYSIQUE", "A8": "TECHNOLOGIQUE"}
CYCLE_YEARS = 3


def _programme_years():
    y = datetime.utcnow().year
    return list(range(y - 1, y + CYCLE_YEARS))


@bp.route("/programme")
@login_required
def programme():
    from app.models import AuditPlanItem, AUDIT_DOMAINS, Theme
    years = _programme_years()
    items = {(i.year, i.domain): i for i in AuditPlanItem.query.filter(AuditPlanItem.year.in_(years))}
    y = datetime.utcnow().year
    window = range(y - 1, y + CYCLE_YEARS - 1)          # cycle de certification de 3 ans
    uncovered = [label for code, label in AUDIT_DOMAINS if not any((yy, code) in items for yy in window)]
    # Indépendance : un auditeur ne doit pas auditer les mesures dont il est responsable
    conflicts = {}
    for (yy, code), it in items.items():
        theme = THEME_OF_DOMAIN.get(code)
        if it.auditor_id and theme:
            n = Control.of().filter(Control.theme == Theme(theme), Control.owner_id == it.auditor_id).count()
            if n:
                conflicts[(yy, code)] = n
    return render_template("audits/programme.html", years=years, domains=AUDIT_DOMAINS, items=items,
                           uncovered=uncovered, conflicts=conflicts, window=window,
                           audits=Audit.query.order_by(Audit.ref.desc()).all(),
                           auditors=User.query.filter_by(is_active_flag=True).order_by(User.name).all())


@bp.route("/programme/case", methods=["POST"])
@auditor_required
def programme_set():
    from app.models import AuditPlanItem, AUDIT_DOMAINS
    year = request.form.get("year", type=int)
    domain = request.form.get("domain")
    if year not in _programme_years() or domain not in dict(AUDIT_DOMAINS):
        abort(400)
    it = AuditPlanItem.query.filter_by(year=year, domain=domain).first()
    if request.form.get("clear"):
        if it:
            db.session.delete(it)
            db.session.commit()
        flash(f"{dict(AUDIT_DOMAINS)[domain]} retiré du programme {year}.", "success")
        return redirect(url_for("audits.programme"))
    if it is None:
        it = AuditPlanItem(year=year, domain=domain)
        db.session.add(it)
    q = request.form.get("quarter", type=int)
    it.quarter = q if q in (1, 2, 3, 4) else None
    it.auditor_id = request.form.get("auditor_id", type=int) or None
    it.audit_id = request.form.get("audit_id", type=int) or None
    it.note = (request.form.get("note") or "").strip()[:300] or None
    db.session.commit()
    flash(f"Programme {year} mis à jour : {dict(AUDIT_DOMAINS)[domain]}.", "success")
    return redirect(url_for("audits.programme"))
