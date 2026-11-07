"""Vie privée (ISO/IEC 27701) : registre des traitements et demandes des personnes concernées.
Accessible quand l'organisation a activé l'ISO 27701."""
import io
from datetime import datetime, date, timedelta
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file
from flask_login import login_required

from app.extensions import db
from app.models import User, Asset, Supplier
from app.models.privacy import (ProcessingActivity, SubjectRequest, LegalBasis, ProcessingRole, DpiaStatus,
                                ProcessingStatus, RequestType, RequestStatus)
from app.services import attachments as att_svc
from app.services import frameworks as fw_svc
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("privacy", __name__, url_prefix="/vie-privee")
CODE = "ISO27701"


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


# --- Registre des traitements ------------------------------------------------
@bp.route("/traitements")
@login_required
@norm_required
def index():
    f_status = request.args.get("statut")
    f_gap = request.args.get("ecarts")
    q = ProcessingActivity.query
    if f_status in [x.value for x in ProcessingStatus]:
        q = q.filter(ProcessingActivity.status == ProcessingStatus(f_status))
    order = {"ACTIF": 0, "EN_PROJET": 1, "ARRETE": 2}
    items = sorted(q.all(), key=lambda p: (order[p.status.value], p.ref))
    if f_gap:
        items = [p for p in items if p.gaps]
    live = [p for p in ProcessingActivity.query.all() if p.status != ProcessingStatus.ARRETE]
    stats = {"live": len(live), "sensitive": sum(p.sensitive_data for p in live),
             "dpia": sum(p.dpia in (DpiaStatus.A_EVALUER, DpiaStatus.A_REALISER) for p in live),
             "gaps": sum(bool(p.gaps) for p in live)}
    return render_template("privacy/index.html", items=items, stats=stats, f_status=f_status, f_gap=f_gap,
                           ProcessingStatus=ProcessingStatus)


@bp.route("/traitements/<int:pid>")
@login_required
@norm_required
def detail(pid):
    p = db.session.get(ProcessingActivity, pid) or abort(404)
    requests_ = SubjectRequest.query.filter_by(processing_id=p.id).order_by(SubjectRequest.received_on.desc()).all()
    return render_template("privacy/detail.html", p=p, requests_=requests_,
                           attachments=att_svc.get_for("processing", p.id))


@bp.route("/traitements/nouveau", methods=["GET", "POST"])
@editor_required
@norm_required
def create():
    return _form(None)


@bp.route("/traitements/<int:pid>/modifier", methods=["GET", "POST"])
@editor_required
@norm_required
def edit(pid):
    return _form(db.session.get(ProcessingActivity, pid) or abort(404))


