"""Récapitulatif des échéances par e-mail : chaque utilisateur reçoit la liste de
ce qui l'attend (retards et échéances proches) dans son organisation.

Exécuté chaque jour par `flask send-reminders` (cron de l'hôte) ; chacun choisit
sa fréquence dans « Mon compte » (quotidien, hebdomadaire le lundi, jamais)."""
from datetime import date, datetime, timedelta
from html import escape

from flask import current_app, url_for

from app.extensions import db
from app.models import (
    Organization, User, Role, CorrectiveAction, ReviewAction, Document, Risk, Indicator, Objective, NonConformity,
    Supplier, Requirement, CompetenceRecord, CompetenceRequirement, BusinessProcess, ContinuityTest, ChangeRequest,
    Incident, AuditPlanItem, ActionStatus, DocStatus, ObjectiveStatus, NcStatus, SupplierStatus, IncidentStatus,
    TestResult, ChangeStatus, ChangeRisk,
)
from app.services import settings as settings_svc, mailer
from app.services.tenancy import tenant_scope

SKIP_DOMAINS_DEFAULT = ".demo,.local,.test,.example,example.com"


def _due(d, today):
    if d is None:
        return ""
    delta = (d - today).days
    if delta < 0:
        return f"en retard depuis le {d:%d/%m/%Y}"
    return "aujourd'hui" if delta == 0 else f"échéance le {d:%d/%m/%Y}"


