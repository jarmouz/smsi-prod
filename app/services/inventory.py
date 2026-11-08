"""Filtres de l'inventaire des actifs, communs à l'écran, aux exports et à l'API (3.14)."""
from sqlalchemy.orm import selectinload

from app.models import Asset, AssetCategory, AssetStatus, Classification
from app.models.asset import NEED_LEVELS

CYCLE = {"fin_support": lambda a: a.eos_state == "depassee", "fin_proche": lambda a: a.eos_state == "proche",
         "a_restituer": lambda a: a.to_recover, "elimination": lambda a: a.disposal_missing,
         "sans_dic": lambda a: a.is_business and a.in_service and a.criticality is None,
         "sans_proprietaire": lambda a: a.in_service and not a.owner_id,
         "absent_source": lambda a: a.in_service and a.source_missing_since is not None}
ROLES = ("metier", "support")
FILTER_NAMES = ("role", "categorie", "criticite", "classification", "statut", "cycle")


class InvalidFilter(ValueError):
    """Valeur de filtre inconnue (mode strict de l'API)."""

    def __init__(self, name, value):
        super().__init__(f"Valeur « {value} » non reconnue pour le paramètre {name}.")
        self.name = name


def has_filters(args):
    return any(args.get(n) for n in FILTER_NAMES)


def _clean(args, strict):
    """Filtres reconnus ; une valeur inconnue est ignorée (écran) ou refusée (API)."""
    allowed = {"role": ROLES, "categorie": [x.value for x in AssetCategory],
               "classification": [x.value for x in Classification], "statut": [x.value for x in AssetStatus],
               "cycle": list(CYCLE), "criticite": [str(n) for n in NEED_LEVELS]}
    out = {}
    for name, values in allowed.items():
        raw = args.get(name)
        if not raw:
            continue
        if raw in values:
            out[name] = raw
        elif strict:
            raise InvalidFilter(name, raw)
    return out


def filter_assets(args, strict=False, eager=False):
    """Actifs correspondant aux filtres, triés par référence."""
    f = _clean(args, strict)
    q = Asset.query
    if eager:
        q = q.options(selectinload(Asset.owner), selectinload(Asset.holder), selectinload(Asset.supports),
                      selectinload(Asset.supported), selectinload(Asset.risks), selectinload(Asset.connector))
    if "categorie" in f:
        q = q.filter(Asset.category == AssetCategory(f["categorie"]))
    if "classification" in f:
        q = q.filter(Asset.classification == Classification(f["classification"]))
    if "statut" in f:
        q = q.filter(Asset.status == AssetStatus(f["statut"]))
    assets = q.order_by(Asset.ref).all()
    if f.get("role") == "metier":
        assets = [a for a in assets if a.is_business]
    elif f.get("role") == "support":
        assets = [a for a in assets if not a.is_business]
    if "criticite" in f:
        assets = [a for a in assets if a.criticality == int(f["criticite"])]
    if "cycle" in f:
        assets = [a for a in assets if CYCLE[f["cycle"]](a)]
    return assets
