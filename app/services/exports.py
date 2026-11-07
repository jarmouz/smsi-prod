"""Exports des livrables du système de management pour l'auditeur : Déclaration d'applicabilité,
registre des risques, plan de traitement des risques (Excel, Word, PDF).
Chaque export porte l'organisation, la date, l'auteur et un cadre d'approbation."""
import re
from datetime import date, datetime

from flask import Response
from flask_login import current_user

from app.models import Control, Risk
from app.services import docgen, risk_criteria
from app.services import onlyoffice as oo
from app.services.audit_trail import log_event
from app.services.tenancy import current_org

MIMES = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "pdf": "application/pdf"}


def _who():
    return f"{current_user.name} ({current_user.role_label})"


def _criteria_text():
    c = risk_criteria.get()
    lv = c["levels"]
    return (f"Échelle {c['scale']['likelihood']}×{c['scale']['impact']} (vraisemblance × impact). Niveaux : {lv['faible']['label']} 1-{lv['modere']['min'] - 1}, {lv['modere']['label']} "
            f"{lv['modere']['min']}-{lv['eleve']['min'] - 1}, {lv['eleve']['label']} {lv['eleve']['min']}-"
            f"{lv['critique']['min'] - 1}, {lv['critique']['label']} {lv['critique']['min']}-{risk_criteria.max_score()}. "
            f"Seuil d'acceptation : score résiduel ≤ {c['acceptance']}.")


# --- Données ------------------------------------------------------------------
def _dda_scope():
    """Norme et vue de l'export DdA / conformité (paramètres norme et vue de la page) : 27001 par défaut."""
    from flask import has_request_context, request
    from app.services import frameworks as fw_svc
    fw = None
    if has_request_context() and request.args.get("norme"):
        fw = next((f for f in fw_svc.controls_frameworks() if f.code == request.args["norme"]), None)
    fw = fw or fw_svc.get(fw_svc.CORE)
    clauses = fw.kind != "controls" or (has_request_context() and request.args.get("vue") == "exigences")
    return fw, ("clause" if clauses else "control")


def _dda_meta():
    fw, kind = _dda_scope()
    if kind == "control":
        return f"Déclaration d'applicabilité - {fw.name}", f"{fw.name}, Annexe A ; ISO/IEC 27001:2022 6.1.3 d)"
    if fw.kind == "common":
        return "Conformité au socle commun du système de management", "Chapitres 4 à 10 (structure harmonisée ISO)"
    return f"Conformité aux exigences - {fw.name}", f"{fw.name}, chapitres 4 à 10"


def soa_rows():
    fw, kind = _dda_scope()
    rows = [["Mesure" if kind == "control" else "Exigence", "Intitulé", "Applicable", "Justification", "Statut",
             "Mise en œuvre", "Responsable", "Preuves"]]
    for c in Control.of(fw.code, kind).order_by(Control.id).all():
        rows.append([c.annex_ref, c.title, "Oui" if c.applicable else "Non", c.justification or "",
                     c.status.label + (" (socle commun)" if c.inherited else ""), c.implementation or "",
                     c.owner.name if c.owner else "", ", ".join(e.ref for e in c.all_evidences)])
    return rows


def _acceptance(r):
    st = r.acceptance_state
    if st == "valid":
        return f"Accepté par {r.accepted_by.name if r.accepted_by else '-'} le {r.accepted_at:%d/%m/%Y}"
    return {"required": "À accepter", "expired": "Acceptation expirée", "outdated": "À ré-accepter",
            "not_applicable": "Sans objet (opportunité)"}.get(st, "Dans les critères")


def _norms(r):
    from app.services import frameworks as fw_svc
    names = {f.code: f.short_name for f in fw_svc.active()}
    return ", ".join(names[c] for c in r.framework_codes if c in names)


def _dims(r):
    return ", ".join(f"{risk_criteria.DIMENSION_LABELS.get(k, k)} {v}" for k, v in sorted(r.impact_by_dim.items()))


def _links(r):
    from app.services import risk_links
    return "; ".join(f"{label} : " + ", ".join(getattr(o, "ref", "") for _, o, _u in rows)
                     for label, rows in risk_links.links_for_risk(r))