def _form(p):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom du traitement est obligatoire.", "danger")
        else:
            if p is None:
                p = ProcessingActivity(ref=next_ref(ProcessingActivity, "TRT", width=3, yearly=False))
                db.session.add(p)
            p.name = name
            for f in ("purpose", "legal_basis_detail", "data_subjects", "data_categories", "sensitive_detail",
                      "source", "recipients", "transfer_detail", "retention", "security_measures", "notes"):
                setattr(p, f, (request.form.get(f) or "").strip() or None)
            p.role = ProcessingRole(request.form.get("role", "RESPONSABLE"))
            p.legal_basis = LegalBasis(request.form.get("legal_basis", "A_DETERMINER"))
            p.sensitive_data = bool(request.form.get("sensitive_data"))
            p.transfers = bool(request.form.get("transfers"))
            p.dpia = DpiaStatus(request.form.get("dpia", "A_EVALUER"))
            p.dpia_date = _date(request.form.get("dpia_date"))
            p.status = ProcessingStatus(request.form.get("status", "ACTIF"))
            p.owner_id = request.form.get("owner_id", type=int) or None
            p.last_review = _date(request.form.get("last_review"))
            p.next_review = _date(request.form.get("next_review"))
            if p.last_review and not p.next_review:
                p.next_review = p.default_next(p.last_review)
            ids = [int(x) for x in request.form.getlist("asset_ids") if x.isdigit()]
            p.assets = Asset.query.filter(Asset.id.in_(ids)).all() if ids else []
            ids = [int(x) for x in request.form.getlist("supplier_ids") if x.isdigit()]
            p.suppliers = Supplier.query.filter(Supplier.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Traitement {p.ref} enregistré.", "success")
            return redirect(url_for("privacy.detail", pid=p.id))
    return render_template("privacy/form.html", p=p, users=_users(), LegalBasis=LegalBasis,
                           ProcessingRole=ProcessingRole, DpiaStatus=DpiaStatus, ProcessingStatus=ProcessingStatus,
                           assets=Asset.query.order_by(Asset.name).all(),
                           suppliers=Supplier.query.order_by(Supplier.name).all())


@bp.route("/traitements/registre.xlsx")
@login_required
@norm_required
def export():
    """Registre des traitements au format tableur (une ligne par traitement)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from app.services import settings as settings_svc
    from app.services.audit_trail import log_event
    wb = Workbook()
    ws = wb.active
    ws.title = "Registre des traitements"
    cols = [("Réf.", "ref", 10), ("Traitement", "name", 30), ("Finalité(s)", "purpose", 40), ("Rôle", "role", 18),
            ("Base juridique", "legal_basis", 22), ("Précisions", "legal_basis_detail", 30),
            ("Personnes concernées", "data_subjects", 28), ("Catégories de données", "data_categories", 34),
            ("Données sensibles", "sensitive_data", 12), ("Précisions (sensibles)", "sensitive_detail", 28),
            ("Source", "source", 22), ("Destinataires", "recipients", 30), ("Sous-traitants", "suppliers", 28),
            ("Transferts hors du pays", "transfers", 12), ("Pays et garanties", "transfer_detail", 30),
            ("Conservation", "retention", 26), ("Mesures de sécurité", "security_measures", 36),
            ("Analyse d'impact", "dpia", 18), ("Statut", "status", 12), ("Responsable interne", "owner", 20),
            ("Dernière revue", "last_review", 13)]
    ws.append([c[0] for c in cols])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E5BB8")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for p in sorted(ProcessingActivity.query.all(), key=lambda x: x.ref):
        row = []
        for _, attr, _w in cols:
            v = getattr(p, attr, None) if attr not in ("suppliers", "owner") else None
            if attr == "suppliers":
                v = ", ".join(s.name for s in p.suppliers)
            elif attr == "owner":
                v = p.owner.name if p.owner else ""
            elif hasattr(v, "label"):
                v = v.label
            elif isinstance(v, bool):
                v = "Oui" if v else "Non"
            elif isinstance(v, date):
                v = v.strftime("%d/%m/%Y")
            row.append(v or "")
        ws.append(row)
    for i, (_, _, w) in enumerate(cols, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
    for r in ws.iter_rows(min_row=2):
        for cell in r:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    log_event("export", "Export du registre des traitements (xlsx)")
    org = settings_svc.get("org_name", "organisation")
    return send_file(buf, as_attachment=True, download_name=f"Registre des traitements - {org}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --- Demandes des personnes concernées ---------------------------------------
@bp.route("/demandes")
@login_required
@norm_required
def requests_index():
    f_open = request.args.get("ouvertes", "1")
    q = SubjectRequest.query
    items = q.order_by(SubjectRequest.received_on.desc(), SubjectRequest.id.desc()).all()
    if f_open == "1":
        items = [r for r in items if not r.status.closed]
    allr = SubjectRequest.query.all()
    year = date.today().year
    stats = {"open": sum(not r.status.closed for r in allr), "overdue": sum(r.overdue for r in allr),
             "year": sum(r.received_on.year == year for r in allr if r.received_on),
             "late_closed": sum(1 for r in allr if r.status.closed and r.closed_on and r.due_on and r.closed_on > r.due_on)}
    return render_template("privacy/requests.html", items=items, stats=stats, f_open=f_open)


@bp.route("/demandes/nouvelle", methods=["GET", "POST"])
@editor_required
@norm_required
def request_create():
    return _request_form(None)


@bp.route("/demandes/<int:rid>", methods=["GET", "POST"])
@editor_required
@norm_required
def request_edit(rid):
    return _request_form(db.session.get(SubjectRequest, rid) or abort(404))


def _request_form(r):
    if request.method == "POST":
        requester = (request.form.get("requester") or "").strip()
        if not requester:
            flash("Indiquez le demandeur (nom ou référence).", "danger")
        else:
            if r is None:
                r = SubjectRequest(ref=next_ref(SubjectRequest, "DMD", width=4))
                db.session.add(r)
            r.requester = requester[:200]
            r.request_type = RequestType(request.form.get("request_type", "ACCES"))
            r.channel = (request.form.get("channel") or "").strip()[:120] or None
            r.received_on = _date(request.form.get("received_on")) or date.today()
            r.due_on = _date(request.form.get("due_on")) or (r.received_on + timedelta(days=SubjectRequest.RESPONSE_DAYS))
            r.processing_id = request.form.get("processing_id", type=int) or None
            r.identity_verified = bool(request.form.get("identity_verified"))
            r.status = RequestStatus(request.form.get("status", "RECUE"))
            r.handled_by_id = request.form.get("handled_by_id", type=int) or None
            r.response = (request.form.get("response") or "").strip() or None
            r.notes = (request.form.get("notes") or "").strip() or None
            r.closed_on = (_date(request.form.get("closed_on")) or r.closed_on or date.today()) if r.status.closed else None
            db.session.commit()
            flash(f"Demande {r.ref} enregistrée." + (" Échéance de réponse : " + r.due_on.strftime("%d/%m/%Y") + "."
                                                     if not r.status.closed else ""), "success")
            return redirect(url_for("privacy.requests_index"))
    return render_template("privacy/request_form.html", r=r, users=_users(), RequestType=RequestType,
                           RequestStatus=RequestStatus, days=SubjectRequest.RESPONSE_DAYS,
                           processings=ProcessingActivity.query.order_by(ProcessingActivity.ref).all())