def collect(user, today=None):
    """Sections [(titre, [(libellé, url, échéance, en_retard)])] pour un utilisateur (organisation courante)."""
    t = today or date.today()
    soon7, soon30 = t + timedelta(days=7), t + timedelta(days=30)
    is_rssi = user.role == Role.RSSI
    is_auditor = user.role in (Role.RSSI, Role.AUDITEUR)
    S = {}

    def add(section, label, url, when="", late=False):
        S.setdefault(section, []).append((label, url, when, late))

    for a in CorrectiveAction.query.filter(CorrectiveAction.owner_id == user.id,
                                           CorrectiveAction.status.in_([ActionStatus.OUVERTE, ActionStatus.EN_COURS])):
        if a.due_date and a.due_date <= soon7:
            url = url_for("audits.detail", audit_id=a.finding.audit_id) if a.finding else \
                url_for("nonconformities.detail", nc_id=a.nonconformity_id)
            add("Actions correctives", f"{a.origin_ref} : {a.description}", url, _due(a.due_date, t), a.due_date < t)
    for a in ReviewAction.query.filter(ReviewAction.owner_id == user.id,
                                       ReviewAction.status.in_([ActionStatus.OUVERTE, ActionStatus.EN_COURS])):
        if a.due_date and a.due_date <= soon7:
            add("Actions de revue de direction", f"{a.review.ref} : {a.description}",
                url_for("reviews.detail", review_id=a.review_id), _due(a.due_date, t), a.due_date < t)
    for n in NonConformity.query.filter(NonConformity.owner_id == user.id, NonConformity.status != NcStatus.CLOTUREE):
        add("Non-conformités", f"{n.ref} : {n.title} ({n.status.label.lower()})",
            url_for("nonconformities.detail", nc_id=n.id), _due(n.effectiveness_due, t),
            bool(n.effectiveness_due and n.effectiveness_due < t))
    if is_auditor:
        for n in NonConformity.query.filter(NonConformity.status == NcStatus.A_VERIFIER, NonConformity.owner_id != user.id):
            add("Efficacité à vérifier", f"{n.ref} : {n.title}", url_for("nonconformities.detail", nc_id=n.id))
    for d in Document.query.filter(Document.owner_id == user.id, Document.status != DocStatus.OBSOLETE,
                                   Document.next_review_at.isnot(None), Document.next_review_at <= soon30):
        add("Documents à revoir", f"{d.ref} : {d.title}", url_for("documents.detail", doc_id=d.id),
            _due(d.next_review_at, t), d.next_review_at < t)
    if is_rssi:
        for d in Document.query.filter(Document.status == DocStatus.EN_REVUE):
            add("Documents à approuver", f"{d.ref} : {d.title} (v{d.version})", url_for("documents.detail", doc_id=d.id))
    for r in Risk.query.filter(Risk.owner_id == user.id):
        if r.acceptance_state in ("required", "expired", "outdated"):
            add("Risques résiduels à accepter", f"{r.ref} : {r.title} (score {r.effective_score})",
                url_for("risks.detail", risk_id=r.id))
        elif r.status.is_open and r.reassess_at:
            add("Risques à réévaluer", f"{r.ref} : {r.title} ({r.reassess_reason})", url_for("risks.detail", risk_id=r.id))
        elif r.status.is_open and r.review_date and r.review_date <= soon7:
            add("Risques à réévaluer", f"{r.ref} : {r.title}", url_for("risks.detail", risk_id=r.id),
                _due(r.review_date, t), r.review_date < t)
    from app.models import Asset
    for a in Asset.query.filter(Asset.owner_id == user.id).all():
        if a.eos_state:
            add("Actifs en fin de support", f"{a.ref} : {a.name}", url_for("assets.detail", asset_id=a.id),
                _due(a.end_of_support, t), a.eos_state == "depassee")
        if a.disposal_missing:
            add("Élimination d'actifs à prouver", f"{a.ref} : {a.name}", url_for("assets.detail", asset_id=a.id))
    from app.services import policies
    for d in policies.pending_for(user):
        add("Politiques à lire et accepter", f"{d.ref} : {d.title} (v{d.version})",
            url_for("documents.detail", doc_id=d.id) + "#acceptation", _due(d.ack_due, t) if d.ack_due else None,
            bool(d.ack_due and d.ack_due < t))
    from app.models import RiskAction, RiskActionStatus
    for a in RiskAction.query.filter(RiskAction.owner_id == user.id,
                                     RiskAction.status.in_([RiskActionStatus.PREVUE, RiskActionStatus.EN_COURS]),
                                     RiskAction.due_date.isnot(None), RiskAction.due_date <= soon7):
        add("Actions de traitement des risques", f"{a.risk.ref} : {a.title}",
            url_for("risks.detail", risk_id=a.risk_id) + "#plan", _due(a.due_date, t), a.due_date < t)
    for i in Indicator.query.filter(Indicator.owner_id == user.id, Indicator.active.is_(True)):
        if i.measurement_due:
            add("Mesures d'indicateurs attendues", f"{i.ref} : {i.name} ({i.frequency.label.lower()})",
                url_for("objectives.indicator", ind_id=i.id))
    for o in Objective.query.filter(Objective.owner_id == user.id,
                                    Objective.status.in_([ObjectiveStatus.PLANIFIE, ObjectiveStatus.EN_COURS])):
        if o.due_date and o.due_date <= soon30:
            add("Objectifs de sécurité", f"{o.ref} : {o.title}", url_for("objectives.index"), _due(o.due_date, t),
                o.due_date < t)
    for s in Supplier.query.filter(Supplier.owner_id == user.id, Supplier.status == SupplierStatus.ACTIF):
        if s.next_assessment is None or s.next_assessment <= soon30:
            add("Fournisseurs à évaluer", f"{s.ref} : {s.name}", url_for("suppliers.detail", sup_id=s.id),
                _due(s.next_assessment, t) or "jamais évalué", s.next_assessment is None or s.next_assessment < t)
        if s.contract_end and t <= s.contract_end <= t + timedelta(days=60):
            add("Contrats fournisseurs à renouveler", f"{s.ref} : {s.name}", url_for("suppliers.detail", sup_id=s.id),
                _due(s.contract_end, t))
    for q in Requirement.query.filter(Requirement.owner_id == user.id, Requirement.next_review.isnot(None),
                                      Requirement.next_review <= soon30):
        add("Exigences légales à revoir", f"{q.ref} : {q.title}", url_for("requirements.index") + f"#r{q.id}",
            _due(q.next_review, t), q.next_review < t)
    for c in CompetenceRecord.query.filter(CompetenceRecord.user_id == user.id, CompetenceRecord.expires_at.isnot(None),
                                           CompetenceRecord.expires_at <= t + timedelta(days=60)):
        add("Vos compétences à renouveler", c.title, url_for("competences.index"), _due(c.expires_at, t), c.expires_at < t)
    if is_rssi:
        gaps = sum(len(r.gaps) for r in CompetenceRequirement.query.all())
        if gaps:
            add("Compétences", f"{gaps} écart(s) de compétence sans preuve valide", url_for("competences.index"))
    for p in BusinessProcess.query.filter(BusinessProcess.owner_id == user.id):
        if p.test_overdue:
            add("Continuité d'activité", f"{p.ref} : {p.name} - test de continuité à planifier",
                url_for("continuity.index"))
    for x in ContinuityTest.query.filter(ContinuityTest.owner_id == user.id, ContinuityTest.result == TestResult.PLANIFIE,
                                         ContinuityTest.test_date.isnot(None), ContinuityTest.test_date <= t + timedelta(days=14)):
        add("Continuité d'activité", f"{x.ref} : {x.title}", url_for("continuity.test_detail", test_id=x.id),
            _due(x.test_date, t), x.test_date < t)
    if is_rssi:
        for c in ChangeRequest.query.filter(ChangeRequest.status == ChangeStatus.DEMANDE):
            if c.risk_level == ChangeRisk.FAIBLE or c.requested_by_id != user.id:
                add("Changements à approuver", f"{c.ref} : {c.title} (risque {c.risk_level.label.lower()})",
                    url_for("changes.detail", change_id=c.id), _due(c.planned_date, t))
    if is_auditor:
        for c in ChangeRequest.query.filter(ChangeRequest.status == ChangeStatus.REALISE):
            add("Revues post-changement", f"{c.ref} : {c.title}", url_for("changes.detail", change_id=c.id))
    for c in ChangeRequest.query.filter(ChangeRequest.requested_by_id == user.id, ChangeRequest.status == ChangeStatus.APPROUVE,
                                        ChangeRequest.planned_date.isnot(None), ChangeRequest.planned_date <= soon7):
        add("Changements à réaliser", f"{c.ref} : {c.title}", url_for("changes.detail", change_id=c.id),
            _due(c.planned_date, t), c.planned_date < t)
    for i in Incident.query.filter(Incident.assignee_id == user.id,
                                   Incident.status.in_([IncidentStatus.NOUVEAU, IncidentStatus.EN_COURS])):
        add("Incidents à traiter", f"{i.ref} : {i.title} ({i.severity.label.lower()})",
            url_for("incidents.detail", incident_id=i.id))
    quarter = (t.month - 1) // 3 + 1
    for it in AuditPlanItem.query.filter(AuditPlanItem.auditor_id == user.id, AuditPlanItem.year == t.year,
                                         AuditPlanItem.audit_id.is_(None)):
        if it.quarter and it.quarter <= quarter:
            from app.models import AUDIT_DOMAINS
            add("Programme d'audit", f"Audit {dict(AUDIT_DOMAINS)[it.domain]} prévu au T{it.quarter} {it.year}",
                url_for("audits.programme"), "", it.quarter < quarter)
    return [(k, v) for k, v in S.items()]


