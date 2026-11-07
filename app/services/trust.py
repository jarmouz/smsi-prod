"""Page de confiance publique (3.11), à la manière des « Trust Centers ».

Page publique d'une organisation (/confiance/<slug>) : certifications et normes, mesures de
sécurité en place, documents publics ou sur demande, sous-traitants, contact. Tout est opt-in :
rien n'est publié tant que le RSSI ne l'a pas activé et choisi.

Sécurité : les pages publiques n'ont pas d'utilisateur connecté, donc pas d'organisation
courante ; chaque requête fixe explicitement l'organisation (tenancy.set_current_org) avant
toute lecture. Seuls des documents approuvés et marqués sont servis ; l'accès aux documents
« sur demande » passe par un lien signé, lié à une demande accordée, révocable et daté.
"""
from datetime import datetime

from flask import current_app
from itsdangerous import URLSafeSerializer, BadSignature

from app.services import settings as settings_svc

KEYS = ("trust_enabled", "trust_title", "trust_intro", "trust_contact", "trust_frameworks", "trust_show_controls",
        "trust_noindex")


def config():
    g = lambda k, d="": settings_svc.get(k, d, inherit=False) or d  # noqa: E731
    return {"enabled": g("trust_enabled") == "1", "title": g("trust_title"), "intro": g("trust_intro"),
            "contact": g("trust_contact"), "frameworks": [c for c in g("trust_frameworks").split(",") if c],
            "show_controls": g("trust_show_controls", "1") == "1", "noindex": g("trust_noindex", "1") == "1"}


def save(cfg):
    settings_svc.set_many({
        "trust_enabled": "1" if cfg["enabled"] else "0", "trust_title": cfg["title"][:200],
        "trust_intro": cfg["intro"][:4000], "trust_contact": cfg["contact"][:255],
        "trust_frameworks": ",".join(cfg["frameworks"]), "trust_show_controls": "1" if cfg["show_controls"] else "0",
        "trust_noindex": "1" if cfg["noindex"] else "0"})


# --- contenu publié -------------------------------------------------------------------
def certifications(cfg):
    """Normes choisies : statut public (certifiée, en cours) sans aucun pourcentage interne."""
    from app.models import OrgFramework, Framework
    rows = (OrgFramework.query.join(Framework, Framework.id == OrgFramework.framework_id)
            .filter(OrgFramework.enabled.is_(True)).order_by(Framework.sort_order).all())
    out = []
    for of in rows:
        if of.framework.code not in cfg["frameworks"]:
            continue
        out.append({"name": of.framework.name, "domain": of.framework.domain, "code": of.framework.code,
                    "certified_on": of.certified_on, "certifier": of.certifier, "target": of.target_date})
    return out


def controls(cfg):
    """Mesures d'annexe en place des normes choisies, par thème : [(norme, [(thème, [intitulés])])]."""
    from app.models import Control, ControlStatus, Framework, Theme
    out = []
    for code in cfg["frameworks"]:
        fw = Framework.query.filter_by(code=code).first()
        if fw is None or fw.kind != "controls":
            continue
        groups = {}
        for c in Control.of(code, "control").order_by(Control.id).all():
            if c.applicable and c.status == ControlStatus.IMPLEMENTE:
                key = c.theme.label if isinstance(c.theme, Theme) else str(c.theme)
                groups.setdefault(key, []).append(c.title)
        if groups:
            out.append((fw.name, list(groups.items())))
    return out


def documents():
    """Documents approuvés publiés : (publics, sur demande)."""
    from app.models import Document, DocStatus
    docs = (Document.query.filter(Document.status == DocStatus.APPROUVE, Document.trust_visibility.isnot(None))
            .order_by(Document.ref).all())
    return ([d for d in docs if d.trust_visibility == "PUBLIC"], [d for d in docs if d.trust_visibility == "DEMANDE"])


def subprocessors():
    from app.models import Supplier
    from app.models.governance import SupplierStatus
    return [s for s in Supplier.query.filter(Supplier.trust_public.is_(True)).order_by(Supplier.name).all()
            if s.status == SupplierStatus.ACTIF]


def file_of(doc):
    """Fichier servi pour un document : la pièce jointe la plus récente (None si aucune)."""
    from app.services import attachments as att_svc
    atts = [a for a in att_svc.get_for("document", doc.id) if a.organization_id == doc.organization_id]
    return atts[0] if atts else None


def published_doc(doc_id, visibility):
    from app.models import Document, DocStatus
    from app.extensions import db
    from app.services.tenancy import current_org_id
    d = db.session.get(Document, doc_id)
    if (d is None or d.organization_id != current_org_id() or d.status != DocStatus.APPROUVE
            or d.trust_visibility != visibility):
        return None
    return d


# --- liens d'accès aux documents sur demande ------------------------------------------
def _serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="trust-access")


def token_for(req):
    return _serializer().dumps({"r": req.id, "o": req.organization_id})


def request_from_token(token, org_id):
    """Demande accordée, non expirée, de cette organisation ; None sinon."""
    from app.models import TrustRequest
    from app.extensions import db
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict) or data.get("o") != org_id:
        return None
    req = db.session.get(TrustRequest, data.get("r"))
    return req if req is not None and req.organization_id == org_id and req.active else None


def touch(req):
    req.downloads = (req.downloads or 0) + 1
    req.last_access_at = datetime.utcnow()
