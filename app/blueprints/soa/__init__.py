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

    q = Control.of()
    if f_theme in [t.value for t in Theme]:
        q = q.filter(Control.theme == Theme(f_theme))
    if f_status in [s.value for s in ControlStatus]:
        q = q.filter(Control.status == ControlStatus(f_status))
    if f_appl == "oui":
        q = q.filter(Control.applicable.is_(True))
    elif f_appl == "non":
        q = q.filter(Control.applicable.is_(False))
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(Control.title.ilike(like), Control.ref.ilike(like)))

    controls = q.order_by(Control.theme, Control.id).all()

    # Regrouper par thème pour l'affichage
    grouped = {}
    for c in controls:
        grouped.setdefault(c.theme, []).append(c)

    # Statistiques globales (indépendantes des filtres)
    allc = Control.of().all()
    appl = [c for c in allc if c.applicable]
    stats = {
        "total": len(allc),
        "applicable": len(appl),
        "exclues": len(allc) - len(appl),
        "implementees": len([c for c in appl if c.status == ControlStatus.IMPLEMENTE]),
    }
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    return render_template("soa/index.html", grouped=grouped, stats=stats, users=users,
                           f_theme=f_theme, f_status=f_status, f_appl=f_appl, search=search)


@bp.route("/<int:control_id>")
@login_required
def detail(control_id):
    c = db.session.get(Control, control_id) or abort(404)
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    return render_template("soa/detail.html", c=c, users=users)


@bp.route("/<int:control_id>/modifier", methods=["POST"])
@editor_required
def update(control_id):
    c = db.session.get(Control, control_id) or abort(404)
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
    db.session.commit()
    flash(f"Mesure {c.annex_ref} mise à jour.", "success")
    nxt = request.form.get("next")
    if nxt:
        return redirect(nxt)
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
