from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import Asset, User, AssetCategory, Classification, AssetStatus
from app.models.asset import NEED_LEVELS, NEED_KEYS, DISPOSAL_METHODS
from app.services import inventory
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("assets", __name__, url_prefix="/actifs")


@bp.route("/")
@login_required
def index():
    f_cat = request.args.get("categorie")
    f_cls = request.args.get("classification")
    f_st = request.args.get("statut")
    f_role = request.args.get("role")
    f_crit = request.args.get("criticite", type=int)
    f_cycle = request.args.get("cycle")
    allassets = Asset.query.all()
    assets = inventory.filter_assets(request.args)
    live = [a for a in allassets if a.in_service]
    stats = {"total": len(allassets), "actifs": sum(a.status == AssetStatus.ACTIF for a in allassets),
             "metier": sum(a.is_business for a in live), "support": sum(not a.is_business for a in live),
             "critiques": sum(a.criticality == 4 for a in live),
             "sensibles": sum(a.classification in (Classification.CONFIDENTIEL, Classification.SECRET) for a in live),
             **{k: sum(1 for a in allassets if fn(a)) for k, fn in inventory.CYCLE.items()}}
    return render_template("assets/index.html", assets=assets, stats=stats,
                           f_cat=f_cat, f_cls=f_cls, f_st=f_st, f_role=f_role, f_crit=f_crit, f_cycle=f_cycle,
                           AssetCategory=AssetCategory, Classification=Classification, AssetStatus=AssetStatus,
                           NEED_LEVELS=NEED_LEVELS)


@bp.route("/export.<fmt>")
@login_required
def export(fmt):
    """Inventaire aux filtres de l'écran : xlsx | csv | docx | pdf."""
    from app.services import exports
    if fmt == "csv":
        return exports.assets_csv_response()
    if fmt not in exports.MIMES:
        abort(404)
    try:
        return exports.response("inventaire-actifs", fmt)
    except RuntimeError as e:
        flash(f"Export PDF indisponible ({e}). Utilisez l'export Word ou Excel.", "danger")
        return redirect(url_for("assets.index", **request.args))


@bp.route("/<int:asset_id>")
@login_required
def detail(asset_id):
    from app.models import ChangeRequest
    a = db.session.get(Asset, asset_id) or abort(404)
    changes = [c for c in ChangeRequest.query.order_by(ChangeRequest.created_at.desc()) if a in c.assets]
    return render_template("assets/detail.html", a=a, changes=changes, NEED_LEVELS=NEED_LEVELS, NEED_KEYS=NEED_KEYS)


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:asset_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(asset_id):
    return _form(db.session.get(Asset, asset_id) or abort(404))


def _date(v):
    try:
        return datetime.strptime(v, "%Y-%m-%d").date() if v else None
    except ValueError:
        return None


def _level(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n in NEED_LEVELS else None


def _form(a):
    users = User.query.order_by(User.name).all()
    if request.method == "POST":
        f = request.form
        name = (f.get("name") or "").strip()
        if not name:
            flash("Le nom de l'actif est obligatoire.", "danger")
        else:
            if a is None:
                a = Asset(ref=next_ref(Asset, "ACT"))
                db.session.add(a)
            a.name = name
            a.category = AssetCategory(f.get("category", "INFORMATION"))
            a.description = f.get("description")
            a.owner_id = f.get("owner_id", type=int) or None
            a.custodian = f.get("custodian")
            a.classification = Classification(f.get("classification", "INTERNE"))
            a.location = f.get("location")
            a.status = AssetStatus(f.get("status", "ACTIF"))
            # besoins DIC+T
            for k, _ in NEED_KEYS:
                setattr(a, f"need_{k}", _level(f.get(f"need_{k}")))
            # dépendances : une valeur métier choisit ses biens supports, un bien support les valeurs portées
            if f.get("deps_present"):
                ids = set(f.getlist("deps", type=int)) - {a.id}
                others = Asset.query.filter(Asset.id.in_(ids)).all() if ids else []
                if a.is_business:
                    a.supports = [o for o in others if not o.is_business]
                    a.supported = []
                else:
                    a.supported = [o for o in others if o.is_business]
                    a.supports = []
            # cycle de vie
            a.acquired_on = _date(f.get("acquired_on"))
            a.end_of_support = _date(f.get("end_of_support"))
            a.holder_id = f.get("holder_id", type=int) or None
            a.disposed_on = _date(f.get("disposed_on"))
            m = f.get("disposal_method")
            a.disposal_method = m if m in DISPOSAL_METHODS else None
            a.disposal_proof = (f.get("disposal_proof") or "").strip()[:300] or None
            if a.status == AssetStatus.RETIRE and a.disposal_missing:
                flash("Actif retiré : indiquez la méthode d'élimination et la preuve (certificat, PV) - mesure A.7.14.",
                      "warning")
            db.session.commit()
            flash(f"Actif {a.ref} enregistré.", "success")
            return redirect(url_for("assets.detail", asset_id=a.id))
    others = Asset.query.filter(Asset.id != (a.id if a else 0)).order_by(Asset.ref).all()
    return render_template("assets/form.html", a=a, users=users, others=others,
                           AssetCategory=AssetCategory, Classification=Classification, AssetStatus=AssetStatus,
                           NEED_LEVELS=NEED_LEVELS, NEED_KEYS=NEED_KEYS, DISPOSAL_METHODS=DISPOSAL_METHODS)
