"""Tableau de bord SMI (3.9) : préparation à la certification par norme et points à traiter.

Inspiré des plateformes de conformité continue : pour chaque norme active, part des
éléments retenus qui sont mis en œuvre et part qui disposent d'une preuve ; puis une
liste unique de « points à traiter », tous modules confondus, chacun avec son lien.
Lecture seule : rien n'est enregistré.
"""
from flask import url_for

from app.models import Control, ControlStatus


def _stats(items):
    appl = [c for c in items if c.applicable]
    impl = [c for c in appl if c.status == ControlStatus.IMPLEMENTE]
    prog = [c for c in appl if c.status == ControlStatus.EN_COURS]
    proven = [c for c in appl if c.all_evidences]
    return {"total": len(items), "applicable": len(appl), "implemented": len(impl), "in_progress": len(prog),
            "proven": len(proven), "unproven_impl": sum(1 for c in impl if not c.all_evidences)}


def _pct(a, b):
    return round(100 * a / b) if b else 0


def norm_cards():
    """Une carte par norme active (socle commun en tête) : avancement, preuves, risques, cible."""
    from app.models import OrgFramework, Risk
    from app.services import frameworks as fw_svc
    risks = [r for r in Risk.query.all() if r.status.is_open and not r.is_opportunity]
    targets = {o.framework_id: o for o in OrgFramework.query.all()}
    cards = []
    for fw in fw_svc.controls_frameworks():
        parts = []
        if fw.kind == "controls":
            parts.append(("Mesures", "control", _stats(Control.of(fw.code, "control").all())))
            if fw_svc.has_clauses(fw):
                parts.append(("Exigences", "clause", _stats(Control.of(fw.code, "clause").all())))
        else:
            parts.append(("Exigences", "clause", _stats(Control.of(fw.code, "clause").all())))
        appl = sum(p[2]["applicable"] for p in parts)
        impl = sum(p[2]["implemented"] for p in parts)
        proven = sum(p[2]["proven"] for p in parts)
        of = targets.get(fw.id)
        is_socle = fw.kind == "common"
        cards.append({
            "fw": fw, "is_socle": is_socle, "parts": [
                {"label": label, "kind": kind, **st, "pct": _pct(st["implemented"], st["applicable"])}
                for label, kind, st in parts],
            "pct": _pct(impl, appl), "evidence_pct": _pct(proven, appl), "applicable": appl, "implemented": impl,
            "risks": None if is_socle else sum(1 for r in risks if r.concerns(fw.code)),
            "high": None if is_socle else sum(1 for r in risks if r.is_high and r.concerns(fw.code)),
            "target": of.target_date if of else None, "certifier": of.certifier if of else None,
            "certified_on": of.certified_on if of else None,
            "url": url_for("soa.index", norme=None if fw.code == fw_svc.CORE else fw.code),
        })
    return cards


def overall(cards):
    """Avancement global : moyenne des normes (hors socle, déjà compté dans chaque norme qui en hérite)."""
    norms = [c for c in cards if not c["is_socle"] and c["applicable"]]
    return round(sum(c["pct"] for c in norms) / len(norms)) if norms else 0


