"""Contexte de l'organisme : périmètre du SMSI (4.3), enjeux (4.1),
parties intéressées et leurs exigences (4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required

from app.extensions import db
from app.models import (ContextIssue, InterestedParty, Risk, IssueKind, IssueCategory,
                        PartyCategory)
from app.services import settings as settings_svc
from app.services.access import editor_required, rssi_required
from app.services.audit_trail import log_event
from app.services.refs import next_ref

bp = Blueprint("context", __name__, url_prefix="/contexte")

SCOPE_FIELDS = [
    ("scope_statement", "Énoncé du périmètre"),
    ("scope_included", "Inclus : activités, processus, sites, systèmes"),
    ("scope_excluded", "Exclusions et justifications"),
    ("scope_interfaces", "Interfaces et dépendances (activités réalisées par d'autres organismes)"),
]


def scope():
    return {k: settings_svc.get(k, "", inherit=False) for k, _ in SCOPE_FIELDS}


@bp.route("/")
@login_required
def index():
    issues = ContextIssue.query.order_by(ContextIssue.kind, ContextIssue.ref).all()
    parties = InterestedParty.query.order_by(InterestedParty.ref).all()
    return render_template("context/index.html", scope=scope(), fields=SCOPE_FIELDS, issues=issues,
                           parties=parties, scope_date=settings_svc.get("scope_updated", "", inherit=False))


@bp.route("/perimetre", methods=["GET", "POST"])
@rssi_required
def edit_scope():
    if request.method == "POST":
        from datetime import date
        old = scope()
        new = {k: (request.form.get(k) or "").strip() for k, _ in SCOPE_FIELDS}
        changes = {k: [old[k] or None, new[k] or None] for k in new if old[k] != new[k]}
        if changes:
            new["scope_updated"] = date.today().isoformat()
            settings_svc.set_many(new)
            log_event("update", "Périmètre du SMSI modifié (4.3)",
                      changes={k: [(v[0] or "")[:300] or None, (v[1] or "")[:300] or None] for k, v in changes.items()})
        flash("Périmètre enregistré.", "success")
        return redirect(url_for("context.index"))
    return render_template("context/scope_form.html", scope=scope(), fields=SCOPE_FIELDS)


# --- Enjeux (4.1) ------------------------------------------------------------
@bp.route("/enjeux/nouveau", methods=["GET", "POST"])
@editor_required
def create_issue():
    return _issue_form(None)


@bp.route("/enjeux/<int:issue_id>", methods=["GET", "POST"])
@editor_required
def edit_issue(issue_id):
    return _issue_form(db.session.get(ContextIssue, issue_id) or abort(404))


def _issue_form(i):
    risks = Risk.query.order_by(Risk.ref).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        if not title:
            flash("L'intitulé de l'enjeu est obligatoire.", "danger")
        else:
            if i is None:
                i = ContextIssue(ref=next_ref(ContextIssue, "ENJ", width=3, yearly=False))
                db.session.add(i)
            i.title = title
            i.kind = IssueKind(request.form.get("kind", "EXTERNE"))
            i.category = IssueCategory(request.form.get("category", "ORGANISATIONNEL"))
            i.description = request.form.get("description")
            i.effect = request.form.get("effect")
            i.response = request.form.get("response")
            i.active = bool(request.form.get("active"))
            ids = request.form.getlist("risks", type=int)
            i.risks = Risk.query.filter(Risk.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash(f"Enjeu {i.ref} enregistré.", "success")
            return redirect(url_for("context.index") + "#enjeux")
    return render_template("context/issue_form.html", i=i, risks=risks, IssueKind=IssueKind, IssueCategory=IssueCategory)


# --- Parties intéressées (4.2) -------------------------------------------------
@bp.route("/parties/nouvelle", methods=["GET", "POST"])
@editor_required
def create_party():
    return _party_form(None)


@bp.route("/parties/<int:party_id>", methods=["GET", "POST"])
@editor_required
def edit_party(party_id):
    return _party_form(db.session.get(InterestedParty, party_id) or abort(404))


def _party_form(p):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Le nom de la partie intéressée est obligatoire.", "danger")
        else:
            if p is None:
                p = InterestedParty(ref=next_ref(InterestedParty, "PI", width=3, yearly=False))
                db.session.add(p)
            p.name = name
            p.category = PartyCategory(request.form.get("category", "CLIENT"))
            p.expectations = request.form.get("expectations")
            p.retained = bool(request.form.get("retained"))
            p.response = request.form.get("response")
            p.influence = min(max(request.form.get("influence", type=int) or 2, 1), 3)
            db.session.commit()
            flash(f"Partie intéressée {p.ref} enregistrée.", "success")
            return redirect(url_for("context.index") + "#parties")
    return render_template("context/party_form.html", p=p, PartyCategory=PartyCategory)
