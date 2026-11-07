"""Critères d'appréciation et d'acceptation des risques (ISO/IEC 27001 6.1.2 a)),
propres à chaque organisation : taille des échelles de vraisemblance et d'impact
(3 à 6 niveaux chacune, ex. 4×4, 5×5, 4×5), seuils des niveaux de risque, seuil
d'acceptation et description de chaque échelon (Administration > Critères de risque).
"""
import json

from flask import g, has_app_context

from app.services import settings as settings_svc

KEY = "risk_criteria"
LEVEL_KEYS = ["faible", "modere", "eleve", "critique"]
SCALE_MIN, SCALE_MAX = 3, 6

# Descriptions proposées par défaut selon la taille de l'échelle
DEFAULT_TEXTS = {
    "likelihood": {
        3: ["Peu probable (moins d'une fois en 5 ans)", "Possible (une fois en 1 à 5 ans)",
            "Probable (au moins une fois par an)"],
        4: ["Improbable (moins d'une fois en 10 ans)", "Possible (une fois en 3 à 10 ans)",
            "Probable (une fois en 1 à 3 ans)", "Très probable (au moins une fois par an)"],
        5: ["Très improbable (moins d'une fois en 10 ans)", "Peu probable (une fois en 5 à 10 ans)",
            "Possible (une fois en 1 à 5 ans)", "Probable (plusieurs fois par an)",
            "Quasi certain (mensuel ou plus)"],
        6: ["Exceptionnel (moins d'une fois en 20 ans)", "Très improbable (une fois en 10 à 20 ans)",
            "Peu probable (une fois en 5 à 10 ans)", "Possible (une fois en 1 à 5 ans)",
            "Probable (plusieurs fois par an)", "Quasi certain (mensuel ou plus)"],
    },
    "impact": {
        3: ["Faible (gêne interne)", "Important (impact client ou réglementaire)",
            "Critique (arrêt d'activité, atteinte majeure)"],
        4: ["Mineur (gêne interne, sans impact client)", "Significatif (impact client ou réglementaire limité)",
            "Grave (plusieurs clients, notification requise)", "Critique (arrêt d'activité, sanction ou atteinte majeure à l'image)"],
        5: ["Négligeable", "Limité (gêne interne, sans impact client)",
            "Important (impact client ou réglementaire limité)",
            "Grave (impact sur plusieurs clients, notification requise)",
            "Critique (arrêt d'activité, atteinte majeure à l'image ou sanction)"],
        6: ["Négligeable", "Mineur (gêne interne)", "Limité (impact client ponctuel)",
            "Important (impact client ou réglementaire)", "Grave (plusieurs clients, notification requise)",
            "Critique (arrêt d'activité, sanction ou atteinte majeure)"],
    },
}

# Dimensions d'impact (3.9) : l'impact d'un risque peut être coté par dimension ; l'impact
# retenu est le maximum des dimensions cotées (approche ISO/IEC 27005). Activables par l'organisation.
DIMENSIONS = [
    ("financier", "Financier"),
    ("clients", "Clients et engagements contractuels"),
    ("reglementaire", "Juridique et réglementaire"),
    ("personnes", "Personnes concernées (vie privée, santé, droits)"),
    ("continuite", "Activité et continuité"),
    ("image", "Image et réputation"),
]
DIMENSION_LABELS = dict(DIMENSIONS)

DEFAULT = {
    "scale": {"likelihood": 5, "impact": 5},
    "levels": {"faible": {"label": "Faible", "min": 1}, "modere": {"label": "Modéré", "min": 5},
               "eleve": {"label": "Élevé", "min": 10}, "critique": {"label": "Critique", "min": 15}},
    # score résiduel <= seuil : acceptable au regard des critères ; au-delà,
    # acceptation formelle du propriétaire du risque requise
    "acceptance": 9,
    "dimensions": ["financier", "clients", "reglementaire", "personnes", "continuite"],
    "likelihood": DEFAULT_TEXTS["likelihood"][5],
    "impact": DEFAULT_TEXTS["impact"][5],
}


def suggested(n_l, n_i):
    """Seuils proposés pour une échelle n_l × n_i (5×5 : 5 / 10 / 15, acceptation 9)."""
    import math
    top = n_l * n_i
    mins = [1]
    for ratio in (0.2, 0.4, 0.6):
        mins.append(max(math.ceil(top * ratio), mins[-1] + 1))
    levels = {k: {"label": DEFAULT["levels"][k]["label"], "min": m} for k, m in zip(LEVEL_KEYS, mins)}
    return levels, mins[2] - 1


