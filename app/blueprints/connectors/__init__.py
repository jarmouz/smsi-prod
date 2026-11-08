"""Administration des connecteurs d'inventaire (3.15), réservée au RSSI."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Asset, Connector
from app.services import connectors as svc
from app.services.access import rssi_required

bp = Blueprint("connectors", __name__, url_prefix="/admin/connecteurs")


def _get(cid):
    return db.session.get(Connector, cid) or abort(404)


@bp.route("/")
@rssi_required
def index():
    items = Connector.query.order_by(Connector.kind, Connector.name).all()
    counts = {c.id: Asset.query.filter_by(connector_id=c.id).count() for c in items}
    return render_template("connectors/index.html", items=items, counts=counts, kinds=svc.kinds())


def _save(kind, c):
    """Enregistre le formulaire ; retourne le connecteur, ou None si incomplet (message affiché)."""
    f = request.form
    name = (f.get("name") or "").strip()[:120]
    cfg = {p.key: (f.get(p.key) or "").strip() for p in kind.params if not p.secret}
    old = svc.unseal(c.secret_enc) if c else {}
    typed = {p.key: f.get(p.key) or "" for p in kind.params if p.secret}
    if c and any(cfg.get(k) != (c.config or {}).get(k) for k in kind.bound_to) and not all(typed.values()):
        flash("L'adresse a changé : ressaisissez les secrets, pour qu'ils ne partent pas vers un autre serveur.", "danger")
        return None
    secrets = {k: v or old.get(k, "") for k, v in typed.items()}
    missing = [p.label for p in kind.params if p.required and not (secrets.get(p.key) if p.secret else cfg.get(p.key))]
    if not name or missing:
        flash("Champs obligatoires manquants : " + ", ".join(["Nom"] * (not name) + missing), "danger")
        return None
    dup = Connector.query.filter_by(kind=kind.key, name=name).first()
    if dup and (c is None or dup.id != c.id):
        flash("Un connecteur de ce type porte déjà ce nom.", "danger")
        return None
    if c is None:
        c = Connector(kind=kind.key)
        db.session.add(c)
    c.name, c.config, c.secret_enc, c.auto = name, cfg, svc.seal(secrets), bool(f.get("auto"))
    db.session.commit()
    return c


@bp.route("/nouveau/<kind>", methods=["GET", "POST"])
@rssi_required
def create(kind):
    k = svc.kinds().get(kind) or abort(404)
    if request.method == "POST" and (c := _save(k, None)):
        flash("Connecteur enregistré. Testez-le, puis consultez l'aperçu avant de synchroniser.", "success")
        return redirect(url_for("connectors.edit", cid=c.id))
    return render_template("connectors/form.html", kind=k, c=None)


@bp.route("/<int:cid>", methods=["GET", "POST"])
@rssi_required
def edit(cid):
    c = _get(cid)
    k = svc.kinds().get(c.kind)
    if request.method == "POST":
        if k is None:
            abort(404)
        if _save(k, c):
            flash("Connecteur enregistré.", "success")
        return redirect(url_for("connectors.edit", cid=c.id))
    return render_template("connectors/form.html", kind=k, c=c, count=Asset.query.filter_by(connector_id=c.id).count())


@bp.route("/<int:cid>/tester", methods=["POST"])
@rssi_required
def test(cid):
    c = _get(cid)
    try:
        first = svc.test(c)
        flash(f"Connexion réussie. Premier élément lu : {first}." if first else "Connexion réussie, mais la source est vide.", "success")
    except svc.ConnectorError as e:
        flash(str(e), "danger")
    return redirect(url_for("connectors.edit", cid=cid))


@bp.route("/<int:cid>/apercu", methods=["POST"])
@rssi_required
def preview(cid):
    c = _get(cid)
    try:
        res = svc.run(c, apply=False)
    except svc.ConnectorError as e:
        flash(str(e), "danger")
        return redirect(url_for("connectors.edit", cid=cid))
    return render_template("connectors/preview.html", c=_get(cid), res=res)


@bp.route("/<int:cid>/synchroniser", methods=["POST"])
@rssi_required
def sync(cid):
    c = _get(cid)
    try:
        res = svc.run(c, apply=True)
        flash("Synchronisation terminée : " + svc.summary(res) + ".", "success")
    except svc.ConnectorError as e:
        flash(str(e), "danger")
    return redirect(url_for("connectors.edit", cid=cid))


@bp.route("/<int:cid>/supprimer", methods=["POST"])
@rssi_required
def delete(cid):
    c = _get(cid)
    Asset.query.filter_by(connector_id=cid).update({"connector_id": None, "external_id": None, "source_seen_at": None,
                                                    "source_missing_since": None}, synchronize_session=False)
    db.session.delete(c)
    db.session.commit()
    flash("Connecteur supprimé. Les actifs sont conservés dans l'inventaire.", "success")
    return redirect(url_for("connectors.index"))