def render(user, org, sections, base_url):
    total = sum(len(v) for _, v in sections)
    late = sum(1 for _, v in sections for x in v if x[3])
    rows = []
    for title, items in sections:
        rows.append(f'<tr><td colspan="2" style="padding:16px 0 6px;font-weight:700;color:#1F3A8A;font-size:14px;">'
                    f'{escape(title)} ({len(items)})</td></tr>')
        for label, url, when, is_late in items:
            color = "#C0392B" if is_late else "#5B6676"
            rows.append(f'<tr><td style="padding:5px 0;border-top:1px solid #E3E8EF;font-size:13px;">'
                        f'<a href="{escape(base_url + url)}" style="color:#1F2937;text-decoration:none;">{escape(label)}</a></td>'
                        f'<td style="padding:5px 0 5px 12px;border-top:1px solid #E3E8EF;font-size:12px;color:{color};'
                        f'white-space:nowrap;text-align:right;">{escape(when)}</td></tr>')
    pref = escape(base_url + url_for("account.home"))
    return (f'<div style="font-family:Montserrat,Arial,sans-serif;max-width:640px;margin:0 auto;color:#1F2937;">'
            f'<h2 style="color:#1F3A8A;margin:0 0 4px;">Vos échéances Integra</h2>'
            f'<p style="color:#5B6676;margin:0 0 8px;font-size:13px;">{escape(org.name)} - {total} point(s) à traiter'
            f'{f", dont {late} en retard" if late else ""}.</p>'
            f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>'
            f'<p style="color:#5B6676;font-size:11.5px;margin-top:20px;">Bonjour {escape(user.name)}, ce récapitulatif est '
            f'envoyé selon la fréquence choisie dans <a href="{pref}">Mon compte</a>.</p></div>')


def due_today(user, now):
    freq = user.digest_frequency or "HEBDO"
    if freq == "JAMAIS":
        return False
    if user.last_digest_at and user.last_digest_at.date() == now.date():
        return False
    return freq == "QUOTIDIEN" or now.weekday() == 0


def run(dry_run=False, org_slug=None, force=False, log=print):
    """Envoie les récapitulatifs dus. Retourne {envoyés, ignorés, erreurs}."""
    now = datetime.utcnow()
    skip = tuple(d.strip().lower() for d in (current_app.config.get("NOTIFY_SKIP_DOMAINS") or SKIP_DOMAINS_DEFAULT).split(",") if d.strip())
    stats = {"envoyés": 0, "sans échéance": 0, "pas aujourd'hui": 0, "erreurs": 0}
    orgs = Organization.query.filter_by(is_active=True)
    if org_slug:
        orgs = orgs.filter_by(slug=org_slug)
    for org in orgs.order_by(Organization.id):
        with tenant_scope(org.id):
            if not settings_svc.notifications_enabled():
                log(f"[{org.slug}] notifications désactivées ou SMTP absent : ignorée")
                continue
            base = settings_svc.get_base_url()
            cfg = settings_svc.get_smtp_config()
            for u in User.query.filter_by(is_active_flag=True, is_readonly=False).order_by(User.id):
                if u.email.lower().endswith(skip):
                    continue
                if not force and not due_today(u, now):
                    stats["pas aujourd'hui"] += 1
                    continue
                sections = collect(u)
                if not sections:
                    stats["sans échéance"] += 1
                    continue
                n = sum(len(v) for _, v in sections)
                if dry_run:
                    log(f"[{org.slug}] {u.email} : {n} point(s) (simulation)")
                    continue
                ok, msg = mailer.send_now(u.email, f"Integra - {n} échéance(s) à traiter", render(u, org, sections, base), cfg)
                if ok:
                    u.last_digest_at = now
                    db.session.commit()
                    stats["envoyés"] += 1
                    log(f"[{org.slug}] {u.email} : {n} point(s) envoyé(s)")
                else:
                    stats["erreurs"] += 1
                    log(f"[{org.slug}] {u.email} : ÉCHEC {msg}")
    return stats