def get():
    from app.services.tenancy import current_org_id
    oid = current_org_id()
    cached = g.get("_risk_criteria") if has_app_context() else None
    if cached is not None and cached[0] == oid:     # cache par organisation (tâches multi-organisations)
        return cached[1]
    raw = settings_svc.get(KEY, inherit=False)
    crit = json.loads(json.dumps(DEFAULT))
    if raw:
        try:
            data = json.loads(raw)
            for axis in ("likelihood", "impact"):
                n = int(data.get("scale", {}).get(axis, 5))
                if SCALE_MIN <= n <= SCALE_MAX:
                    crit["scale"][axis] = n
            for k in LEVEL_KEYS:
                if k in data.get("levels", {}):
                    crit["levels"][k].update(data["levels"][k])
            for k in ("acceptance", "likelihood", "impact"):
                if k in data:
                    crit[k] = data[k]
            if isinstance(data.get("dimensions"), list):
                crit["dimensions"] = [d for d in data["dimensions"] if d in DIMENSION_LABELS]
        except (ValueError, TypeError, AttributeError):
            pass
    # une description par échelon (complétée par défaut si besoin)
    for axis in ("likelihood", "impact"):
        n = crit["scale"][axis]
        texts = list(crit[axis])[:n]
        texts += DEFAULT_TEXTS[axis][n][len(texts):]
        crit[axis] = texts
    if has_app_context():
        g._risk_criteria = (oid, crit)
    return crit


def save(crit):
    settings_svc.set_many({KEY: json.dumps(crit, ensure_ascii=False)})
    g.pop("_risk_criteria", None)


def validate(levels, acceptance, top):
    mins = [levels[k]["min"] for k in LEVEL_KEYS]
    if mins[0] != 1 or not all(a < b for a, b in zip(mins, mins[1:])) or mins[-1] > top:
        return f"Les seuils doivent être strictement croissants (faible = 1, dernier niveau ≤ {top})."
    if not 1 <= acceptance <= top:
        return f"Le seuil d'acceptation doit être compris entre 1 et {top}."
    return None


def dimensions():
    """Dimensions d'impact activées : [(clé, libellé)]."""
    return [(k, DIMENSION_LABELS[k]) for k in get()["dimensions"] if k in DIMENSION_LABELS]


def max_score():
    c = get()
    return c["scale"]["likelihood"] * c["scale"]["impact"]


def scale(axis):
    return get()["scale"][axis]


def middle(axis):
    return (scale(axis) + 1) // 2


def convert(value, old_n, new_n):
    """Conversion proportionnelle d'une cotation d'une échelle à une autre (1 -> 1, max -> max)."""
    if value is None or old_n == new_n:
        return value
    return max(1, min(new_n, int(1 + (value - 1) * (new_n - 1) / (old_n - 1) + 0.5)))


def change_scale(new_l, new_i, rescale):
    """Change la taille des échelles de l'organisation. Si rescale, convertit les
    cotations existantes ; sinon refuse si des cotations sortent des nouvelles échelles.
    Retourne (nombre de risques convertis, message d'erreur ou None)."""
    from app.extensions import db
    from app.models import Risk
    crit = get()
    old_l, old_i = crit["scale"]["likelihood"], crit["scale"]["impact"]
    risks = Risk.query.all()
    if not rescale:
        out = [r.ref for r in risks if max(r.likelihood or 0, r.residual_likelihood or 0) > new_l
               or max(r.impact or 0, r.residual_impact or 0) > new_i]
        if out:
            return 0, (f"{len(out)} risque(s) ont des cotations hors des nouvelles échelles "
                       f"({', '.join(out[:5])}{'…' if len(out) > 5 else ''}) : cochez la conversion.")
    n = 0
    if rescale:
        for r in risks:
            before = (r.likelihood, r.impact, r.residual_likelihood, r.residual_impact)
            r.likelihood = convert(r.likelihood, old_l, new_l)
            r.residual_likelihood = convert(r.residual_likelihood, old_l, new_l)
            r.impact = convert(r.impact, old_i, new_i)
            r.residual_impact = convert(r.residual_impact, old_i, new_i)
            if r.impact_by_dim:
                r.set_impact_details({k: convert(v, old_i, new_i) for k, v in r.impact_by_dim.items()})
            n += before != (r.likelihood, r.impact, r.residual_likelihood, r.residual_impact)
    levels, acceptance = suggested(new_l, new_i)
    save({"scale": {"likelihood": new_l, "impact": new_i}, "levels": levels, "acceptance": acceptance,
          "likelihood": DEFAULT_TEXTS["likelihood"][new_l], "impact": DEFAULT_TEXTS["impact"][new_i],
          "dimensions": crit["dimensions"]})
    db.session.commit()
    return n, None


def level_of(score):
    if score is None:
        return "inconnu"
    levels = get()["levels"]
    out = "faible"
    for k in LEVEL_KEYS:
        if score >= levels[k]["min"]:
            out = k
    return out


def label_of(level):
    if level == "opportunite":
        return "Opportunité"
    return get()["levels"].get(level, {}).get("label", "-")


def high_threshold():
    """Score à partir duquel un risque est « élevé » (tableaux de bord, revue)."""
    return get()["levels"]["eleve"]["min"]


def acceptance_threshold():
    return get()["acceptance"]


def init_app(app):
    @app.context_processor
    def _inject():
        return {"risk_level": level_of, "risk_level_label": label_of, "risk_criteria": get,
                "impact_dimensions": dimensions, "dimension_label": lambda k: DIMENSION_LABELS.get(k, k),
                "risk_max_score": max_score}
