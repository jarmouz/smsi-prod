"""Exigences propres à une norme (chapitres 6 et 8 de l'ISO/IEC 27001 et de l'ISO/IEC 42001) :
modules de l'application qui en apportent la preuve, avec un indicateur tiré des données.

Lecture seule : rien n'est calculé ni recopié dans l'évaluation de l'exigence, la fiche
affiche seulement où se trouve la preuve et son état.
"""
from flask import url_for
from werkzeug.routing import BuildError

from app.models import Control, Risk

# (code de la norme, réf. de l'exigence) -> modules de preuve
_MAP = {
    ("ISO27001", "6.1.2"): ("criteres", "registre"),
    ("ISO27001", "8.2"): ("registre", "export_registre"),
    ("ISO27001", "6.1.3"): ("plan", "dda", "acceptation"),
    ("ISO27001", "8.3"): ("plan", "traitement", "acceptation"),
    ("ISO42001", "6.1.2"): ("criteres", "registre", "systemes_ia"),
    ("ISO42001", "8.2"): ("registre", "systemes_ia"),
    ("ISO42001", "6.1.3"): ("plan", "dda", "acceptation"),
    ("ISO42001", "8.3"): ("plan", "traitement", "acceptation"),
    ("ISO42001", "6.1.4"): ("etudes_impact",),
    ("ISO42001", "8.4"): ("etudes_impact", "systemes_ia"),
}


def _risks(code):
    """Risques du registre (hors opportunités) qui concernent la norme : par leur domaine
    ou par un rattachement explicite (3.6)."""
    return [r for r in Risk.query.all() if not r.is_opportunity and r.concerns(code)]


def _ai():
    from app.models.ai_system import AiSystem, AiLifecycle, AiRiskLevel
    live = [s for s in AiSystem.query.all() if s.lifecycle != AiLifecycle.RETIRE]
    return live, AiRiskLevel


def _dda(code):
    allc = Control.of(code, "control").all()
    appl = [c for c in allc if c.applicable]
    nojust = [c for c in allc if not (c.justification or "").strip()]
    return len(allc), len(appl), len(allc) - len(appl), len(nojust)


def _item(key, code):
    if key == "criteres":
        return {"label": "Critères de risque (acceptation, échelles)", "url": url_for("admin.risk_criteria_page"),
                "info": "vraisemblance, impact et seuil d'acceptation de l'organisation"}
    if key == "registre":
        rs = _risks(code)
        own = sum(1 for r in rs if r.owner_id)
        return {"label": "Registre des risques", "url": url_for("risks.index", norme=code, nature="risques"),
                "info": f"{len(rs)} risque(s) identifié(s) et coté(s), {own} avec un propriétaire",
                "warn": not rs}
    if key == "export_registre":
        return {"label": "Registre des risques (export Excel)",
                "url": url_for("soa.export", kind="registre-risques", fmt="xlsx"),
                "info": "information documentée des résultats de l'appréciation"}
    if key == "plan":
        return {"label": "Plan de traitement des risques (export Excel)",
                "url": url_for("soa.export", kind="plan-traitement", fmt="xlsx"),
                "info": "options de traitement, mesures retenues, propriétaires, risques résiduels"}
    if key == "traitement":
        rs = [r for r in _risks(code) if r.treatment.value == "REDUIRE"]
        own = [r for r in rs if any(c.framework.code == code for c in r.controls)]
        done = sum(1 for r in rs if r.controls)
        return {"label": "Risques à réduire traités par des mesures", "url": url_for("risks.index", norme=code, nature="risques"),
                "info": f"{done} / {len(rs)} risque(s) à réduire rattaché(s) à au moins une mesure"
                        + (f", dont {len(own)} par une mesure de l'Annexe A de la norme" if code != "ISO27001" else ""),
                "warn": done < len(rs)}
    if key == "acceptation":
        rs = _risks(code)
        todo = sum(1 for r in rs if r.acceptance_state in ("required", "expired", "outdated"))
        return {"label": "Acceptation des risques résiduels", "url": url_for("risks.index", acceptation="a_faire", norme=code),
                "info": f"{todo} acceptation(s) par le propriétaire du risque à obtenir" if todo
                else "aucune acceptation en attente", "warn": bool(todo)}
    if key == "dda":
        total, appl, excl, nojust = _dda(code)
        label = "Déclaration d'applicabilité" + (" (Annexe A ISO/IEC 27001)" if code == "ISO27001" else " (Annexe A ISO/IEC 42001)")
        return {"label": label, "url": url_for("soa.index", norme=None if code == "ISO27001" else code),
                "info": f"{total} mesures : {appl} retenue(s), {excl} exclue(s), {nojust} sans justification",
                "warn": bool(nojust)}
    if key == "systemes_ia":
        live, lvl = _ai()
        high = sum(1 for s in live if s.risk_level in (lvl.ELEVE, lvl.INACCEPTABLE))
        return {"label": "Inventaire des systèmes d'IA", "url": url_for("aisystems.index"),
                "info": f"{len(live)} système(s) en service, {high} à risque élevé ou inacceptable"}
    if key == "etudes_impact":
        live, _ = _ai()
        todo = sum(1 for s in live if any("étude d'impact" in g for g in s.gaps))
        if not live:
            return {"label": "Études d'impact des systèmes d'IA", "url": url_for("aisystems.index"),
                    "info": "aucun système d'IA inventorié : commencer par l'inventaire", "warn": True}
        return {"label": "Études d'impact des systèmes d'IA", "url": url_for("aisystems.index", ecarts=1),
                "info": f"{len(live) - todo} / {len(live)} système(s) avec une étude d'impact à jour",
                "warn": bool(todo)}
    return None


def for_control(c):
    """Modules de preuve d'une exigence propre (liste vide pour toute autre exigence ou mesure)."""
    if not c.is_clause or c.framework is None:
        return []
    keys = _MAP.get((c.framework.code, c.ref), ())
    out = []
    for k in keys:
        try:
            it = _item(k, c.framework.code)
        except BuildError:         # module absent de cette installation : repère omis
            it = None
        if it:
            out.append(it)
    return out