def attention(pilot):
    """Points à traiter, tous modules : [(gravité, libellé, nombre, url)] triés (0 = critique)."""
    from datetime import date
    from app.models import (Risk, RiskAction, CorrectiveAction, ReviewAction, Document, DocStatus, Incident,
                            IncidentStatus)
    from app.services import frameworks as fw_svc
    risks = Risk.query.all()
    open_r = [r for r in risks if r.status.is_open]
    items = []

    def add(sev, label, n, url):
        if n:
            items.append((sev, label, n, url))

    add(0, "Risques résiduels à accepter ou ré-accepter",
        sum(r.acceptance_state in ("required", "expired", "outdated") for r in risks),
        url_for("risks.index", acceptation="a_faire"))
    add(0, "Risques à réévaluer (incident, NC ou changement lié)", sum(bool(r.reassess_at) for r in open_r),
        url_for("risks.index", statut="a_reevaluer"))
    add(0, "Non-conformités majeures ouvertes", pilot.get("nc_major", 0), url_for("nonconformities.index", statut="ouvertes"))
    add(1, "Actions de traitement des risques en retard", sum(a.is_overdue for a in RiskAction.query.all()),
        url_for("risks.plan", etat="retard"))
    add(1, "Risques à traiter sans action planifiée",
        sum(1 for r in open_r if r.status.value in ("IDENTIFIE", "EN_TRAITEMENT") and not r.is_opportunity
            and r.treatment.value in ("REDUIRE", "EVITER", "PARTAGER") and not r.actions),
        url_for("risks.index", statut="IDENTIFIE"))
    add(1, "Actions correctives en retard", sum(a.is_overdue for a in CorrectiveAction.query.all()),
        url_for("nonconformities.index", statut="ouvertes"))
    add(1, "Actions de revue de direction en retard",
        sum(1 for a in ReviewAction.query.all() if a.is_overdue), url_for("reviews.index"))
    add(1, "Incidents ouverts", Incident.query.filter(Incident.status != IncidentStatus.CLOTURE).count(),
        url_for("incidents.index"))
    add(2, "Efficacité de non-conformités à vérifier", pilot.get("nc_verify", 0),
        url_for("nonconformities.index", statut="A_VERIFIER"))
    fw_ids = [f.id for f in fw_svc.controls_frameworks()]          # normes actives + socle commun
    impl_noproof = sum(1 for c in Control.query.filter(Control.framework_id.in_(fw_ids), Control.applicable.is_(True),
                                                       Control.status == ControlStatus.IMPLEMENTE).all()
                       if not c.inherited and not c.all_evidences)
    add(2, "Mesures ou exigences mises en œuvre sans preuve", impl_noproof, url_for("soa.index"))
    docs = Document.query.all()
    add(2, "Documents à approuver", sum(d.status == DocStatus.EN_REVUE for d in docs), url_for("documents.index"))
    add(2, "Documents à revoir", sum(bool(d.review_overdue) for d in docs), url_for("documents.index"))
    add(2, "Fournisseurs avec écarts", pilot.get("sup_gaps", 0), url_for("suppliers.index", ecarts=1))
    add(2, "Exigences légales non conformes ou partielles", pilot.get("req_nok", 0), url_for("requirements.index"))
    add(2, "Mesures d'indicateurs attendues", pilot.get("kpi_due", 0), url_for("objectives.index"))
    add(2, "Objectifs en retard", pilot.get("obj_overdue", 0), url_for("objectives.index"))
    add(3, "Activités de la BIA dont l'exercice est à refaire", pilot.get("bcp_overdue", 0), url_for("continuity.index"))
    add(3, "Changements en attente de décision", pilot.get("chg_pending", 0), url_for("changes.index"))
    add(3, "Écarts de compétences", pilot.get("comp_gaps", 0), url_for("competences.index"))
    from app.services import policies
    ps = policies.summary()
    add(1, "Acceptations de politiques hors délai", ps["overdue"], url_for("documents.acceptances"))
    add(2, "Acceptations de politiques en attente", ps["pending"] - ps["overdue"], url_for("documents.acceptances"))
    for code, label, n, url in module_inputs():
        add(1 if "retard" in label else 2, f"{label} ({code[3:] if code != 'ISO20000' else '20000-1'})", n, url)
    review = sum(1 for r in open_r if r.review_date and r.review_date < date.today())
    add(3, "Risques dont la date de revue est dépassée", review, url_for("risks.index"))
    return sorted(items, key=lambda x: x[0])


