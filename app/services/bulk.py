"""Actions en masse sur les registres (3.18).

La suppression est réservée au RSSI et passe par un écran de confirmation. Elle ne contourne aucune
protection : un élément encore référencé est bloqué, et un enregistrement clos à conserver
(ISO 7.5.3) n'est supprimé que sur décision explicite. Chaque suppression laisse une copie au journal.
"""
import enum
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Optional

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
import app.models as M
from app.services.audit_trail import ENTITY_LABELS, FIELD_LABELS, label_of, log_event

MAX_IDS = 2000
CONFIRM_WORD = "SUPPRIMER"
_HIDDEN = {"id", "organization_id", "secret_enc", "token_hash"}


def _closed(*values):
    def check(o):
        return "Enregistrement clos, à conserver (ISO 7.5.3)." if o.status.value in values else None
    return check


def _risk(o):
    return "Risque formellement accepté, à conserver." if o.accepted_at else None


def _document(o):
    return "Document approuvé : passez-le d'abord en obsolète, ou confirmez." if o.status.value == "APPROUVE" else None


def _asset_hard(o):
    return f"Suivi par le connecteur {o.connector.name} : il serait recréé au prochain passage." if o.connector_id and o.connector else None


@dataclass
class Spec:
    model: type
    label: str
    protected: Optional[Callable] = None        # enregistrement à conserver : levable par le RSSI
    hard: Optional[Callable] = None             # blocage non levable
    attach: Optional[str] = None                # clé des pièces jointes
    status: Optional[type] = None               # changement de statut en masse (cycles sans circuit)


def registry():
    return {
        "actifs": Spec(M.Asset, "actifs", hard=_asset_hard, status=M.AssetStatus),
        "risques": Spec(M.Risk, "risques", protected=_risk),
        "actions-risque": Spec(M.RiskAction, "actions de traitement"),
        "incidents": Spec(M.Incident, "incidents", protected=_closed("RESOLU", "CLOTURE"), attach="incident"),
        "non-conformites": Spec(M.NonConformity, "non-conformités", protected=_closed("CLOTUREE")),
        "audits": Spec(M.Audit, "audits", protected=_closed("TERMINE"), attach="audit"),
        "revues": Spec(M.ManagementReview, "revues de direction", protected=_closed("TENUE"), attach="review"),
        "documents": Spec(M.Document, "documents", protected=_document, attach="document"),
        "preuves": Spec(M.Evidence, "preuves", attach="evidence"),
        "fournisseurs": Spec(M.Supplier, "fournisseurs", attach="supplier", status=M.SupplierStatus),
        "exigences": Spec(M.Requirement, "exigences"),
        "sensibilisation": Spec(M.AwarenessAction, "actions de sensibilisation", attach="awareness"),
        "changements": Spec(M.ChangeRequest, "changements", protected=_closed("REALISE", "CLOTURE"), attach="change"),
        "competences": Spec(M.CompetenceRequirement, "compétences requises"),
        "preuves-competence": Spec(M.CompetenceRecord, "preuves de compétence", attach="competence"),
        "enjeux": Spec(M.ContextIssue, "enjeux"),
        "parties": Spec(M.InterestedParty, "parties intéressées"),
        "activites": Spec(M.BusinessProcess, "activités (BIA)"),
        "exercices": Spec(M.ContinuityTest, "exercices de continuité", attach="continuity"),
        "traitements": Spec(M.ProcessingActivity, "traitements", attach="processing"),
        "demandes-personnes": Spec(M.SubjectRequest, "demandes des personnes", protected=_closed("CLOTUREE", "REJETEE")),
        "systemes-ia": Spec(M.AiSystem, "systèmes d'IA", attach="aisystem"),
        "plans-continuite": Spec(M.ContinuityPlan, "plans de continuité", attach="bcplan"),
        "services": Spec(M.ItService, "services", attach="itservice"),
        "problemes": Spec(M.Problem, "problèmes", protected=_closed("RESOLU", "CLOS")),
        "mises-en-production": Spec(M.Release, "mises en production", protected=_closed("DEPLOYEE", "RETOUR_ARRIERE")),
        "reclamations": Spec(M.Complaint, "réclamations", protected=_closed("CLOTUREE", "REJETEE")),
        "satisfaction": Spec(M.CustomerSurvey, "mesures de satisfaction"),
    }


def owner_attr(model):
    for attr in ("owner_id", "assignee_id"):
        if hasattr(model, attr):
            return attr
    return None


