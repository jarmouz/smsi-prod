"""Création des organisations (tenants) et de leur socle initial."""
import re
import unicodedata

from app.extensions import db
from app.models import Organization, Control, User, Role, ControlStatus
from app.services import settings as settings_svc
from app.services.tenancy import tenant_scope


def slugify(text):
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:64] or "org"


def unique_slug(base):
    slug, n = base, 2
    while Organization.query.filter_by(slug=slug).first():
        slug = f"{base[:60]}-{n}"
        n += 1
    return slug


def seed_controls():
    """Active l'ISO 27001 (catalogue Annexe A, 93 mesures) pour l'organisation courante."""
    from app.services import frameworks
    frameworks.enable(frameworks.CORE)


def create_organization(name, slug=None, docs_folder=None,
                        admin_email=None, admin_name=None, admin_password=None):
    """Crée une organisation, son catalogue Annexe A, son nom en paramètres et,
    si fourni, son premier RSSI. Retourne (organization, user|None)."""
    org = Organization(name=name.strip(), slug=unique_slug(slugify(slug or name)),
                       docs_folder=(docs_folder or "").strip("/") or None)
    db.session.add(org)
    db.session.flush()
    user = None
    with tenant_scope(org.id):
        seed_controls()
        if admin_email:
            from app.services import totp
            user = User(email=admin_email.strip().lower(), name=(admin_name or admin_email).strip(),
                        role=Role.RSSI, job_title="RSSI")
            user.temp_password = admin_password or totp.temporary_password()
            user.set_password(user.temp_password)
            user.must_change_password = True
            db.session.add(user)
        db.session.flush()
        settings_svc.set_many({"org_name": org.name})  # commit
    return org, user


# --------------------------------------------------------------------------
# Déplacement de comptes et d'objets entre organisations (hors contexte
# d'organisation : CLI uniquement, aucune requête n'est filtrée)
# --------------------------------------------------------------------------
def _fk_columns(model, table_name):
    """Colonnes de model qui référencent table_name.id."""
    return [c.key for c in model.__table__.columns
            if any(fk.column.table.name == table_name for fk in c.foreign_keys)]


def _tenant_models():
    from app.models import TenantMixin
    return [m.class_ for m in db.Model.registry.mappers if issubclass(m.class_, TenantMixin)]


def move_users(users, target, log):
    """Rattache des comptes à l'organisation target. Dans l'organisation
    d'origine, les objets qui les désignaient (propriétaire, responsable...)
    perdent cette référence, qui pointerait sinon hors de l'organisation."""
    for u in users:
        src = u.organization_id
        if src == target.id:
            log(f"{u.email} : déjà dans {target.name}")
            continue
        for model in _tenant_models():
            for col in _fk_columns(model, "users"):
                n = (model.query.filter(getattr(model, col) == u.id, model.organization_id == src)
                     .update({col: None}, synchronize_session=False))
                if n:
                    log(f"  {u.email} : {n} {model.__tablename__}.{col} remis à vide dans l'origine")
        u.organization_id = target.id
        log(f"{u.email} -> {target.name}")


def _remap(obj, target, log):
    """Aligne les liens d'un objet déplacé sur l'organisation cible : mesures
    retrouvées par référence, utilisateurs hors cible remis à vide."""
    from app.models import User
    for col in _fk_columns(type(obj), "controls"):
        cid = getattr(obj, col)
        if cid:
            src = db.session.get(Control, cid)
            new = Control.query.filter_by(organization_id=target.id, framework_id=src.framework_id, kind=src.kind,
                                          ref=src.ref).first()
            setattr(obj, col, new.id if new else None)
    if hasattr(obj, "controls"):
        mapped = []
        for c in obj.controls:
            c2 = Control.query.filter_by(organization_id=target.id, framework_id=c.framework_id,
                                         kind=c.kind, ref=c.ref).first()
            if c2:
                mapped.append(c2)
            else:
                log(f"    mesure {c.annex_ref} ({c.framework.short_name}) non rattachée : norme inactive dans {target.name}")
        obj.controls = mapped
    for col in _fk_columns(type(obj), "users"):
        uid = getattr(obj, col)
        if uid and db.session.get(User, uid).organization_id != target.id:
            setattr(obj, col, None)
            log(f"    {col} remis à vide (utilisateur hors de {target.name})")
    obj.organization_id = target.id


def record_kinds():
    from app.models import (Risk, Document, Evidence, Asset, Incident, AwarenessAction,
                            Audit, ManagementReview)
    # type -> (modèle, entity_type des pièces jointes)
    return {"risk": (Risk, None), "document": (Document, "document"), "evidence": (Evidence, "evidence"),
            "asset": (Asset, None), "incident": (Incident, "incident"),
            "awareness": (AwarenessAction, "awareness"), "audit": (Audit, "audit"),
            "review": (ManagementReview, "review")}


def move_records(kind, refs, source, target, log):
    """Déplace des objets (par référence) de source vers target, avec leurs
    sous-éléments (constats, actions) et leurs pièces jointes."""
    from app.models import Attachment
    model, att_type = record_kinds()[kind]

    def move_attachments(entity_type, entity_id):
        for att in Attachment.query.filter_by(organization_id=source.id, entity_type=entity_type,
                                              entity_id=entity_id).all():
            _remap(att, target, log)
            log(f"    pièce jointe {att.filename}")

    for ref in refs:
        obj = model.query.filter_by(organization_id=source.id, ref=ref).first()
        if obj is None:
            raise ValueError(f"{kind} {ref} introuvable dans {source.name}.")
        if model.query.filter_by(organization_id=target.id, ref=ref).first():
            raise ValueError(f"{kind} {ref} existe déjà dans {target.name}.")
        log(f"{kind} {ref} -> {target.name}")
        _remap(obj, target, log)
        if att_type:
            move_attachments(att_type, obj.id)
        for f in getattr(obj, "findings", []):
            _remap(f, target, log)
            move_attachments("finding", f.id)
            for a in f.actions:
                _remap(a, target, log)
        for a in getattr(obj, "actions", []):
            _remap(a, target, log)
        # rattachements aux normes (FrameworkLink) : suivent l'objet
        from app.models import FrameworkLink
        for fl in FrameworkLink.query.filter_by(organization_id=source.id, entity_type=type(obj).__name__,
                                                entity_id=obj.id).all():
            fl.organization_id = target.id
        # liens d'un risque vers les autres modules et actifs : ces éléments restent dans
        # l'organisation d'origine, les liens sont retirés (sinon ils traverseraient deux organisations)
        if kind == "document":     # acceptations des personnes de l'origine : elles y restent
            from app.models import PolicyAcceptance
            n = PolicyAcceptance.query.filter_by(organization_id=source.id, document_id=obj.id).delete(
                synchronize_session=False)
            if n:
                log(f"    {n} acceptation(s) de lecture retirée(s) (personnes restées dans {source.name})")
        if kind == "risk":
            for link in list(obj.links):
                log(f"    lien vers {link.entity_type} n°{link.entity_id} retiré (élément resté dans {source.name})")
                obj.links.remove(link)
            for asset in [x for x in obj.assets if x.organization_id != target.id]:
                log(f"    actif {asset.ref} détaché (resté dans {source.name})")
                obj.assets.remove(asset)
