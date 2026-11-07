"""Page de confiance publique (3.11) et sa gestion par le RSSI.

Public (sans connexion) : /confiance/<slug>, demande d'accès, téléchargements.
Gestion (RSSI) : /confiance/gestion/... - réglages, documents publiés, sous-traitants,
demandes d'accès (accorder, refuser, révoquer).
"""
import io
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file, g
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Organization, Document, DocStatus, Supplier, TrustRequest
from app.services import tenancy, trust as trust_svc
from app.services.access import rssi_required

bp = Blueprint("trust", __name__, url_prefix="/confiance")


# --------------------------------------------------------------------------- public
def _public_org(slug):
    """Organisation de la page : fixée explicitement (pas de filtre d'organisation sans connexion)."""
    org = Organization.query.filter_by(slug=slug, is_active=True).first() or abort(404)
    tenancy.set_current_org(org.id)
    g.org = org
    cfg = trust_svc.config()
    preview = (current_user.is_authenticated and current_user.organization_id == org.id
               and current_user.role.value == "RSSI")
    if not cfg["enabled"] and not preview:
        abort(404)
    return org, cfg, preview and not cfg["enabled"]


def _ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.remote_addr or "")[:64]


@bp.route("/<slug>")
def page(slug):
    org, cfg, preview = _public_org(slug)
    public_docs, request_docs = trust_svc.documents()
    return render_template("trust/public.html", org=org, cfg=cfg, preview=preview,
                           certs=trust_svc.certifications(cfg),
                           controls=trust_svc.controls(cfg) if cfg["show_controls"] else [],
                           public_docs=public_docs, request_docs=request_docs,
                           subprocessors=trust_svc.subprocessors(), file_of=trust_svc.file_of,
                           updated=datetime.utcnow())


@bp.route("/<slug>/demande", methods=["POST"])
def ask(slug):
    org, cfg, _ = _public_org(slug)
    f = request.form
    back = url_for("trust.page", slug=slug) + "#documents"
    if f.get("website"):                               # champ piège : robots
        return redirect(back)
    name, email = (f.get("name") or "").strip()[:120], (f.get("email") or "").strip().lower()[:255]
    if not name or "@" not in email or "." not in email.split("@")[-1] or not f.get("consent"):
        flash("Indiquez votre nom, une adresse e-mail valide et acceptez l'usage de vos données pour cette demande.",
              "danger")
        return redirect(back)
    since = datetime.utcnow() - timedelta(days=1)
    if TrustRequest.query.filter(TrustRequest.email == email, TrustRequest.created_at >= since).count() >= 3:
        flash("Votre demande a déjà été enregistrée : elle sera traitée prochainement.", "warning")
        return redirect(back)
    req = TrustRequest(name=name, email=email, company=(f.get("company") or "").strip()[:200] or None,
                       reason=(f.get("reason") or "").strip()[:2000] or None, ip=_ip())
    db.session.add(req)
    db.session.commit()
    if cfg["contact"]:
        from app.services import mailer
        mailer.send_email(cfg["contact"], f"Demande d'accès à la page de confiance - {req.name}",
                          f"<p>{req.name} ({req.email}{', ' + req.company if req.company else ''}) demande l'accès "
                          f"aux documents réservés de la page de confiance de {org.name}.</p>"
                          f"<p>Motif : {req.reason or '-'}</p>"
                          f"<p><a href=\"{url_for('trust.manage', _external=True)}#demandes\">Traiter la demande</a></p>")
    flash("Merci : votre demande d'accès est enregistrée. Vous recevrez un lien par e-mail si elle est accordée.",
          "success")
    return redirect(back)


def _send(doc):
    att = trust_svc.file_of(doc) or abort(404)
    from app.services import attachments as att_svc
    try:
        data = att_svc.read_bytes(att)
    except Exception:  # noqa: BLE001
        abort(404)
    return send_file(io.BytesIO(data), as_attachment=True, download_name=att.filename,
                     mimetype=att.content_type or "application/octet-stream")


@bp.route("/<slug>/documents/<int:doc_id>")
def public_doc(slug, doc_id):
    _public_org(slug)
    return _send(trust_svc.published_doc(doc_id, "PUBLIC") or abort(404))


