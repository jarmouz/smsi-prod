"""Objectifs de sécurité (6.2) et indicateurs de surveillance et de mesure (9.1)."""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (Objective, Indicator, Measurement, Control, User, ObjectiveStatus, Frequency, Direction)
from app.services.access import editor_required
from app.services.refs import next_ref

bp = Blueprint("objectives", __name__, url_prefix="/objectifs")


def _date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _float(s):
    try:
        return float(str(s).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def _users():
    return User.query.filter_by(is_active_flag=True).order_by(User.name).all()


@bp.route("/")
@login_required
def index():
    objectives = Objective.query.order_by(Objective.ref).all()
    orphans = Indicator.query.filter(Indicator.objective_id.is_(None)).order_by(Indicator.ref).all()
    indicators = Indicator.query.filter_by(active=True).all()
    stats = {
        "objectives": len(objectives),
        "reached": sum(o.status == ObjectiveStatus.ATTEINT for o in objectives),
        "off": sum(i.state == "hors_cible" for i in indicators),
        "due": sum(i.measurement_due for i in indicators),
        "indicators": len(indicators),
    }
    return render_template("objectives/index.html", objectives=objectives, orphans=orphans, stats=stats)


# --- Objectifs (6.2) -----------------------------------------------------------
@bp.route("/nouveau", methods=["GET", "POST"])
@editor_required
def create():
    return _objective_form(None)


@bp.route("/<int:obj_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit(obj_id):
    return _objective_form(db.session.get(Objective, obj_id) or abort(404))


def _objective_form(o):
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de l'objectif est obligatoire.", "danger")
        else:
            if o is None:
                o = Objective(ref=next_ref(Objective, "OBJ", width=2))
                db.session.add(o)
            o.title = title
            for f in ("description", "actions", "resources", "evaluation"):
                setattr(o, f, request.form.get(f))
            o.owner_id = request.form.get("owner_id", type=int) or None
            o.due_date = _date(request.form.get("due_date"))
            o.status = ObjectiveStatus(request.form.get("status", "EN_COURS"))
            db.session.commit()
            flash(f"Objectif {o.ref} enregistré.", "success")
            return redirect(url_for("objectives.index"))
    return render_template("objectives/objective_form.html", o=o, users=_users(), ObjectiveStatus=ObjectiveStatus)


# --- Indicateurs (9.1) -----------------------------------------------------------
@bp.route("/indicateurs/nouveau", methods=["GET", "POST"])
@editor_required
def create_indicator():
    return _indicator_form(None)


@bp.route("/indicateurs/<int:ind_id>/modifier", methods=["GET", "POST"])
@editor_required
def edit_indicator(ind_id):
    return _indicator_form(db.session.get(Indicator, ind_id) or abort(404))


def _indicator_form(i):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        target = _float(request.form.get("target"))
        if not name or target is None:
            flash("Le nom et la cible de l'indicateur sont obligatoires.", "danger")
        else:
            alert = _float(request.form.get("alert"))
            direction = Direction(request.form.get("direction", "HAUSSE"))
            if alert is not None and ((direction == Direction.HAUSSE and alert > target) or
                                      (direction == Direction.BAISSE and alert < target)):
                flash("Le seuil d'alerte doit se situer entre la cible et les valeurs inacceptables.", "danger")
                return redirect(request.url)
            if i is None:
                i = Indicator(ref=next_ref(Indicator, "KPI", width=3, yearly=False))
                db.session.add(i)
            i.name = name
            i.target, i.alert, i.direction = target, alert, direction
            i.unit = (request.form.get("unit") or "").strip()[:24] or None
            i.frequency = Frequency(request.form.get("frequency", "MENSUELLE"))
            i.method = request.form.get("method")
            i.analyst = (request.form.get("analyst") or "").strip() or None
            i.owner_id = request.form.get("owner_id", type=int) or None
            i.objective_id = request.form.get("objective_id", type=int) or None
            i.control_id = request.form.get("control_id", type=int) or None
            i.active = bool(request.form.get("active"))
            db.session.commit()
            flash(f"Indicateur {i.ref} enregistré.", "success")
            return redirect(url_for("objectives.indicator", ind_id=i.id))
    return render_template("objectives/indicator_form.html", i=i, users=_users(),
                           objectives=Objective.query.order_by(Objective.ref).all(),
                           controls=Control.of().order_by(Control.id).all(),
                           Frequency=Frequency, Direction=Direction,
                           preset_objective=request.args.get("objectif", type=int))


@bp.route("/indicateurs/<int:ind_id>")
@login_required
def indicator(ind_id):
    i = db.session.get(Indicator, ind_id) or abort(404)
    return render_template("objectives/indicator.html", i=i)


@bp.route("/indicateurs/<int:ind_id>/mesure", methods=["POST"])
@editor_required
def add_measurement(ind_id):
    i = db.session.get(Indicator, ind_id) or abort(404)
    period = _date(request.form.get("period"))
    value = _float(request.form.get("value"))
    if period is None or value is None:
        flash("Indiquez la période et une valeur numérique.", "danger")
    else:
        db.session.add(Measurement(indicator_id=i.id, period=period, value=value,
                                   comment=(request.form.get("comment") or "").strip() or None,
                                   recorded_by_id=current_user.id))
        db.session.commit()
        db.session.refresh(i)
        state = i.evaluate(value)
        flash(f"Mesure enregistrée : {i.fmt(value)}" + {"ok": " (cible atteinte).", "alerte": " (zone d'alerte).",
                                                         "hors_cible": " : hors cible, analysez l'écart et envisagez une "
                                                                       "non-conformité."}.get(state, "."),
              "success" if state == "ok" else "warning")
    return redirect(url_for("objectives.indicator", ind_id=i.id))


@bp.route("/mesures/<int:m_id>/supprimer", methods=["POST"])
@editor_required
def delete_measurement(m_id):
    m = db.session.get(Measurement, m_id) or abort(404)
    ind_id = m.indicator_id
    db.session.delete(m)
    db.session.commit()
    flash("Mesure supprimée (tracée dans le journal d'activité).", "success")
    return redirect(url_for("objectives.indicator", ind_id=ind_id))