def _measure_ref(c):
    return c.annex_ref if c.framework.code == "ISO27001" else f"{c.framework.short_name} {c.annex_ref}"


def _risks():
    return sorted(Risk.query.all(), key=lambda r: (r.is_opportunity, -r.effective_score, r.ref))


def risk_rows():
    rows = [["Réf.", "Risque", "Nature", "Domaine", "Normes", "Actif / périmètre", "Menace ou cause",
             "Vulnérabilité ou facteur aggravant", "V", "I", "Score inhérent",
             "Niveau inhérent", "Traitement", "V rés.", "I rés.", "Score résiduel", "Niveau résiduel",
             "Acceptation", "Statut", "Propriétaire", "Prochaine revue", "Éléments liés", "Réévaluation demandée",
             "Conséquences", "Impacts par dimension"]]
    for r in _risks():
        rows.append([r.ref, r.title, "Opportunité" if r.is_opportunity else "Risque", r.domain_label, _norms(r),
                     r.asset or "", r.threat or "", r.vulnerability or "", r.likelihood, r.impact,
                     r.inherent_score, risk_criteria.label_of(r.display_inherent_level), r.treatment.label,
                     r.residual_likelihood or "", r.residual_impact or "", r.residual_score or "",
                     risk_criteria.label_of(r.display_level), _acceptance(r), r.status.label,
                     r.owner.name if r.owner else "", r.review_date.strftime("%d/%m/%Y") if r.review_date else "",
                     _links(r), r.reassess_reason or "", r.consequence or "", _dims(r)])
    return rows


def plan_rows():
    rows = [["Réf.", "Risque", "Niveau inhérent", "Option de traitement", "Mesures d'annexe et état",
             "Actions (responsable, échéance, état)", "Ressources", "Avancement", "Propriétaire",
             "Niveau résiduel", "Acceptation du risque résiduel", "Échéance de revue"]]
    for r in _risks():
        if r.status.value == "CLOTURE" and r.treatment.value != "EVITER":
            continue
        measures = "; ".join(f"{_measure_ref(c)} {c.status.label.lower()}" for c in r.controls) or "-"
        title = f"{r.title} (opportunité)" if r.is_opportunity else r.title
        acts = [a for a in r.actions if a.status.value != "ABANDONNEE"]
        actions = "\n".join(f"- {a.title} ({a.owner.name if a.owner else 'sans responsable'}, "
                             f"{a.due_date.strftime('%d/%m/%Y') if a.due_date else 'sans échéance'}, "
                             f"{a.status.label.lower()}{', en retard' if a.is_overdue else ''})" for a in acts) or "-"
        resources = "\n".join(f"- {a.resources}" for a in acts if a.resources) or ""
        progress = f"{r.plan_progress} %" if r.plan_progress is not None else "-"
        rows.append([r.ref, title, f"{r.inherent_score} - {risk_criteria.label_of(r.display_inherent_level)}",
                     r.treatment.label, measures, actions, resources, progress, r.owner.name if r.owner else "",
                     f"{r.effective_score} - {risk_criteria.label_of(r.display_level)}", _acceptance(r),
                     r.review_date.strftime("%d/%m/%Y") if r.review_date else ""])
    return rows


def action_rows():
    """Suivi des actions du plan de traitement (une ligne par action)."""
    from app.models import RiskAction
    rows = [["Risque", "Intitulé du risque", "Action", "Mesure", "Responsable", "Échéance", "Statut",
             "Avancement", "Ressources", "Résultat / preuve", "Réalisée le"]]
    acts = sorted(RiskAction.query.all(), key=lambda a: (not a.status.is_open, a.due_date is None,
                                                         a.due_date or date.max, a.risk.ref))
    for a in acts:
        rows.append([a.risk.ref, a.risk.title, a.title, _measure_ref(a.control) if a.control else "",
                     a.owner.name if a.owner else "", a.due_date.strftime("%d/%m/%Y") if a.due_date else "",
                     a.status.label + (" (en retard)" if a.is_overdue else ""), f"{a.progress} %", a.resources or "",
                     a.note or "", a.completed_at.strftime("%d/%m/%Y") if a.completed_at else ""])
    return rows


