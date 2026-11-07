"""Piste d'audit automatique.

Après chaque flush, les créations / modifications / suppressions des modèles
rattachés à une organisation sont enregistrées dans activity_logs avec les
valeurs avant / après (y compris les liens risque<->mesure). L'insertion passe
par la connexion du flush : elle est atomique avec la modification journalisée.
"""
import enum
from contextlib import contextmanager
from datetime import date, datetime

from flask import g, has_request_context, request
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import ActivityLog, TenantMixin, User

# Champs techniques ou secrets : jamais journalisés en clair
IGNORED = {"updated_at", "created_at", "failed_logins", "locked_until", "totp_last_step", "password_changed_at",
           "last_digest_at"}
SECRET = {"password_hash": "mot de passe modifié", "totp_secret": "double authentification modifiée",
          "recovery_codes": "codes de secours régénérés"}
MAX_LEN = 400

ENTITY_LABELS = {
    "Risk": "Risque", "RiskAction": "Action de traitement", "RiskLink": "Lien d'un risque", "PolicyAcceptance": "Acceptation d'une politique",
    "TrustRequest": "Demande d'accès (page de confiance)", "Control": "Mesure", "Audit": "Audit", "Finding": "Constat",
    "CorrectiveAction": "Action corrective", "ManagementReview": "Revue de direction",
    "ReviewAction": "Action de revue", "Document": "Document", "DocumentVersion": "Version de document",
    "Evidence": "Preuve", "Attachment": "Pièce jointe", "Asset": "Actif", "Incident": "Incident",
    "AwarenessAction": "Sensibilisation", "User": "Utilisateur",
    "ContextIssue": "Enjeu", "InterestedParty": "Partie intéressée", "Objective": "Objectif",
    "Indicator": "Indicateur", "Measurement": "Mesure d'indicateur", "NonConformity": "Non-conformité",
    "Supplier": "Fournisseur", "Requirement": "Exigence",
    "AuditPlanItem": "Programme d'audit", "CompetenceRequirement": "Compétence requise",
    "CompetenceRecord": "Preuve de compétence", "BusinessProcess": "Activité (BIA)",
    "ContinuityTest": "Exercice de continuité", "ChangeRequest": "Changement",
    # Référentiels et modules par norme (phases 0 à 2)
    "OrgFramework": "Référentiel de l'organisation", "FrameworkLink": "Rattachement à une norme",
    "ProcessingActivity": "Traitement de données", "SubjectRequest": "Demande d'une personne",
    "AiSystem": "Système d'IA", "AiImpactAssessment": "Étude d'impact IA",
    "ContinuityPlan": "Plan de continuité", "ItService": "Service", "ServiceMeasure": "Mesure de service",
    "Problem": "Problème", "Release": "Mise en production",
    "QmsProcess": "Processus", "CustomerSurvey": "Mesure de satisfaction", "Complaint": "Réclamation client",
}
FIELD_LABELS = {
    "title": "Titre", "name": "Nom", "description": "Description", "status": "Statut", "owner_id": "Propriétaire",
    "applicable": "Applicable", "justification": "Justification", "implementation": "Mise en œuvre",
    "inherit": "Évaluée dans le socle commun", "common_id": "Exigence du socle commun",
    "note": "Note", "progress": "Avancement (%)", "entity_type": "Type d'élément", "entity_id": "Élément",
    "reassess_at": "Réévaluation demandée le", "ack_required": "Acceptation requise", "ack_roles": "Rôles concernés",
    "ack_days": "Délai d'acceptation (jours)", "trust_visibility": "Page de confiance", "trust_public": "Affiché sur la page de confiance",
    "expires_at": "Accès jusqu'au", "decided_by_id": "Décidé par", "reassess_reason": "Motif de réévaluation", "control_id": "Mesure", "risk_id": "Risque", "completed_at": "Réalisée le",
    "likelihood": "Vraisemblance", "impact": "Impact", "residual_likelihood": "Vraisemblance résiduelle",
    "residual_impact": "Impact résiduel", "treatment": "Traitement", "controls": "Mesures",
    "version": "Version", "approved_at": "Date d'approbation", "next_review_at": "Prochaine revue",
    "role": "Rôle", "email": "E-mail", "is_active_flag": "Actif", "assignee_id": "Responsable",
    "severity": "Gravité", "due_date": "Échéance", "accepted_by_id": "Accepté par",
    "acceptance_note": "Justification d'acceptation", "acceptance_until": "Acceptation valable jusqu'au",
    "kind": "Type", "category": "Catégorie", "effect": "Effet sur le SMSI", "response": "Réponse",
    "expectations": "Attentes", "retained": "Retenue", "risks": "Risques", "target": "Cible", "alert": "Seuil d'alerte",
    "value": "Valeur", "period": "Période", "comment": "Commentaire", "frequency": "Fréquence",
    "root_cause": "Cause racine", "correction": "Correction", "extent": "NC similaires", "isms_changes": "Modifications du SMSI",
    "criticality": "Criticité", "data_access": "Accès aux données", "security_clauses": "Clauses de sécurité",
    "dpa": "Accord de traitement", "assessment_result": "Évaluation", "next_assessment": "Prochaine évaluation",
    "last_assessment": "Dernière évaluation", "obligation": "Obligation", "req_type": "Type d'exigence",
    "source": "Origine / source", "next_review": "Prochaine revue",
    "quarter": "Trimestre", "auditor_id": "Auditeur", "audit_id": "Audit", "users": "Personnes",
    "expires_at": "Expire le", "obtained_at": "Obtenue le", "mtpd_hours": "DMIA (h)", "rto_hours": "RTO (h)",
    "rpo_hours": "RPO (h)", "achieved_rto_hours": "RTO atteint (h)", "result": "Résultat", "assets": "Actifs",
    "security_impact": "Impact sécurité", "risk_level": "Risque", "rollback": "Retour arrière",
    "digest_frequency": "Récapitulatif e-mail",
    # Référentiels
    "framework_id": "Norme", "enabled": "Activée", "scope": "Périmètre", "target_date": "Certification visée",
    "certifier": "Organisme de certification", "certified_on": "Certifiée le",
    # Vie privée (ISO 27701)
    "purpose": "Finalité", "legal_basis": "Base juridique", "legal_basis_detail": "Précisions (base juridique)",
    "data_subjects": "Personnes concernées", "data_categories": "Catégories de données",
    "sensitive_data": "Données sensibles", "sensitive_detail": "Précisions (données sensibles)",
    "recipients": "Destinataires", "transfers": "Transferts hors du pays", "transfer_detail": "Pays et garanties",
    "retention": "Conservation", "security_measures": "Mesures de sécurité", "dpia": "Analyse d'impact",
    "dpia_date": "Date de l'analyse d'impact", "last_review": "Dernière revue", "suppliers": "Fournisseurs",
    "request_type": "Type de demande", "requester": "Demandeur", "channel": "Canal", "received_on": "Reçue le",
    "due_on": "Échéance", "processing_id": "Traitement", "identity_verified": "Identité vérifiée",
    "handled_by_id": "Traitée par", "closed_on": "Clôturée le", "notes": "Notes",
    # Intelligence artificielle (ISO 42001)
    "intended_use": "Utilisation prévue", "ai_type": "Type de système", "provider": "Modèle / éditeur",
    "supplier_id": "Fournisseur", "data_used": "Données utilisées", "personal_data": "Données personnelles",
    "affected_parties": "Personnes concernées", "automated_decisions": "Décisions automatisées",
    "human_oversight": "Supervision humaine", "lifecycle": "Cycle de vie", "assessed_on": "Date de l'étude",
    "assessor_id": "Réalisée par", "impacts_individuals": "Impacts sur les personnes",
    "impacts_society": "Impacts sur la société", "impact_level": "Niveau d'impact", "measures": "Mesures",
    "residual": "Impact résiduel", "decision": "Décision",
    # Continuité (ISO 22301)
    "plan_type": "Type de plan", "activation": "Déclenchement", "response_team": "Structure de réponse",
    "alerting": "Alerte et communication", "procedures": "Procédures", "resources": "Ressources",
    "document_id": "Document", "processes": "Activités", "tests": "Exercices / tests",
    # Services informatiques (ISO/IEC 20000-1)
    "customers": "Clients", "support_hours": "Plage de service", "availability_target": "Disponibilité visée (%)",
    "response_time": "Délais de prise en charge", "resolution_time": "Délais de résolution",
    "sla_reference": "Accord de référence", "sla_review": "Revue de l'accord", "availability": "Disponibilité (%)",
    "incidents": "Incidents", "sla_breaches": "Dépassements", "service_id": "Service", "priority": "Priorité",
    "workaround": "Contournement", "resolution": "Résolution", "change_id": "Changement correctif",
    "opened_on": "Ouvert le", "resolved_on": "Résolu le", "planned_on": "Prévue le", "deployed_on": "Déployée le",
    "content": "Contenu", "rollback_plan": "Plan de retour arrière", "changes": "Changements",
    # Qualité (ISO 9001)
    "risk_domain": "Domaine", "nature": "Nature", "nc_kind": "Type de non-conformité", "product": "Produit ou service",
    "disposition": "Traitement de l'élément", "process_type": "Type de processus", "pilot_id": "Pilote",
    "inputs": "Éléments d'entrée", "outputs": "Éléments de sortie", "beneficiaries": "Bénéficiaires",
    "activities": "Activités", "indicators": "Indicateurs", "documents": "Documents", "next_processes": "Processus en aval",
    "sort_order": "Ordre", "method": "Méthode", "conducted_on": "Date", "respondents": "Répondants", "score": "Résultat",
    "strengths": "Points forts", "improvements": "Axes d'amélioration", "actions": "Actions", "customer": "Client",
    "analysis": "Analyse", "justified": "Fondée", "customer_satisfied": "Client satisfait",
    "nonconformity_id": "Non-conformité",
}


