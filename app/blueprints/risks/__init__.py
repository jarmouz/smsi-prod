from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Risk, Control, User, Asset, Treatment, RiskStatus
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("risks", __name__, url_prefix="/risques")


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# --- Cotation ---------------------------------------------------------------
def _rating(axis, val, default=None):
    """Cotation bornée à l'échelle de l'organisation (sinon valeur par défaut)."""
    from app.services import risk_criteria
    try:
        n = int(val)
    except (TypeError, ValueError):
        return default
    return n if 1 <= n <= risk_criteria.scale(axis) else default


def _mid(axis):
    from app.services import risk_criteria
    return risk_criteria.middle(axis)


@bp.route("/import", methods=["GET", "POST"])
@editor_required
def import_file():
    # remplacé par l'import guidé (correspondance des colonnes + aperçu)
    return redirect(url_for("imports.upload", kind="risques"))


@bp.route("/import/modele.csv")
@editor_required
def import_template():
    return redirect(url_for("imports.template", kind="risques"))


def _smi_fields(r):
    """Domaine, nature, option de traitement cohérente avec la nature, normes supplémentaires."""
    from app.models.risk import DOMAINS, SECURITE, RISK_NATURES
    from app.services import frameworks as fw_svc
    f = request.form
    if f.get("smi_present"):
        d = f.get("risk_domain") or SECURITE
        r.risk_domain = None if d == SECURITE or d not in DOMAINS else d
        n = f.get("nature") or None
        r.nature = n if n in RISK_NATURES else None
    try:
        t = Treatment(f.get("treatment") or "")
    except ValueError:
        t = None
    allowed = Treatment.for_nature(r.nature)
    r.treatment = t if t in allowed else (r.treatment if r.treatment in allowed else Treatment.default_for(r.nature))
    if r.is_opportunity:                    # pas d'acceptation formelle pour une opportunité
        r.accepted_by_id = r.accepted_at = r.accepted_score = r.acceptance_note = r.acceptance_until = None
    if f.get("fw_present"):
        db.session.flush()                  # id requis pour les rattachements
        base = set(DOMAINS[r.domain_key][1])
        fw_svc.set_links(r, [c for c in f.getlist("fw") if c not in base], collapse=False)


def _controls_from_form(r):
    """Mesures cochées parmi les normes proposées ; celles d'une norme non proposée
    (désactivée depuis) restent rattachées."""
    offered = {c.id for _, groups in _control_groups() for _, cs in groups for c in cs}
    ids = set(request.form.getlist("controls", type=int)) & offered
    kept = [c for c in (r.controls or []) if c.id not in offered]
    r.controls = kept + (Control.query.filter(Control.id.in_(ids)).all() if ids else [])


def _control_groups():
    """Mesures d'annexe des normes actives à mesures (27001, 27701, 42001), par norme puis par groupe."""
    from app.services import frameworks as fw_svc
    from app.models import Theme
    out = []
    for fw in fw_svc.active():
        if fw.kind != "controls":
            continue
        cs = Control.of(fw.code, "control").order_by(Control.id).all()
        groups = {}
        for c in cs:
            key = f"{c.theme.annex} - {c.theme.label}" if isinstance(c.theme, Theme) else str(c.theme)
            groups.setdefault(key, []).append(c)
        if cs:
            out.append((fw, list(groups.items())))
    return out


def _form_ctx(risk):
    from app.models.risk import domains_for, DOMAINS
    from app.services import frameworks as fw_svc
    codes = [f.code for f in fw_svc.active()]
    explicit = {f.code for f in fw_svc.frameworks_of(risk)} if risk else set()
    return dict(control_groups=_control_groups(), users=User.query.filter_by(is_active_flag=True).order_by(User.name).all(),
                assets=Asset.query.order_by(Asset.ref).all(), Treatment=Treatment, RiskStatus=RiskStatus, risk=risk,
                domains=domains_for(codes, risk.risk_domain if risk else None),
                fw_list=fw_svc.active(), fw_on=explicit,
                domain_norms={k: list(v[1]) for k, v in DOMAINS.items()})