# --- Mise en forme --------------------------------------------------------------
DOCS = {
    "dda": {"title": "Déclaration d'applicabilité", "rows": soa_rows, "clause": "ISO/IEC 27001:2022, 6.1.3 d)",
            "meta": _dda_meta,
            "widths": [900, 2600, 900, 3300, 1100, 3300, 1300, 1170], "approver": "Direction / RSSI"},
    "registre-risques": {"title": "Registre des risques", "rows": risk_rows, "clause": "Chapitres 6.1 et 8 des normes de systèmes de management (ISO/IEC 27001:2022, 6.1.2 et 8.2)",
                         "widths": None, "approver": "RSSI",
                         # Réf., Risque, Normes, Score inh., Traitement, Score rés., Niveau rés., Acceptation, Statut, Propriétaire
                         "pdf_keep": ([0, 1, 4, 10, 12, 15, 16, 17, 18, 19],
                                      [1150, 2800, 1700, 850, 1250, 850, 1100, 2000, 1100, 1770])},
    "actions-traitement": {"title": "Suivi des actions de traitement des risques", "rows": action_rows,
                           "clause": "Chapitres 6.1 et 8 des normes de systèmes de management (ISO/IEC 27001:2022, 6.1.3 e) et 8.3)",
                           "widths": None, "approver": "RSSI",
                           # Risque, Action, Mesure, Responsable, Échéance, Statut, Avancement, Résultat
                           "pdf_keep": ([0, 2, 3, 4, 5, 6, 7, 9], [1000, 3600, 1300, 1500, 1100, 1500, 900, 3670])},
    "plan-traitement": {"title": "Plan de traitement des risques", "rows": plan_rows, "clause": "Chapitres 6.1 et 8 des normes de systèmes de management (ISO/IEC 27001:2022, 6.1.3 e) et f), 8.3)",
                        "widths": [900, 1780, 950, 1000, 1650, 2200, 1100, 640, 1100, 950, 1300, 1000],
                        "approver": "Propriétaires des risques"},
}


# --- Registres P2 -----------------------------------------------------------------
def _d(v):
    return v.strftime("%d/%m/%Y") if v else ""


def context_sections():
    from app.blueprints.context import SCOPE_FIELDS, scope
    from app.models import ContextIssue, InterestedParty
    sc = scope()
    scope_rows = [["Élément", "Description"]] + [[label, sc[k] or "-"] for k, label in SCOPE_FIELDS]
    issues = [["Réf.", "Type", "Catégorie", "Enjeu", "Effet sur le système de management", "Prise en compte", "Risques"]]
    for i in ContextIssue.query.filter_by(active=True).order_by(ContextIssue.kind, ContextIssue.ref):
        issues.append([i.ref, i.kind.label, i.category.label, i.title, i.effect or "", i.response or "",
                       ", ".join(r.ref for r in i.risks)])
    parties = [["Réf.", "Partie intéressée", "Catégorie", "Besoins et attentes", "Retenues", "Réponse du système de management",
                "Exigences"]]
    for p in InterestedParty.query.order_by(InterestedParty.ref):
        parties.append([p.ref, p.name, p.category.label, p.expectations or "", "Oui" if p.retained else "Non",
                        p.response or "", ", ".join(r.ref for r in p.requirements)])
    return [("Périmètre (4.3)", scope_rows, [3600, 10970]),
            ("Enjeux internes et externes (4.1)", issues, [900, 1300, 1700, 2900, 3100, 3300, 1370]),
            ("Parties intéressées (4.2)", parties, [900, 2300, 1600, 3600, 900, 3600, 1670])]