@contextmanager
def paused():
    """Suspend la journalisation (chargements de masse : démo, migrations)."""
    prev = g.get("audit_paused")
    g.audit_paused = True
    try:
        yield
    finally:
        g.audit_paused = prev


def _actor():
    if has_request_context():
        from flask_login import current_user
        try:
            if current_user.is_authenticated:
                return current_user.id, current_user.name
        except Exception:  # noqa: BLE001
            pass
    return None, "Système"


def _ip():
    if not has_request_context():
        return None
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or request.headers.get("X-Real-IP") or request.remote_addr or "")[:64]


def label_of(obj):
    for attr in ("ref", "email", "title", "name", "filename"):
        v = getattr(obj, attr, None)
        if v:
            if attr == "ref" and getattr(obj, "title", None):
                return f"{v} - {obj.title}"[:300]
            return str(v)[:300]
    return f"#{getattr(obj, 'id', '?')}"


def _fmt(sess, key, value):
    if value is None or value == "":
        return None
    if key.endswith("_id") and isinstance(value, int) and key in ("owner_id", "assignee_id", "lead_auditor_id", "accepted_by_id",
                                                                    "uploaded_by_id", "approved_by_id", "recorded_by_id",
                                                                    "effectiveness_by_id", "auditor_id", "user_id",
                                                                    "requested_by_id", "handled_by_id", "assessor_id", "pilot_id"):
        u = sess.get(User, value)
        return u.name if u else f"#{value}"
    if isinstance(value, enum.Enum):
        return getattr(value, "label", value.value)
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    s = str(value)
    return s if len(s) <= MAX_LEN else s[:MAX_LEN] + "…"