def load(spec, ids):
    """Objets de l'organisation courante (filtre automatique) parmi les identifiants reçus."""
    return spec.model.query.filter(spec.model.id.in_(ids[:MAX_IDS])).all() if ids else []


def _class_label(table):
    for m in db.Model.registry.mappers:
        if m.local_table is table:
            return ENTITY_LABELS.get(m.class_.__name__, m.class_.__name__)
    return table.name


def dependencies(obj):
    """(conséquences, blocages) : éléments liés, d'après les clés étrangères réelles du schéma."""
    mapper = inspect(type(obj))
    table = mapper.local_table
    secondary = {r.secondary for r in mapper.relationships if r.secondary is not None}
    cascaded = {r.mapper.local_table for r in mapper.relationships if r.cascade.delete}
    effects, blocks = [], []
    for t in db.metadata.sorted_tables:
        for fk in t.foreign_keys:
            if fk.column.table is not table:
                continue
            n = db.session.execute(select(func.count()).select_from(t).where(fk.parent == obj.id)).scalar()
            if not n:
                continue
            if t in secondary or t in cascaded or fk.ondelete in ("CASCADE", "SET NULL"):
                effects.append(f"{n} lien(s) ou élément(s) rattaché(s) : {_class_label(t) if t not in secondary else 'associations'}")
            else:
                blocks.append(f"Encore utilisé par {n} {_class_label(t).lower()}.")
    return effects, blocks


def classify(spec, objs):
    """Répartit la sélection : deletable [(obj, conséquences)], protected [(obj, raison)], blocked [(obj, raison)]."""
    deletable, protected, blocked = [], [], []
    for o in objs:
        effects, blocks = dependencies(o)
        hard = spec.hard(o) if spec.hard else None
        keep = spec.protected(o) if spec.protected else None
        if hard or blocks:
            blocked.append((o, hard or blocks[0]))
        elif keep:
            protected.append((o, keep, effects))
        else:
            deletable.append((o, effects))
    return deletable, protected, blocked


def _plain(v):
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def snapshot(obj):
    return {c.key: _plain(getattr(obj, c.key)) for c in inspect(type(obj)).column_attrs
            if c.key not in _HIDDEN and getattr(obj, c.key) not in (None, "")}


def _polymorphic_cleanup(spec, obj):
    """Liens génériques (type + identifiant), que la base ne peut pas supprimer d'elle-même."""
    name = type(obj).__name__
    M.FrameworkLink.query.filter_by(entity_type=name, entity_id=obj.id).delete(synchronize_session=False)
    M.RiskLink.query.filter_by(entity_type=name, entity_id=obj.id).delete(synchronize_session=False)
    files = []
    keys = [(spec.attach, obj.id)] if spec.attach else []
    if isinstance(obj, M.Audit):
        keys += [("finding", f.id) for f in obj.findings]
    for key, oid in keys:
        for att in M.Attachment.query.filter_by(entity_type=key, entity_id=oid).all():
            files.append(att.stored_name)
            db.session.delete(att)
    return files


def delete(spec, objs, include_protected):
    """Supprime ce qui peut l'être, dans une seule transaction. Retourne (supprimés, ignorés)."""
    from app.services import storage
    deletable, protected, blocked = classify(spec, objs)
    targets = [o for o, _ in deletable] + ([o for o, *_ in protected] if include_protected else [])
    done, files, copies = [], [], {}
    failed = len(blocked) + (0 if include_protected else len(protected))
    for o in targets:
        label, copy = label_of(o), snapshot(o)
        try:
            with db.session.begin_nested():
                found = _polymorphic_cleanup(spec, o)
                db.session.delete(o)
                db.session.flush()
        except IntegrityError:
            failed += 1
            continue
        files += found
        done.append(label)
        copies[label[:120]] = [json.dumps(copy, ensure_ascii=False, default=str)[:3000], "supprimé"]
    if done:
        log_event("delete", f"Suppression en masse : {len(done)} {spec.label}.", changes=copies)
    else:
        db.session.rollback()
    for name in files:
        try:
            storage.delete(name)
        except Exception:  # noqa: BLE001
            pass
    return done, failed


def csv_rows(spec, objs):
    cols = [c for c in inspect(spec.model).column_attrs if c.key not in _HIDDEN and not c.key.endswith("_id") and not c.key.endswith("_enc")]
    rows = [[FIELD_LABELS.get(c.key, c.key) for c in cols]]
    for o in objs:
        rows.append([getattr(_v, "label", _plain(_v)) if (_v := getattr(o, c.key)) is not None else "" for c in cols])
    return rows
