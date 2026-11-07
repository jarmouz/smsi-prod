"""Synthèse des modules de pilotage (P2) pour le tableau de bord et la revue de direction."""
from app.models import (BusinessProcess, ChangeRequest, ChangeStatus, CompetenceRequirement, NonConformity, Finding, Indicator, Objective, Supplier, Requirement, FindingType, NcStatus,
                        ObjectiveStatus, SupplierStatus, ComplianceStatus, NcSeverity)


def summary():
    ncs = NonConformity.query.all()
    tracked = {n.finding_id for n in ncs if n.finding_id}
    # constats d'audit NC encore ouverts et pas encore suivis dans le registre 10.2
    untracked = [f for f in Finding.query.filter(Finding.type.in_([FindingType.NC_MAJEURE, FindingType.NC_MINEURE]),
                                                 Finding.closed.is_(False)) if f.id not in tracked]
    open_ncs = [n for n in ncs if n.status != NcStatus.CLOTUREE]
    kpis = Indicator.query.filter_by(active=True).all()
    objectives = Objective.query.all()
    suppliers = [s for s in Supplier.query.all() if s.status == SupplierStatus.ACTIF]
    reqs = Requirement.query.all()
    return {
        "nc_open": len(open_ncs) + len(untracked),
        "nc_major": sum(n.severity == NcSeverity.MAJEURE for n in open_ncs),
        "nc_verify": sum(n.status == NcStatus.A_VERIFIER for n in open_ncs),
        "nc_closed": sum(n.status == NcStatus.CLOTUREE for n in ncs),
        "kpi_total": len(kpis),
        "kpi_ok": sum(k.state == "ok" for k in kpis),
        "kpi_off": sum(k.state == "hors_cible" for k in kpis),
        "kpi_due": sum(k.measurement_due for k in kpis),
        "obj_total": len(objectives),
        "obj_reached": sum(o.status == ObjectiveStatus.ATTEINT for o in objectives),
        "obj_overdue": sum(o.is_overdue for o in objectives),
        "sup_total": len(suppliers),
        "sup_gaps": sum(bool(s.gaps) for s in suppliers),
        "req_total": len(reqs),
        "req_nok": sum(r.status in (ComplianceStatus.NON_CONFORME, ComplianceStatus.PARTIEL) for r in reqs),
        "req_todo": sum(r.status == ComplianceStatus.A_EVALUER for r in reqs),
        "bcp_overdue": sum(p.test_overdue for p in BusinessProcess.query.all()),
        "chg_pending": ChangeRequest.query.filter(ChangeRequest.status.in_([ChangeStatus.DEMANDE, ChangeStatus.REALISE])).count(),
        "comp_gaps": sum(len(r.gaps) for r in CompetenceRequirement.query.all()),
    }
