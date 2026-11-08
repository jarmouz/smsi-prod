"""Actions en masse sur les listes : export, attribution, statut, suppression (3.18)."""
import csv
import io
from datetime import datetime
from urllib.parse import quote, urlparse

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Role, User
from app.services import bulk as svc
from app.services.access import editor_required, rssi_required
from app.services.audit_trail import log_event
from app.services.exports import _csv_safe

bp = Blueprint("bulk", __name__, url_prefix="/masse")


def _spec(kind):
    return svc.registry().get(kind) or abort(404)


def _ids():
    out = []
    for raw in request.form.getlist("ids")[:svc.MAX_IDS]:
        if raw.isdigit():
            out.append(int(raw))
    return out


def _back():
    target = request.form.get("next") or request.referrer or url_for("dashboard.home")
    p = urlparse(target)
    if p.netloc and p.netloc != request.host:
        return url_for("dashboard.home")
    return (p.path or "/") + (f"?{p.query}" if p.query else "")


@bp.route("/<kind>/config")
@editor_required
def config(kind):
    spec = _spec(kind)
    users = []
    if svc.owner_attr(spec.model):
        users = [[u.id, u.name] for u in User.query.filter_by(is_active_flag=True).order_by(User.name).all()]
    statuses = [[s.value, s.label] for s in spec.status] if spec.status else []
    return jsonify({"label": spec.label, "users": users, "statuses": statuses, "canDelete": current_user.role == Role.RSSI})


@bp.route("/<kind>/exporter", methods=["POST"])
@editor_required
def export(kind):
    spec = _spec(kind)
    objs = svc.load(spec, _ids())
    if not objs:
        flash("Aucun élément sélectionné.", "warning")
        return redirect(_back())
    buf = io.StringIO()
    csv.writer(buf, delimiter=";").writerows([_csv_safe(c) for c in row] for row in svc.csv_rows(spec, objs))
    log_event("export", f"Export de la sélection : {len(objs)} {spec.label} (CSV)")
    name = quote(f"{spec.label} - selection - {datetime.utcnow():%Y-%m-%d}.csv")
    return Response(("﻿" + buf.getvalue()).encode("utf-8"), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{name}"})


@bp.route("/<kind>/attribuer", methods=["POST"])
@editor_required
def assign(kind):
    spec = _spec(kind)
    attr = svc.owner_attr(spec.model) or abort(404)
    user = db.session.get(User, request.form.get("user_id", type=int) or 0)
    if user is None or not user.is_active_flag:
        flash("Choisissez un utilisateur actif.", "danger")
        return redirect(_back())
    objs = svc.load(spec, _ids())
    for o in objs:
        setattr(o, attr, user.id)
    db.session.commit()
    flash(f"{len(objs)} élément(s) attribué(s) à {user.name}.", "success")
    return redirect(_back())


@bp.route("/<kind>/statut", methods=["POST"])
@editor_required
def status(kind):
    spec = _spec(kind)
    if not spec.status:
        abort(404)
    value = request.form.get("status")
    if value not in [s.value for s in spec.status]:
        flash("Statut inconnu.", "danger")
        return redirect(_back())
    objs = svc.load(spec, _ids())
    for o in objs:
        o.status = spec.status(value)
    db.session.commit()
    flash(f"{len(objs)} élément(s) : statut modifié.", "success")
    return redirect(_back())


@bp.route("/<kind>/supprimer", methods=["POST"])
@rssi_required
def confirm(kind):
    """Écran de confirmation : rien n'est supprimé ici."""
    spec = _spec(kind)
    objs = svc.load(spec, _ids())
    if not objs:
        flash("Aucun élément sélectionné.", "warning")
        return redirect(_back())
    deletable, protected, blocked = svc.classify(spec, objs)
    return render_template("bulk/confirm.html", kind=kind, spec=spec, deletable=deletable, protected=protected, blocked=blocked,
                           label_of=svc.label_of, back=_back(), word=svc.CONFIRM_WORD)


@bp.route("/<kind>/supprimer/confirmer", methods=["POST"])
@rssi_required
def apply(kind):
    spec = _spec(kind)
    back = _back()
    if (request.form.get("confirm") or "").strip().upper() != svc.CONFIRM_WORD:
        flash(f"Saisissez {svc.CONFIRM_WORD} pour confirmer : rien n'a été supprimé.", "warning")
        return redirect(back)
    done, skipped = svc.delete(spec, svc.load(spec, _ids()), bool(request.form.get("include_protected")))
    if done:
        flash(f"{len(done)} élément(s) supprimé(s). Une copie est conservée au journal d'activité.", "success")
    if skipped:
        flash(f"{skipped} élément(s) conservé(s) : protégés ou encore utilisés.", "warning")
    return redirect(back)