def _changes(sess, obj, mode):
    out = {}
    state = inspect(obj)
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in IGNORED or key in ("id", "organization_id"):
            continue
        hist = state.attrs[key].history
        if key in SECRET:
            if mode == "update" and hist.has_changes():
                out[key] = [None, SECRET[key]]
            continue
        if mode == "create":
            new = _fmt(sess, key, getattr(obj, key))
            if new is not None:
                out[key] = [None, new]
        elif mode == "update" and hist.has_changes():
            old = _fmt(sess, key, hist.deleted[0] if hist.deleted else None)
            new = _fmt(sess, key, hist.added[0] if hist.added else None)
            if old != new:
                out[key] = [old, new]
    # Collections many-to-many (risque <-> mesures, preuve <-> mesures)
    if mode == "update":
        for rel in state.mapper.relationships:
            if rel.secondary is None:
                continue
            hist = state.attrs[rel.key].history
            if hist.added or hist.deleted:
                out[rel.key] = [", ".join(sorted(label_of(o).split(" - ")[0] for o in hist.deleted)) or None,
                                ", ".join(sorted(label_of(o).split(" - ")[0] for o in hist.added)) or None]
    return out


def _collect(sess, flush_context):
    if g.get("audit_paused"):
        return
    uid, uname = _actor()
    ip = _ip()
    rows = []
    with sess.no_autoflush:
        for mode, objs in (("create", sess.new), ("update", sess.dirty), ("delete", sess.deleted)):
            for obj in objs:
                if not isinstance(obj, TenantMixin) or isinstance(obj, ActivityLog):
                    continue
                if mode == "update" and not sess.is_modified(obj, include_collections=True):
                    continue
                changes = _changes(sess, obj, mode) if mode != "delete" else {}
                if mode == "update" and not changes:
                    continue
                rows.append({
                    "organization_id": obj.organization_id, "created_at": datetime.utcnow(),
                    "user_id": uid, "user_name": uname, "action": mode,
                    "entity_type": type(obj).__name__, "entity_id": obj.id, "entity_ref": label_of(obj),
                    "changes": changes or None, "ip": ip,
                })
    if rows:
        sess.connection().execute(ActivityLog.__table__.insert(), rows)


def log_event(action, summary, org_id=None, user=None, entity=None, changes=None):
    """Événement explicite (connexion, export, approbation...). Commit inclus."""
    from app.services.tenancy import current_org_id
    if user is None:
        uid, uname = _actor()
    else:
        uid, uname = user.id, user.name
    oid = org_id or (entity.organization_id if entity is not None else None) or current_org_id() \
        or (user.organization_id if user is not None else None)
    if oid is None:
        return
    db.session.add(ActivityLog(
        organization_id=oid, user_id=uid, user_name=uname, action=action, summary=summary,
        entity_type=type(entity).__name__ if entity is not None else None,
        entity_id=getattr(entity, "id", None), entity_ref=label_of(entity) if entity is not None else None,
        changes=changes, ip=_ip()))
    db.session.commit()


def history(entity, limit=30):
    return (ActivityLog.query.filter_by(entity_type=type(entity).__name__, entity_id=entity.id)
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit).all())


def init_app(app):
    event.listen(Session, "after_flush", _collect)

    @app.context_processor
    def _inject():
        return {"activity_history": history, "ENTITY_LABELS": ENTITY_LABELS, "FIELD_LABELS": FIELD_LABELS}
