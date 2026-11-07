"""Maillage SMI (3.8) : liens entre un risque et les éléments des autres modules.

Un seul registre décrit chaque type d'élément liable (modèle, libellé, page, norme dont le
module dépend). Les liens sont stockés dans RiskLink (entity_type = nom de la classe).

Clause 8.2 des normes : l'appréciation des risques est refaite « lorsque des changements
significatifs sont proposés ou surviennent ». Lier un incident, une non-conformité ou un
changement à un risque demande donc sa réévaluation (Risk.flag_reassess), visible sur la
fiche, dans le registre, les relances et les preuves de l'exigence 8.2.
"""
from flask import url_for
from sqlalchemy import event, text

from app.extensions import db


def _types():
    from app.models.ai_system import AiSystem, AiImpactAssessment
    from app.models.privacy import ProcessingActivity
    from app.models.operations import BusinessProcess, ChangeRequest
    from app.models.service_mgmt import ContinuityPlan, ItService
    from app.models.governance import Supplier, NonConformity
    from app.models.asset import Incident
    # type -> (modèle, libellé, (endpoint, paramètre), norme requise ou None, déclenche une réévaluation)
    return {
        "Incident": (Incident, "Incident", ("incidents.detail", "incident_id"), None, True),
        "NonConformity": (NonConformity, "Non-conformité", ("nonconformities.detail", "nc_id"), None, True),
        "ChangeRequest": (ChangeRequest, "Changement", ("changes.detail", "change_id"), None, True),
        "Supplier": (Supplier, "Fournisseur", ("suppliers.detail", "sup_id"), None, False),
        "BusinessProcess": (BusinessProcess, "Activité (BIA)", ("continuity.edit_process", "proc_id"), None, False),
        "ContinuityPlan": (ContinuityPlan, "Plan de continuité", ("bcplans.detail", "pid"), "ISO22301", False),
        "ItService": (ItService, "Service IT", ("itsm.detail", "sid"), "ISO20000", False),
        "ProcessingActivity": (ProcessingActivity, "Traitement de données personnelles", ("privacy.detail", "pid"),
                               "ISO27701", False),
        "AiSystem": (AiSystem, "Système d'IA", ("aisystems.detail", "sid"), "ISO42001", False),
        "AiImpactAssessment": (AiImpactAssessment, "Étude d'impact IA", ("aisystems.assessment_edit", "aid"),
                               "ISO42001", False),
    }


TYPES = None


def types():
    global TYPES
    if TYPES is None:
        TYPES = _types()
    return TYPES


def label_of(etype):
    return types()[etype][1] if etype in types() else etype


def available_types():
    """Types proposés : modules communs + modules des normes actives."""
    from app.services import frameworks as fw_svc
    codes = {f.code for f in fw_svc.active()}
    return [k for k, v in types().items() if v[3] is None or v[3] in codes]


def name_of(obj):
    return getattr(obj, "name", None) or getattr(obj, "title", None) or ""


def url_of(etype, obj):
    endpoint, param = types()[etype][2]
    return url_for(endpoint, **{param: obj.id})


def entity_of(link):
    t = types().get(link.entity_type)
    return db.session.get(t[0], link.entity_id) if t else None


def links_for_risk(risk):
    """[(libellé du type, [(lien, objet, url)])] dans l'ordre du registre ; liens orphelins ignorés."""
    out = []
    for etype, (model, label, *_rest) in types().items():
        rows = []
        for link in sorted((l for l in risk.links if l.entity_type == etype), key=lambda l: l.entity_id):
            obj = entity_of(link)
            if obj is not None:
                rows.append((link, obj, url_of(etype, obj)))
        if rows:
            out.append((label, rows))
    return out


def risks_for(entity):
    """[(lien, risque)] liés à un élément d'un autre module."""
    from app.models import Risk, RiskLink
    etype = type(entity).__name__
    rows = (RiskLink.query.filter_by(entity_type=etype, entity_id=entity.id)
            .join(Risk, Risk.id == RiskLink.risk_id).order_by(Risk.ref).all())
    return [(l, l.risk) for l in rows]


def candidates():
    """Éléments liables depuis la fiche d'un risque : [(libellé du type, [(valeur, libellé)])]."""
    out = []
    for etype in available_types():
        model, label = types()[etype][0], types()[etype][1]
        objs = sorted(model.query.all(), key=lambda o: getattr(o, "ref", "") or "", reverse=etype in
                      ("Incident", "NonConformity", "ChangeRequest"))
        if objs:
            out.append((label, [(f"{etype}:{o.id}", f"{getattr(o, 'ref', '')} - {name_of(o)}"[:110]) for o in objs]))
    return out


def add(risk, etype, eid):
    """Crée le lien (sans doublon). Retourne (lien ou None, message d'erreur ou None)."""
    from app.models import RiskLink
    if etype not in types():
        return None, "Type d'élément inconnu."
    obj = db.session.get(types()[etype][0], eid)
    if obj is None:
        return None, "Élément introuvable."
    existing = next((l for l in risk.links if l.entity_type == etype and l.entity_id == eid), None)
    if existing:
        return existing, None
    link = RiskLink(entity_type=etype, entity_id=eid)
    risk.links.append(link)
    if types()[etype][4] and risk.status.is_open:
        risk.flag_reassess(f"{label_of(etype)} {getattr(obj, 'ref', '')} lié".strip())
    return link, None


def init_app(app):
    @app.context_processor
    def _ctx():
        def risk_choices():
            from app.models import Risk
            return Risk.query.order_by(Risk.ref).all()
        return {"risks_for": risks_for, "risk_link_types": types, "risk_choices": risk_choices,
                "entity_type_of": lambda obj: type(obj).__name__}

    # Suppression d'un élément lié : ses liens disparaissent avec lui (pas de lien orphelin)
    with app.app_context():
        for etype, (model, *_rest) in types().items():
            def _cleanup(mapper, connection, target, _etype=etype):
                connection.execute(text("DELETE FROM risk_links WHERE entity_type = :t AND entity_id = :i"),
                                   {"t": _etype, "i": target.id})
            if not event.contains(model, "after_delete", _cleanup):
                event.listen(model, "after_delete", _cleanup)