@bp.route("/<slug>/acces/<token>")
def access(slug, token):
    org, cfg, _ = _public_org(slug)
    req = trust_svc.request_from_token(token, org.id)
    if req is None:
        return render_template("trust/access.html", org=org, cfg=cfg, req=None, docs=[], token=token), 403
    public_docs, request_docs = trust_svc.documents()
    return render_template("trust/access.html", org=org, cfg=cfg, req=req, docs=public_docs + request_docs,
                           token=token, file_of=trust_svc.file_of)


@bp.route("/<slug>/acces/<token>/documents/<int:doc_id>")
def access_doc(slug, token, doc_id):
    org, _, _ = _public_org(slug)
    req = trust_svc.request_from_token(token, org.id) or abort(403)
    doc = trust_svc.published_doc(doc_id, "DEMANDE") or trust_svc.published_doc(doc_id, "PUBLIC") or abort(404)
    trust_svc.touch(req)
    db.session.commit()
    return _send(doc)


# --------------------------------------------------------------------------- gestion
@bp.route("/gestion", methods=["GET", "POST"])
@login_required
@rssi_required
def manage():
    from app.services import frameworks as fw_svc
    if request.method == "POST":
        f = request.form
        active = {x.code for x in fw_svc.active()}
        trust_svc.save({"enabled": bool(f.get("enabled")), "title": (f.get("title") or "").strip(),
                        "intro": (f.get("intro") or "").strip(), "contact": (f.get("contact") or "").strip(),
                        "frameworks": [c for c in f.getlist("frameworks") if c in active],
                        "show_controls": bool(f.get("show_controls")), "noindex": bool(f.get("noindex"))})
        for d in Document.query.all():
            v = f.get(f"doc_{d.id}")
            if v is not None:
                d.trust_visibility = v if v in ("PUBLIC", "DEMANDE") else None
        if f.get("sup_present"):
            chosen = set(f.getlist("suppliers", type=int))
            for s in Supplier.query.all():
                s.trust_public = s.id in chosen
        db.session.commit()
        from app.services.audit_trail import log_event
        log_event("admin", "Page de confiance mise à jour")
        flash("Page de confiance enregistrée.", "success")
        return redirect(url_for("trust.manage"))
    cfg = trust_svc.config()
    docs = Document.query.filter(Document.status != DocStatus.OBSOLETE).order_by(Document.ref).all()
    reqs = TrustRequest.query.order_by(TrustRequest.created_at.desc()).limit(200).all()
    return render_template("trust/manage.html", cfg=cfg, fws=fw_svc.active(), docs=docs,
                           suppliers=Supplier.query.order_by(Supplier.name).all(), reqs=reqs,
                           org=tenancy.current_org(), file_of=trust_svc.file_of, token_for=trust_svc.token_for)


@bp.route("/gestion/demandes/<int:req_id>/<action>", methods=["POST"])
@login_required
@rssi_required
def decide(req_id, action):
    from app.services.audit_trail import log_event
    req = db.session.get(TrustRequest, req_id) or abort(404)
    if action not in ("accorder", "refuser", "revoquer"):
        abort(400)
    req.decided_by_id, req.decided_at = current_user.id, datetime.utcnow()
    if action == "accorder":
        days = max(1, min(365, request.form.get("days", type=int) or 30))
        req.status, req.expires_at = "ACCORDEE", datetime.utcnow() + timedelta(days=days)
    elif action == "refuser":
        req.status, req.expires_at = "REFUSEE", None
    else:
        req.status, req.expires_at = "REVOQUEE", None
    db.session.commit()
    log_event("admin", f"Page de confiance : accès {req.status_label.lower()} à {req.name} ({req.email})")
    if action == "accorder":
        org = tenancy.current_org()
        link = url_for("trust.access", slug=org.slug, token=trust_svc.token_for(req), _external=True)
        from app.services import mailer
        mailer.send_email(req.email, f"Accès aux documents de sécurité - {org.name}",
                          f"<p>Bonjour {req.name},</p><p>{org.name} vous donne accès à ses documents de sécurité "
                          f"jusqu'au {req.expires_at:%d/%m/%Y} :</p><p><a href=\"{link}\">{link}</a></p>"
                          f"<p>Ce lien est personnel : merci de ne pas le diffuser.</p>")
        flash(f"Accès accordé jusqu'au {req.expires_at:%d/%m/%Y}. Lien envoyé par e-mail (si l'envoi est configuré) "
              f"et copiable ci-dessous.", "success")
    else:
        flash(f"Demande {req.status_label.lower()}.", "success")
    return redirect(url_for("trust.manage") + "#demandes")