@bp.route("/")
@login_required
def index():
    from app.models.risk import DOMAINS, SECURITE, OPPORTUNITE, domains_for
    from app.services import frameworks as fw_svc
    f_status = request.args.get("statut")
    f_level = request.args.get("niveau")
    f_domain = request.args.get("domaine")
    f_nature = request.args.get("nature")
    f_norm = request.args.get("norme")
    q = Risk.query
    if f_status in [s.value for s in RiskStatus]:
        q = q.filter(Risk.status == RiskStatus(f_status))
    if f_domain == SECURITE:
        q = q.filter(Risk.risk_domain.is_(None))
    elif f_domain in DOMAINS:
        q = q.filter(Risk.risk_domain == f_domain)
    elif f_domain == OPPORTUNITE:               # ancien lien (3.3 à 3.5)
        f_nature, f_domain = "opportunites", None
    if f_nature == "opportunites":
        q = q.filter(Risk.nature == OPPORTUNITE)
    elif f_nature == "risques":
        q = q.filter(Risk.nature.is_(None))
    risks = q.all()
    active = fw_svc.active()
    if f_norm in {f.code for f in active}:
        risks = [r for r in risks if r.concerns(f_norm)]
    if f_level:
        risks = [r for r in risks if r.display_level == f_level]
    f_acc = request.args.get("acceptation")
    if f_acc == "a_faire":
        risks = [r for r in risks if r.acceptance_state in ("required", "expired", "outdated")]
    elif f_acc == "acceptes":
        risks = [r for r in risks if r.acceptance_state == "valid"]
    risks.sort(key=lambda r: (r.is_opportunity, -r.effective_score))
    return render_template("risks/index.html", risks=risks, f_status=f_status, f_level=f_level, f_acc=f_acc,
                           f_domain=f_domain, f_nature=f_nature, f_norm=f_norm, fw_list=active,
                           domains=domains_for([f.code for f in active]))


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("Le titre du risque est obligatoire.", "danger")
        else:
            r = Risk(
                ref=next_ref(Risk, "R"),
                title=title,
                description=request.form.get("description"),
                asset=request.form.get("asset"),
                threat=request.form.get("threat"),
                vulnerability=request.form.get("vulnerability"),
                likelihood=_rating("likelihood", request.form.get("likelihood"), _mid("likelihood")),
                impact=_rating("impact", request.form.get("impact"), _mid("impact")),
                residual_likelihood=_rating("likelihood", request.form.get("residual_likelihood")),
                residual_impact=_rating("impact", request.form.get("residual_impact")),
                status=RiskStatus(request.form.get("status", "IDENTIFIE")),
                owner_id=request.form.get("owner_id", type=int) or None,
                review_date=_parse_date(request.form.get("review_date")),
            )
            r.controls = []
            _controls_from_form(r)
            asset_ids = request.form.getlist("assets", type=int)
            r.assets = Asset.query.filter(Asset.id.in_(asset_ids)).all() if asset_ids else []
            db.session.add(r)
            _smi_fields(r)
            db.session.commit()
            flash(f"{'Opportunité' if r.is_opportunity else 'Risque'} {r.ref} créé{'e' if r.is_opportunity else ''}.", "success")
            return redirect(url_for("risks.detail", risk_id=r.id))
    return render_template("risks/form.html", **_form_ctx(None))


@bp.route("/<int:risk_id>")
@login_required
def detail(risk_id):
    r = db.session.get(Risk, risk_id) or abort(404)
    return render_template("risks/detail.html", r=r, can_accept=_can_accept(r))


@bp.route("/<int:risk_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(risk_id):
    r = db.session.get(Risk, risk_id) or abort(404)
    if request.method == "POST":
        r.title = (request.form.get("title") or r.title).strip()
        r.description = request.form.get("description")
        r.asset = request.form.get("asset")
        r.threat = request.form.get("threat")
        r.vulnerability = request.form.get("vulnerability")
        r.likelihood = _rating("likelihood", request.form.get("likelihood"), r.likelihood)
        r.impact = _rating("impact", request.form.get("impact"), r.impact)
        r.residual_likelihood = _rating("likelihood", request.form.get("residual_likelihood"))
        r.residual_impact = _rating("impact", request.form.get("residual_impact"))
        r.status = RiskStatus(request.form.get("status", r.status.value))
        r.owner_id = request.form.get("owner_id", type=int) or None
        r.review_date = _parse_date(request.form.get("review_date"))
        _controls_from_form(r)
        asset_ids = request.form.getlist("assets", type=int)
        r.assets = Asset.query.filter(Asset.id.in_(asset_ids)).all() if asset_ids else []
        _smi_fields(r)
        db.session.commit()
        flash(f"Risque {r.ref} mis à jour.", "success")
        return redirect(url_for("risks.detail", risk_id=r.id))
    return render_template("risks/form.html", **_form_ctx(r))


# --- Acceptation formelle du risque résiduel (ISO/IEC 27001 6.1.3 f) -------
def _can_accept(r):
    return not r.is_opportunity and current_user.is_authenticated and not current_user.is_readonly and \
        (current_user.id == r.owner_id or current_user.role.value == "RSSI")


@bp.route("/<int:risk_id>/accepter", methods=["POST"])
@login_required
def accept(risk_id):
    from datetime import date as _date, timedelta
    from app.services.audit_trail import log_event
    r = db.session.get(Risk, risk_id) or abort(404)
    if not _can_accept(r):
        abort(403)
    note = (request.form.get("acceptance_note") or "").strip()
    if not note:
        flash("Une justification est obligatoire pour accepter un risque résiduel.", "danger")
        return redirect(url_for("risks.detail", risk_id=r.id))
    r.accepted_by_id = current_user.id
    r.accepted_at = datetime.utcnow()
    r.accepted_score = r.effective_score
    r.acceptance_note = note
    r.acceptance_until = _parse_date(request.form.get("acceptance_until")) or (_date.today() + timedelta(days=365))
    db.session.commit()
    on_behalf = "" if current_user.id == r.owner_id else \
        f" (enregistrée par {current_user.name} pour le propriétaire {r.owner.name if r.owner else 'non désigné'})"
    log_event("accept", f"Risque résiduel accepté au score {r.accepted_score}{on_behalf}", entity=r)
    flash(f"Risque résiduel {r.ref} accepté jusqu'au {r.acceptance_until.strftime('%d/%m/%Y')}.", "success")
    return redirect(url_for("risks.detail", risk_id=r.id))


@bp.route("/<int:risk_id>/retirer-acceptation", methods=["POST"])
@login_required
def revoke_acceptance(risk_id):
    from app.services.audit_trail import log_event
    r = db.session.get(Risk, risk_id) or abort(404)
    if not _can_accept(r):
        abort(403)
    r.accepted_by_id = r.accepted_at = r.accepted_score = r.acceptance_note = r.acceptance_until = None
    db.session.commit()
    log_event("accept", "Acceptation du risque résiduel retirée", entity=r)
    flash("Acceptation retirée.", "success")
    return redirect(url_for("risks.detail", risk_id=r.id))
