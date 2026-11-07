from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import Asset, User, AssetCategory, Classification, AssetStatus
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("assets", __name__, url_prefix="/actifs")


@bp.route("/")
@login_required
def index():
    f_cat = request.args.get("categorie")
    f_cls = request.args.get("classification")
    f_st = request.args.get("statut")
    q = Asset.query
    if f_cat in [x.value for x in AssetCategory]:
        q = q.filter(Asset.category == AssetCategory(f_cat))
    if f_cls in [x.value for x in Classification]:
        q = q.filter(Asset.classification == Classification(f_cls))
    if f_st in [x.value for x in AssetStatus]:
        q = q.filter(Asset.status == AssetStatus(f_st))
    assets = q.order_by(Asset.ref).all()
    stats = {"total": Asset.query.count(),
             "actifs": Asset.query.filter_by(status=AssetStatus.ACTIF).count(),
             "sensibles": Asset.query.filter(Asset.classification.in_([Classification.CONFIDENTIEL, Classification.SECRET])).count()}
    return render_template("assets/index.html", assets=assets, stats=stats,
                           f_cat=f_cat, f_cls=f_cls, f_st=f_st,
                           AssetCategory=AssetCategory, Classification=Classification, AssetStatus=AssetStatus)


@bp.route("/<int:asset_id>")
@login_required
def detail(asset_id):
    from app.models import ChangeRequest
    a = db.session.get(Asset, asset_id) or abort(404)
    changes = [c for c in ChangeRequest.query.order_by(ChangeRequest.created_at.desc()) if a in c.assets]
    return render_template("assets/detail.html", a=a, changes=changes)


@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    return _form(None)


@bp.route("/<int:asset_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(asset_id):
    return _form(db.session.get(Asset, asset_id) or abort(404))


def _form(a):
    users = User.query.filter_by(is_active_flag=True).order_by(User.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom de l'actif est obligatoire.", "danger")
        else:
            if a is None:
                a = Asset(ref=next_ref(Asset, "ACT"))
                db.session.add(a)
            a.name = name
            a.category = AssetCategory(request.form.get("category", "INFORMATION"))
            a.description = request.form.get("description")
            a.owner_id = request.form.get("owner_id", type=int) or None
            a.custodian = request.form.get("custodian")
            a.classification = Classification(request.form.get("classification", "INTERNE"))
            a.location = request.form.get("location")
            a.status = AssetStatus(request.form.get("status", "ACTIF"))
            db.session.commit()
            flash(f"Actif {a.ref} enregistré.", "success")
            return redirect(url_for("assets.detail", asset_id=a.id))
    return render_template("assets/form.html", a=a, users=users,
                           AssetCategory=AssetCategory, Classification=Classification, AssetStatus=AssetStatus)
