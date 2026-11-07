from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Control, User, Theme, ControlStatus
from app.services.access import editor_required

bp = Blueprint("soa", __name__, url_prefix="/dda")


@bp.route("/")
@login_required
def index():
    f_theme = request.args.get("theme")
    f_status = request.args.get("statut")
    f_appl = request.args.get("applicable")
    search = (request.args.get("q") or "").strip()

    from app.services import frameworks as fw_svc
    fws = fw_svc.controls_frameworks()
    norme = request.args.get("norme")
    fw = next((f for f in fws if f.code == norme), None) or fw_svc.get(fw_svc.CORE)
    norme = None if fw.code == fw_svc.CORE else fw.code      # URL inchangée pour l'ISO 27001
    # Normes à mesures ayant aussi leurs exigences de chapitres (27001, 42001 : 3.5) :
    # « mesures » (DdA, vue par défaut, inchangée) ou « exigences » (chapitres 4 à 10)
    split = fw_svc.has_clauses(fw)
    vue = "exigences" if split and request.args.get("vue") == "exigences" else None
    kind = "clause" if vue else None
    reqs = fw.kind != "controls" or vue          # vue d'exigences (normes d'exigences, socle, chapitres)

    q = Control.of(fw.code, kind)
    if fw.code == fw_svc.CORE and not vue:
        groups = [(t.value, f"{t.annex} - {t.label}") for t in Theme]
    else:
        groups = [(g, g) for (g,) in db.session.query(Control.theme)
                  .filter(Control.framework_id == fw.id, Control.kind == (kind or ("control" if fw.kind == "controls" else "clause")))
                  .distinct().order_by(Control.theme)]
        if reqs:      # chapitres dans l'ordre numérique (« 10 Amélioration » après « 9 »)
            groups.sort(key=lambda g: int(str(g[0]).split(" ")[0]) if str(g[0]).split(" ")[0].isdigit() else 99)
    if f_theme in [v for v, _ in groups]:
        q = q.filter(Control.theme == f_theme)
    if f_status in [s.value for s in ControlStatus]:
        q = q.filter(Control.status == ControlStatus(f_status))
    if f_appl == "oui":
        q = q.filter(Control.applicable.is_(True))
    elif f_appl == "non":
        q = q.filter(Control.applicable.is_(False))
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(Control.title.ilike(like), Control.ref.ilike(like)))

    controls = q.order_by(Control.theme, Control.id).all() if fw.code == fw_svc.CORE and not vue else q.order_by(Control.id).all()

    # Regrouper par thème pour l'affichage
    grouped = {}
    for c in controls:
        grouped.setdefault(c.theme, []).append(c)

    # Statistiques globales (indépendantes des filtres)
    allc = Control.of(fw.code, kind).all()
    appl = [c for c in allc if c.applicable]
    stats = {
        "total": len(allc),
        "applicable": len(appl),
        "exclues": len(allc) - len(appl),
        "implementees": len([c for c in appl if c.status == ControlStatus.IMPLEMENTE]),
    }
    if fw.kind == "common":
        stats["socle"] = fw_svc.socle_stats()
    elif reqs:
        stats["heritees"] = sum(1 for c in allc if c.inherited)
        stats["propres"] = sum(1 for c in allc if not c.common_id)
    rels = {c.id: fw_svc.common_relation(c) for c in controls} if reqs and fw.kind != "common" else {}
    heirs = {c.id: fw_svc.heirs(c) for c in controls} if fw.kind == "common" else {}
    counts = {"mesures": Control.of(fw.code, "control").count(), "exigences": Control.of(fw.code, "clause").count()} if split else {}
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    return render_template("soa/index.html", grouped=grouped, stats=stats, users=users,
                           f_theme=f_theme, f_status=f_status, f_appl=f_appl, search=search,
                           fw=fw, fws=fws, norme=norme, groups=groups, rels=rels, heirs=heirs,
                           vue=vue, split=split, reqs=reqs, counts=counts)


@bp.route("/<int:control_id>")
@login_required
def detail(control_id):
    c = db.session.get(Control, control_id) or abort(404)
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    from app.services import frameworks as fw_svc
    from app.services import proofs
    from app.services.catalogue_data import SOCLE_NOTES
    return render_template("soa/detail.html", c=c, users=users, corresp=fw_svc.correspondences(c),
                           norme=None if c.framework.code == fw_svc.CORE else c.framework.code,
                           vue="exigences" if c.is_clause and c.framework.kind == "controls" else None,
                           rel=fw_svc.common_relation(c),
                           heirs=fw_svc.heirs(c) if c.framework.kind == "common" else [],
                           proofs=proofs.for_control(c),
                           socle_note=SOCLE_NOTES.get(c.ref) if c.framework.kind == "common" else None)


@bp.route("/<int:control_id>/modifier", methods=["POST"])
@editor_required
def update(control_id):
    c = db.session.get(Control, control_id) or abort(404)
    from app.services import frameworks as fw_svc
    if c.inherited:
        # Évaluation tenue dans le socle commun : seul le complément propre à la norme est saisi ici
        c.implementation = (request.form.get("implementation") or "").strip() or None
        db.session.commit()
        flash(f"Exigence {c.annex_ref} : complément enregistré (évaluation tenue dans le socle commun).", "success")
        return redirect(request.form.get("next") or url_for("soa.detail", control_id=c.id))
    c.applicable = request.form.get("applicable") == "oui"
    try:
        c.status = ControlStatus(request.form.get("status"))
    except (ValueError, TypeError):
        pass
    if not c.applicable:
        c.status = ControlStatus.NON_APPLICABLE
    c.justification = (request.form.get("justification") or "").strip() or None
    c.implementation = (request.form.get("implementation") or "").strip() or None
    owner_id = request.form.get("owner_id", type=int)
    c.owner_id = owner_id or None
    if c.framework.kind == "common":
        fw_svc.propagate(c)
    db.session.commit()
    flash(f"{'Exigence' if c.is_clause else 'Mesure'} {c.annex_ref} mise à jour.", "success")
    nxt = request.form.get("next")
    if nxt:
        return redirect(nxt)
    return redirect(url_for("soa.detail", control_id=c.id))


@bp.route("/<int:control_id>/socle", methods=["POST"])
@editor_required
def socle(control_id):
    """Rattache une exigence à l'évaluation du socle commun, ou l'en détache."""
    c = db.session.get(Control, control_id) or abort(404)
    from app.services import frameworks as fw_svc
    if not c.common_id:
        abort(400)
    on = request.form.get("action") == "heriter"
    fw_svc.set_inherit(c, on)
    db.session.commit()
    flash(f"Exigence {c.annex_ref} : " + ("évaluée dans le socle commun." if on else "évaluée séparément dans la norme."), "success")
    return redirect(url_for("soa.detail", control_id=c.id))


@bp.route("/export/<kind>.<fmt>")
@login_required
def export(kind, fmt):
    """Livrables pour l'auditeur : dda | registre-risques | plan-traitement, en xlsx | docx | pdf."""
    from app.services import exports
    if kind not in exports.DOCS or fmt not in exports.MIMES:
        abort(404)
    try:
        return exports.response(kind, fmt)
    except RuntimeError as e:
        flash(f"Export PDF indisponible ({e}). Utilisez l'export Word ou Excel.", "danger")
        return redirect(request.referrer or url_for("soa.index"))