def indicator_sections():
    from app.models import Objective, Indicator
    objs = [["Réf.", "Objectif", "Ce qui sera fait", "Ressources", "Responsable", "Échéance", "Évaluation", "Statut"]]
    for o in Objective.query.order_by(Objective.ref):
        objs.append([o.ref, o.title, o.actions or "", o.resources or "", o.owner.name if o.owner else "",
                     _d(o.due_date), o.evaluation or "", o.status.label])
    states = {"ok": "Atteint", "alerte": "Alerte", "hors_cible": "Hors cible", None: "Pas de mesure"}
    kpis = [["Réf.", "Indicateur", "Objectif", "Méthode", "Fréquence", "Mesuré par", "Cible", "Dernière valeur",
             "Période", "État"]]
    for i in Indicator.query.order_by(Indicator.ref):
        kpis.append([i.ref, i.name, i.objective.ref if i.objective else "-", i.method or "", i.frequency.label,
                     i.owner.name if i.owner else "", ("≥ " if i.direction.value == "HAUSSE" else "≤ ") + i.fmt(i.target),
                     i.fmt(i.last.value) if i.last else "-", _d(i.last.period) if i.last else "", states[i.state]])
    return [("Objectifs de sécurité (6.2)", objs, [1300, 2500, 2600, 1800, 1400, 1150, 2500, 1320]),
            ("Indicateurs (9.1)", kpis, [900, 2500, 1300, 3100, 1150, 1400, 950, 1050, 1150, 1070])]


def nc_sections():
    from app.models import NonConformity
    rows = [["Réf.", "Non-conformité", "Origine", "Gravité", "Cause racine", "Actions correctives", "Efficacité", "Statut"]]
    for n in NonConformity.query.order_by(NonConformity.ref):
        acts = "; ".join(f"{a.description} ({a.status.label.lower()})" for a in n.actions)
        eff = f"Vérifiée le {_d(n.effectiveness_at)} par {n.effectiveness_by.name}" if n.effectiveness_at and n.effectiveness_by else ""
        rows.append([n.ref, n.title, n.source.label, n.severity.label, n.root_cause or "", acts, eff, n.status.label])
    return [("Non-conformités et actions correctives (10.2)", rows, [1200, 2600, 1500, 900, 2700, 3200, 1500, 970])]


def supplier_sections():
    from app.models import Supplier
    rows = [["Réf.", "Fournisseur", "Service", "Criticité", "Accès aux données", "Clauses", "DPA", "Certifications",
             "Évaluation", "Prochaine", "Écarts"]]
    for s in Supplier.query.order_by(Supplier.ref):
        rows.append([s.ref, s.name, s.service or "", s.criticality.label, s.data_access.label,
                     "Oui" if s.security_clauses else "Non", "Oui" if s.dpa else "Non", s.certifications or "",
                     f"{s.assessment_result.label} {_d(s.last_assessment)}".strip(), _d(s.next_assessment),
                     ", ".join(s.gaps)])
    return [("Registre des fournisseurs (A.5.19 - A.5.22)", rows,
             [850, 1700, 2200, 950, 1300, 750, 650, 1900, 1500, 1150, 1620])]


def requirement_sections():
    from app.models import Requirement
    rows = [["Réf.", "Exigence", "Type", "Référence", "Obligation", "Mise en conformité", "Mesures", "Conformité",
             "Prochaine revue"]]
    for r in Requirement.query.order_by(Requirement.ref):
        rows.append([r.ref, r.title, r.req_type.label, r.source or "", r.obligation or "", r.response or "",
                     ", ".join(c.annex_ref for c in r.controls), r.status.label, _d(r.next_review)])
    return [("Exigences légales, réglementaires et contractuelles (A.5.31)", rows,
             [850, 1900, 1050, 1700, 2820, 2900, 1050, 1150, 1150])]


DOCS.update({
    "contexte": {"title": "Contexte, parties intéressées et périmètre", "sections": context_sections,
                 "clause": "Chapitres 4.1 à 4.3 des normes de systèmes de management", "approver": "Direction", "criteria": False},
    "indicateurs": {"title": "Objectifs et indicateurs", "sections": indicator_sections,
                    "clause": "Chapitres 6.2 et 9.1 des normes de systèmes de management", "approver": "RSSI", "criteria": False},
    "non-conformites": {"title": "Registre des non-conformités", "sections": nc_sections,
                        "clause": "Chapitre 10.2 des normes de systèmes de management", "approver": "RSSI", "criteria": False},
    "fournisseurs": {"title": "Registre des fournisseurs", "sections": supplier_sections,
                     "clause": "Maîtrise des prestataires (ISO/IEC 27001 A.5.19 à A.5.22, ISO 9001 8.4, ISO/IEC 20000-1 8.2.3)", "approver": "RSSI", "criteria": False},
    "exigences": {"title": "Registre des exigences légales et contractuelles", "sections": requirement_sections,
                  "clause": "Chapitre 4.2 des normes de systèmes de management (ISO/IEC 27001 A.5.31)", "approver": "Juridique / RSSI", "criteria": False},
})


