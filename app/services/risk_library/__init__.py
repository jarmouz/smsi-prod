"""Bibliothèque de scénarios de risques et d'opportunités (3.12).

Scénarios prêts à l'emploi, par domaine (sécurité de l'information, vie privée, IA,
continuité, services informatiques, qualité), rédigés selon ISO 31000 / ISO/IEC 27005 :
événement redouté, cause, vulnérabilité, conséquences, cotation proposée (vraisemblance et
impacts par dimension sur une échelle de 5), option de traitement, mesures d'annexe des
normes (27001, 27701, 42001), exigences de référence (22301, 20000-1, 9001), actions de
traitement proposées, secteurs concernés.

Les données sont dans les modules de ce paquet (une liste SCENARIOS par module) ; l'import
crée des risques dans le registre de l'organisation courante en convertissant la cotation à
ses échelles et en ne rattachant que les mesures des normes actives.
"""
import importlib
from functools import lru_cache

MODULES = ("securite_externe", "securite_interne", "vie_privee", "ia", "continuite", "services_it", "qualite")

DOMAIN_ORDER = [None, "VIE_PRIVEE", "IA", "CONTINUITE", "SERVICES", "QUALITE"]
SECTORS = {"tous": "Tous secteurs", "saas": "Éditeurs et SaaS", "industrie": "Industrie", "sante": "Santé",
           "finance": "Banque, assurance, finance", "public": "Secteur public", "commerce": "Commerce et distribution",
           "services": "Services", "logistique": "Transport et logistique", "telecom": "Télécoms", "education": "Éducation",
           "energie": "Énergie", "btp": "BTP", "agro": "Agroalimentaire"}
NORM_LABELS = {"ISO27001": "27001", "ISO27701": "27701", "ISO42001": "42001", "ISO22301": "22301",
               "ISO20000": "20000-1", "ISO9001": "9001"}


@lru_cache(maxsize=1)
def scenarios():
    """Tous les scénarios, dans l'ordre des domaines puis des codes."""
    out = []
    for name in MODULES:
        try:
            mod = importlib.import_module(f"{__name__}.{name}")
        except ImportError:
            continue
        for s in getattr(mod, "SCENARIOS", []):
            s = dict(s)
            s["category"] = s["category"].replace("'", "’").strip()   # familles : apostrophe unique
            s.setdefault("clauses", {})
            s.setdefault("references", "")
            s["impact"] = max(s["impacts"].values()) if s.get("impacts") else 3
            s["score5"] = s["likelihood"] * s["impact"]
            out.append(s)
    order = {d: i for i, d in enumerate(DOMAIN_ORDER)}
    return sorted(out, key=lambda s: (order.get(s["domain"], 9), s["nature"] == "OPPORTUNITE", s["code"]))


def by_code():
    return {s["code"]: s for s in scenarios()}


def categories(items):
    seen = []
    for s in items:
        if s["category"] not in seen:
            seen.append(s["category"])
    return seen


def search(domain=None, nature=None, category=None, sector=None, q=None):
    """Filtre ; domain : clé de domaine, « SECURITE » ou vide ; nature : « risques » / « opportunites »."""
    import unicodedata

    def norm(t):
        return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")
    items = scenarios()
    if domain == "SECURITE":
        items = [s for s in items if s["domain"] is None]
    elif domain:
        items = [s for s in items if s["domain"] == domain]
    if nature == "risques":
        items = [s for s in items if s["nature"] is None]
    elif nature == "opportunites":
        items = [s for s in items if s["nature"] == "OPPORTUNITE"]
    if category:
        items = [s for s in items if s["category"] == category]
    if sector and sector != "tous":
        items = [s for s in items if sector in s["sectors"] or "tous" in s["sectors"]]
    if q:
        words = norm(q).split()
        items = [s for s in items
                 if all(w in norm(" ".join([s["code"], s["title"], s["event"], s["cause"], s["vulnerability"],
                                            s["consequence"], s["category"], " ".join(s["actions"])])) for w in words)]
    return items


# --- import dans le registre ------------------------------------------------------------
def scaled(s):
    """Cotation convertie aux échelles de l'organisation : (vraisemblance, {dimension: impact})."""
    from app.services import risk_criteria
    n_l, n_i = risk_criteria.scale("likelihood"), risk_criteria.scale("impact")
    lik = risk_criteria.convert(s["likelihood"], 5, n_l)
    dims = {k: risk_criteria.convert(v, 5, n_i) for k, v in s["impacts"].items()}
    return lik, dims


def existing_titles():
    from app.models import Risk
    return {r.title.strip().lower() for r in Risk.query.all()}


def import_scenarios(codes, owner_id=None, with_actions=True, force=False):
    """Crée un risque par scénario. Retourne (risques créés, [(code, motif)] ignorés)."""
    from app.extensions import db
    from app.models import Risk, RiskAction, RiskStatus, Treatment, Control
    from app.services import risk_criteria, frameworks as fw_svc
    from app.services.refs import next_ref
    lib = by_code()
    active = {f.code for f in fw_svc.active()}
    enabled_dims = {k for k, _ in risk_criteria.dimensions()}
    titles = existing_titles()
    created, skipped = [], []
    for code in codes:
        s = lib.get(code)
        if s is None:
            skipped.append((code, "scénario inconnu"))
            continue
        if not force and s["title"].strip().lower() in titles:
            skipped.append((code, "déjà présent dans le registre (même intitulé)"))
            continue
        lik, dims = scaled(s)
        kept = {k: v for k, v in dims.items() if k in enabled_dims}
        notes = [f"Source : bibliothèque de scénarios Integra ({s['code']}, {s['category']})."]
        cl = "; ".join(f"ISO {NORM_LABELS.get(n, n)} {', '.join(r)}" for n, r in (s.get("clauses") or {}).items() if r)
        if cl:
            notes.append(f"Exigences de référence : {cl}.")
        if s.get("references"):
            notes.append(f"Références : {s['references']}.")
        r = Risk(ref=next_ref(Risk, "R"), title=s["title"][:300], description=s["event"] + "\n\n" + " ".join(notes),
                 threat=s["cause"][:255], vulnerability=s["vulnerability"][:255], consequence=s["consequence"],
                 likelihood=lik, impact=max(dims.values()) if dims else risk_criteria.middle("impact"),
                 risk_domain=s["domain"], nature=s["nature"], treatment=Treatment(s["treatment"]),
                 status=RiskStatus.IDENTIFIE, owner_id=owner_id or None)
        if kept:
            r.set_impact_details(kept)
        controls = []
        for norm, refs in s["controls"].items():
            if norm in active and refs:
                controls += Control.of(norm, "control").filter(Control.ref.in_(refs)).all()
        r.controls = controls
        db.session.add(r)
        db.session.flush()
        if with_actions:
            for title in s["actions"]:
                r.actions.append(RiskAction(title=title[:300], owner_id=owner_id or None))
        titles.add(s["title"].strip().lower())
        created.append(r)
    return created, skipped