def risk_summary():
    from app.models import Risk, RiskAction
    from app.services import risk_criteria
    risks = Risk.query.all()
    open_r = [r for r in risks if r.status.is_open and not r.is_opportunity]
    acts = RiskAction.query.all()
    live = [a for a in acts if a.status.value != "ABANDONNEE"]
    n_l, n_i = risk_criteria.scale("likelihood"), risk_criteria.scale("impact")
    matrix = {(l, i): [] for l in range(1, n_l + 1) for i in range(1, n_i + 1)}
    for r in open_r:
        l, i = r.residual_likelihood or r.likelihood, r.residual_impact or r.impact
        if (l, i) in matrix:
            matrix[(l, i)].append(r)
    return {
        "open": len(open_r), "high": sorted((r for r in open_r if r.is_high), key=lambda r: -r.effective_score),
        "to_accept": sum(r.acceptance_state in ("required", "expired", "outdated") for r in risks),
        "reassess": sum(bool(r.reassess_at) for r in open_r),
        "opportunities": sum(1 for r in risks if r.status.is_open and r.is_opportunity),
        "actions_open": sum(a.status.is_open for a in acts), "actions_late": sum(a.is_overdue for a in acts),
        "plan_pct": round(sum(a.progress for a in live) / len(live)) if live else None,
        "matrix": matrix, "n_l": n_l, "n_i": n_i,
    }


def module_inputs():
    """Points propres aux modules des normes actives : [(code, libellé, nombre, url)], nombres non nuls.
    Alimentent les points à traiter et les données d'entrée de la revue de direction (9.3.2)."""
    from app.services import frameworks as fw_svc
    codes = {f.code for f in fw_svc.active()}
    out = []

    def add(code, label, n, url):
        if n:
            out.append((code, label, n, url))
    if "ISO27701" in codes:
        from app.models.privacy import ProcessingActivity, SubjectRequest, DpiaStatus
        pas = ProcessingActivity.query.all()
        add("ISO27701", "Demandes de personnes concernées en retard", sum(r.overdue for r in SubjectRequest.query.all()),
            url_for("privacy.requests_index"))
        add("ISO27701", "Analyses d'impact (AIPD) à évaluer ou réaliser",
            sum(p.dpia in (DpiaStatus.A_EVALUER, DpiaStatus.A_REALISER) for p in pas), url_for("privacy.index"))
        add("ISO27701", "Traitements de données à revoir", sum(bool(p.review_overdue) for p in pas), url_for("privacy.index"))
    if "ISO42001" in codes:
        from app.models.ai_system import AiSystem, AiImpactAssessment
        add("ISO42001", "Systèmes d'IA avec écarts", sum(bool(s.gaps) for s in AiSystem.query.all()),
            url_for("aisystems.index"))
        add("ISO42001", "Études d'impact IA à revoir", sum(bool(a.review_overdue) for a in AiImpactAssessment.query.all()),
            url_for("aisystems.index"))
    if "ISO22301" in codes:
        from app.models.service_mgmt import ContinuityPlan
        add("ISO22301", "Plans de continuité avec écarts (validation, exercice)",
            sum(bool(p.gaps) for p in ContinuityPlan.query.all()), url_for("bcplans.index"))
    if "ISO20000" in codes:
        from app.models.service_mgmt import ItService, Problem, Release
        add("ISO20000", "Services IT avec écarts (niveaux de service, mesures)",
            sum(bool(s.gaps) for s in ItService.query.all()), url_for("itsm.index"))
        add("ISO20000", "Problèmes ouverts", sum(not p.status.closed for p in Problem.query.all()), url_for("itsm.problems"))
        add("ISO20000", "Mises en production avec écarts", sum(bool(r.gaps) for r in Release.query.all()),
            url_for("itsm.releases"))
    if "ISO9001" in codes:
        from app.models.quality import QmsProcess, CustomerSurvey, Complaint
        cps = Complaint.query.all()
        add("ISO9001", "Réclamations clients en retard", sum(c.overdue for c in cps), url_for("quality.complaints"))
        add("ISO9001", "Réclamations clients ouvertes", sum(not c.status.closed for c in cps), url_for("quality.complaints"))
        add("ISO9001", "Mesures de satisfaction sous la cible", sum(bool(s.below_target) for s in CustomerSurvey.query.all()),
            url_for("quality.surveys"))
        add("ISO9001", "Processus avec écarts (pilote, indicateurs, risques)",
            sum(bool(p.gaps) for p in QmsProcess.query.all()), url_for("quality.index"))
    return out