def programme_sections():
    from app.models import AuditPlanItem, AUDIT_DOMAINS
    from app.blueprints.audits import _programme_years
    years = _programme_years()
    items = {(i.year, i.domain): i for i in AuditPlanItem.query.filter(AuditPlanItem.year.in_(years))}
    rows = [["Domaine"] + [str(y) for y in years]]
    for code, label in AUDIT_DOMAINS:
        row = [label]
        for y in years:
            it = items.get((y, code))
            row.append("" if not it else " - ".join(x for x in [f"T{it.quarter}" if it.quarter else "Prévu",
                                                                 it.auditor.name if it.auditor else "",
                                                                 it.audit.ref if it.audit else ""] if x))
        rows.append(row)
    rest = 14570 - 3170
    return [("Programme d'audit (9.2.2)", rows, [3170] + [rest // len(years)] * (len(years) - 1) + [rest - rest // len(years) * (len(years) - 1)])]


def competence_sections():
    from app.models import CompetenceRequirement, CompetenceRecord
    cov = [["Compétence requise", "Renouvellement", "Personne", "Preuve valide", "Expire le"]]
    for r in CompetenceRequirement.query.order_by(CompetenceRequirement.title):
        for u in r.users:
            rec = r.valid_record(u.id)
            cov.append([r.title, f"{r.validity_months} mois" if r.validity_months else "Permanente", u.name,
                        rec.title if rec else "ÉCART : aucune preuve valide", _d(rec.expires_at) if rec else ""])
    recs = [["Personne", "Preuve", "Type", "Organisme", "Obtenue", "Expire"]]
    for c in CompetenceRecord.query.order_by(CompetenceRecord.user_id):
        recs.append([c.user.name, c.title, c.ctype.label, c.provider or "", _d(c.obtained_at), _d(c.expires_at)])
    return [("Couverture des compétences requises (7.2)", cov, [3600, 1600, 2600, 4970, 1800]),
            ("Preuves de compétence", recs, [2600, 4700, 1500, 2470, 1650, 1650])]


def continuity_sections():
    from app.models import BusinessProcess, ContinuityTest
    h = lambda v: f"{v:g} h".replace(".", ",") if v is not None else ""  # noqa: E731
    bia = [["Réf.", "Activité", "Criticité", "DMIA", "RTO", "RPO", "Dépendances", "Stratégie", "Dernier test"]]
    for p in sorted(BusinessProcess.query.all(), key=lambda p: (-p.criticality, p.ref)):
        lt = p.last_test
        bia.append([p.ref, p.name, p.criticality_label, h(p.mtpd_hours), h(p.rto_hours), h(p.rpo_hours),
                    p.dependencies or "", p.strategy or "",
                    f"{lt.ref} {_d(lt.test_date)} ({lt.result.label})" if lt else "Jamais testée"])
    tests = [["Réf.", "Exercice", "Type", "Date", "Activités", "RTO atteint", "Résultat", "Constats"]]
    for t in ContinuityTest.query.order_by(ContinuityTest.test_date):
        tests.append([t.ref, t.title, t.ttype.label, _d(t.test_date), ", ".join(p.ref for p in t.processes),
                      h(t.achieved_rto_hours), t.result.label, t.findings or ""])
    return [("Analyse d'impact sur l'activité (BIA)", bia, [1000, 2300, 1000, 800, 800, 800, 2800, 2970, 2100]),
            ("Exercices et tests de continuité (A.5.30)", tests, [1350, 2500, 1500, 1150, 1500, 1050, 1400, 4120])]


def change_sections():
    from app.models import ChangeRequest
    rows = [["Réf.", "Changement", "Type", "Risque", "Demandeur", "Approbation", "Réalisé", "Revue post-changement", "Statut"]]
    for c in ChangeRequest.query.order_by(ChangeRequest.ref):
        appr = f"{c.approved_by.name} {_d(c.approved_at)}" if c.approved_by else ""
        rows.append([c.ref, c.title, c.kind.label, c.risk_level.label, c.requested_by.name if c.requested_by else "",
                     appr, _d(c.done_at), c.review_note or "", c.status.label])
    return [("Registre des changements (6.3, A.8.32)", rows, [1250, 2700, 1700, 850, 1500, 1900, 1100, 2420, 1150])]


DOCS.update({
    "programme-audit": {"title": "Programme d'audit interne", "sections": programme_sections,
                        "clause": "Chapitre 9.2.2 des normes de systèmes de management", "approver": "Direction / RSSI", "criteria": False},
    "competences": {"title": "Registre des compétences", "sections": competence_sections,
                    "clause": "Chapitre 7.2 des normes de systèmes de management", "approver": "RSSI / RH", "criteria": False},
    "continuite": {"title": "Analyse d'impact et exercices de continuité", "sections": continuity_sections,
                   "clause": "ISO 22301 8.2 et 8.5 ; ISO/IEC 27001 A.5.29 et A.5.30", "approver": "Direction", "criteria": False},
    "changements": {"title": "Registre des changements", "sections": change_sections,
                    "clause": "Chapitre 6.3 des normes de systèmes de management (ISO/IEC 27001 A.8.32, ISO/IEC 20000-1 8.5.1)", "approver": "RSSI", "criteria": False},
})


def _sections(spec, for_pdf):
    """Liste (titre, lignes, largeurs) ; les registres P1 n'ont qu'une section."""
    if "sections" in spec:
        return spec["sections"]()
    rows, widths = spec["rows"](), spec["widths"]
    if not widths and for_pdf and "pdf_keep" in spec:   # colonnes essentielles en format paysage
        keep, widths = spec["pdf_keep"]
        rows = [[row[i] for i in keep] for row in rows]
    return [(spec["title"], rows, widths)]


def _header(spec, now):
    org = current_org()
    out = [("Organisation", org.name if org else ""), ("Document", spec["title"]), ("Référence normative", spec["clause"]),
           ("Généré le", now.strftime("%d/%m/%Y à %H:%M (UTC)")), ("Généré par", _who())]
    if spec.get("criteria", True):
        out.append(("Critères de risque", _criteria_text()))
    return out


def build(kind, fmt):
    """Retourne (octets, nom de fichier) ; fmt ∈ xlsx, docx, pdf."""
    spec = dict(DOCS[kind])
    if "meta" in spec:                      # titre et référence selon la norme exportée
        spec["title"], spec["clause"] = spec["meta"]()
    now = datetime.utcnow()
    org = current_org()
    base = f"{spec['title']} - {org.slug if org else ''} - {now:%Y-%m-%d}"
    sections = _sections(spec, fmt != "xlsx")
    if fmt == "xlsx":
        info = [["Champ", "Valeur"]] + [list(x) for x in _header(spec, now)] + [
            ["Approbation", f"{spec['approver']} : nom, fonction, date, signature"]]
        sheets = [(re.sub(r"[\\/*?:\[\]]", "-", t)[:31], rows) for t, rows, _ in sections]
        return docgen.xlsx(sheets + [("Informations", info)]), base + ".xlsx"
    blocks = [("title", spec["title"]),
              ("subtitle", f"{org.name if org else ''} - {spec['clause']} - généré le {now:%d/%m/%Y} par {_who()}")]
    if spec.get("criteria", True):
        blocks.append(("p", _criteria_text()))
    for title, rows, widths in sections:
        if len(sections) > 1:
            blocks.append(("h2", title))
        blocks.append(("table", (rows, widths) if widths else rows))
    blocks += [("h2", "Approbation"),
               ("table", ([["Rôle", "Nom", "Fonction", "Date", "Signature"], [spec["approver"], "", "", "", ""]],
                          [2400, 3200, 3200, 2000, 3770]))]
    data = docgen.docx(blocks, landscape=True, font_size=8)
    if fmt == "docx":
        return data, base + ".docx"
    return oo.convert(data, "docx", "pdf"), base + ".pdf"


def response(kind, fmt):
    data, name = build(kind, fmt)
    log_event("export", f"Export {_dda_meta()[0] if kind == 'dda' else DOCS[kind]['title']} ({fmt.upper()})")
    from urllib.parse import quote
    return Response(data, mimetype=MIMES[fmt],
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
