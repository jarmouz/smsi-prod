"""Lecture et acceptation des politiques par les personnes (3.10).

Un document approuvé marqué « acceptation requise » doit être lu et accepté par chaque compte
concerné (tous les comptes actifs ou certains rôles), dans un délai après approbation. Chaque
nouvelle version approuvée demande une nouvelle acceptation. Exigences : 5.2 et 7.3 des normes
de systèmes de management (politique communiquée, personnes conscientes de la politique),
ISO/IEC 27001 A.5.1 et A.6.3.
"""
from datetime import datetime

from flask import g, has_request_context, request

from app.extensions import db


def required_docs():
    from app.models import Document, DocStatus
    return Document.query.filter(Document.ack_required.is_(True), Document.status == DocStatus.APPROUVE) \
        .order_by(Document.ref).all()


def pending_for(user):
    """Documents que l'utilisateur doit encore lire et accepter (version en vigueur)."""
    if user is None or not user.is_authenticated or user.is_readonly:
        return []
    from app.models import PolicyAcceptance
    done = {(a.document_id, a.version) for a in PolicyAcceptance.query.filter_by(user_id=user.id).all()}
    out = []
    for d in required_docs():
        roles = d.ack_role_list
        if (not roles or user.role.value in roles) and (d.id, d.version) not in done:
            out.append(d)
    return out


def pending_count(user):
    if not has_request_context():
        return len(pending_for(user))
    if "_policy_pending" not in g:
        g._policy_pending = len(pending_for(user))
    return g._policy_pending


def accept(doc, user):
    from app.models import PolicyAcceptance
    if not doc.ack_active or user.is_readonly:
        return None
    acc = PolicyAcceptance.query.filter_by(document_id=doc.id, user_id=user.id, version=doc.version).first()
    if acc is None:
        fwd = request.headers.get("X-Forwarded-For", "") if has_request_context() else ""
        ip = (fwd.split(",")[0].strip() or (request.remote_addr if has_request_context() else "") or "")[:64]
        acc = PolicyAcceptance(document_id=doc.id, user_id=user.id, version=doc.version,
                               accepted_at=datetime.utcnow(), ip=ip or None)
        db.session.add(acc)
    return acc


def summary():
    """Vue d'ensemble : [(document, statut)] et totaux (attendues, faites, en retard)."""
    rows = [(d, d.ack_status()) for d in required_docs()]
    expected = sum(len(st["audience"]) for _, st in rows)
    done = sum(len(st["done"]) for _, st in rows)
    return {"rows": rows, "expected": expected, "done": done, "pending": expected - done,
            "rate": round(100 * done / expected) if expected else 100,
            "overdue_docs": sum(1 for _, st in rows if st["overdue"]),
            "overdue": sum(len(st["pending"]) for _, st in rows if st["overdue"])}


def init_app(app):
    @app.context_processor
    def _ctx():
        from flask_login import current_user
        return {"policy_pending_count": lambda: pending_count(current_user)}
