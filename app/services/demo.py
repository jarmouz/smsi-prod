"""Organisation de démonstration : création et réinitialisation complète.

La réinitialisation ne s'applique qu'à une organisation marquée comme démo
(paramètre demo_org=1) : toutes ses données, ses pièces jointes et ses fichiers
Docs sont supprimés puis rechargés depuis app.demo_content."""
import io
from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy import text
from werkzeug.datastructures import FileStorage

from app import demo_content as C
from app.extensions import db
from app.models import (
    AuditPlanItem, CompetenceRequirement, CompetenceRecord, BusinessProcess, ContinuityTest, ChangeRequest,
    CompetenceType, TestType, TestResult, ChangeKind, ChangeRisk, ChangeStatus,
    ActivityLog, DocumentVersion, ContextIssue, InterestedParty, Objective, Indicator, Measurement,
    NonConformity, Supplier, Requirement, IssueKind, IssueCategory, PartyCategory, ObjectiveStatus, Frequency,
    Direction, NcSource, NcSeverity, NcStatus, SupplierCategory, Criticality, DataAccess, AssessmentResult,
    SupplierStatus, RequirementType, ComplianceStatus,
    Organization, User, Setting, Control, Risk, RiskAction, Audit, Finding, CorrectiveAction,
    ManagementReview, ReviewAction, Document, Evidence, Attachment, Asset, Incident,
    AwarenessAction, Role, ControlStatus, Treatment, RiskStatus, AuditStatus, FindingType,
    ActionStatus, ReviewStatus, DocType, DocStatus, AssetCategory, Classification, AssetStatus,
    IncidentCategory, IncidentSeverity, IncidentStatus, AwarenessType, AwarenessStatus,
)
from app.services import settings as settings_svc, storage, webdav, docgen
from app.services import attachments as att_svc
from app.services.organizations import create_organization, seed_controls
from app.services.tenancy import tenant_scope, current_org
from app.services import audit_trail

DEMO_FLAG = "demo_org"


def demo_org():
    return Organization.query.filter_by(slug=C.ORG_SLUG).first()


def _is_demo(org):
    return Setting.query.filter_by(organization_id=org.id, key=DEMO_FLAG, value="1").first() is not None


def load(log=print):
    """Crée l'organisation de démo, ou la réinitialise si elle existe. Retourne l'organisation."""
    org = demo_org()
    if org is None:
        if User.query.execution_options(all_tenants=True).filter(User.email.like(f"%@{C.DOMAIN}")).first():
            raise RuntimeError(f"Des comptes @{C.DOMAIN} existent hors de l'organisation de démo.")
        org, _ = create_organization(C.ORG_NAME, slug=C.ORG_SLUG)
        with tenant_scope(org.id):
            settings_svc.set_many({DEMO_FLAG: "1"})
        log(f"Organisation {org.name} créée.")
    elif not _is_demo(org):
        raise RuntimeError(f"L'organisation « {org.slug} » n'est pas marquée comme démo : réinitialisation refusée.")
    with tenant_scope(org.id), audit_trail.paused():
        _wipe(org, log)
        _seed(org, log)
    return org


# --------------------------------------------------------------------------
# Effacement (limité à l'organisation de démo)
# --------------------------------------------------------------------------
def _wipe(org, log):
    oid = org.id
    for att in Attachment.query.filter_by(organization_id=oid).all():
        try:
            storage.delete(att.stored_name)
        except Exception as e:  # noqa: BLE001
            log(f"  (fichier {att.filename} non supprimé du stockage : {e})")
    if webdav.enabled():
        try:
            for entry in webdav.list_dir(""):
                webdav.delete(entry["rel"])
        except Exception as e:  # noqa: BLE001
            log(f"  (dossier Docs non vidé : {e})")
    db.session.execute(text("DELETE FROM risk_controls WHERE risk_id IN (SELECT id FROM risks WHERE organization_id = :o)"), {"o": oid})
    db.session.execute(text("DELETE FROM evidence_controls WHERE evidence_id IN (SELECT id FROM evidence WHERE organization_id = :o)"), {"o": oid})
    db.session.execute(text("DELETE FROM issue_risks WHERE issue_id IN (SELECT id FROM context_issues WHERE organization_id = :o)"), {"o": oid})
    db.session.execute(text("DELETE FROM requirement_controls WHERE requirement_id IN (SELECT id FROM requirements WHERE organization_id = :o)"), {"o": oid})
    for table, col, src in (("asset_risks", "risk_id", "risks"), ("process_assets", "process_id", "business_processes"),
                            ("test_processes", "test_id", "continuity_tests"), ("change_assets", "change_id", "change_requests"),
                            ("competence_users", "requirement_id", "competence_requirements")):
        db.session.execute(text(f"DELETE FROM {table} WHERE {col} IN (SELECT id FROM {src} WHERE organization_id = :o)"), {"o": oid})
    # modules des normes (27701, 42001, 22301, 20000-1, 9001) et rattachements : avant les comptes,
    # que leurs responsables référencent sans suppression en cascade
    from app.models import FrameworkLink, RiskLink
    from app.models.ai_system import AiSystem, AiImpactAssessment
    from app.models.privacy import ProcessingActivity, SubjectRequest
    from app.models.service_mgmt import ContinuityPlan, ItService, ServiceMeasure, Problem, Release
    from app.models.quality import QmsProcess, CustomerSurvey, Complaint
    for model in (FrameworkLink, RiskLink, AiImpactAssessment, AiSystem, SubjectRequest, ProcessingActivity,
                  ServiceMeasure, Problem, Release, ItService, ContinuityPlan, Complaint, CustomerSurvey, QmsProcess):
        model.query.filter(model.organization_id == oid).delete(synchronize_session=False)
    for model in (ActivityLog, Attachment, CorrectiveAction, NonConformity, AuditPlanItem, CompetenceRecord,
                  CompetenceRequirement, ContinuityTest, BusinessProcess, ChangeRequest, Measurement, Indicator, Objective,
                  Requirement, InterestedParty, ContextIssue, Supplier, Finding, Audit, ReviewAction, ManagementReview,
                  Incident, Asset, AwarenessAction, DocumentVersion, Document, Evidence, RiskAction, Risk, Control, User):
        model.query.filter(model.organization_id == oid).delete(synchronize_session=False)
    Setting.query.filter(Setting.organization_id == oid, Setting.key.notin_(["org_name", DEMO_FLAG])).delete(synchronize_session=False)
    db.session.commit()
    db.session.expire_all()
    log("Données de démo effacées.")


# --------------------------------------------------------------------------
# Chargement
# --------------------------------------------------------------------------
def _d(j):
    return date.today() + timedelta(days=j) if j is not None else None


def _dt(j):
    return datetime.combine(_d(j), datetime.min.time()) + timedelta(hours=10) if j is not None else None


def _seed(org, log):
    y = date.today().year
    seed_controls()
    # normes restées actives : leur catalogue a été effacé avec les mesures, on le recopie
    from app.services import frameworks
    for f in frameworks.active():
        frameworks.enable(f.code)
    db.session.flush()

    users = {}
    for key, (name, role, job) in C.USERS.items():
        u = User(email=f"{key}@{C.DOMAIN}", name=name, role=Role(role), job_title=job)
        u.set_password(C.DEMO_PASSWORD)
        db.session.add(u)
        users[key] = u
    pkey, pname, pjob = C.PROSPECT
    prospect = User(email=f"{pkey}@{C.DOMAIN}", name=pname, role=Role.LECTEUR, job_title=pjob,
                    is_readonly=True)   # compte partagé : mot de passe non modifiable
    prospect.set_password(C.PROSPECT_PASSWORD)
    db.session.add(prospect)
    akey, aname, ajob = C.DEMO_ADMIN
    admin = User(email=f"{akey}@{C.DOMAIN}", name=aname, role=Role.RSSI, job_title=ajob, is_readonly=True)
    admin.set_password(C.DEMO_ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.flush()
    uid = lambda k: users[k].id if k else None  # noqa: E731
    ctrl = {c.ref: c for c in Control.of().all()}

    # Déclaration d'applicabilité
    status_map = {"I": ControlStatus.IMPLEMENTE, "E": ControlStatus.EN_COURS,
                  "N": ControlStatus.NON_DEMARRE, "X": ControlStatus.NON_APPLICABLE}
    for ref, (st, owner, justif, impl) in C.SOA.items():
        c = ctrl[ref]
        c.applicable = st != "X"
        c.status = status_map[st]
        c.owner_id = uid(owner)
        c.justification = justif
        c.implementation = impl or None

    for i, (name, cat, cls, owner, cust, loc, st, desc) in enumerate(C.ASSETS, 1):
        db.session.add(Asset(ref=f"ACT-{y}-{i:04d}", name=name, category=AssetCategory(cat),
                             classification=Classification(cls), owner_id=uid(owner), custodian=cust or None,
                             location=loc, status=AssetStatus(st), description=desc))

    for i, (title, asset, threat, vuln, l, imp, tr, rl, ri, st, owner, refs, desc) in enumerate(C.RISKS, 1):
        r = Risk(ref=f"R-{y}-{i:04d}", title=title, description=desc, asset=asset, threat=threat,
                 vulnerability=vuln, likelihood=l, impact=imp, treatment=Treatment(tr),
                 residual_likelihood=rl, residual_impact=ri, status=RiskStatus(st), owner_id=uid(owner),
                 review_date=_d(60 + 15 * (i % 6)))
        r.controls = [ctrl[x] for x in refs]
        db.session.add(r)

    db.session.flush()
    from app.models import RiskActionStatus
    risks_by_n = {int(r.ref[-4:]): r for r in Risk.query.all()}
    for n, title, cref, owner, j, st, prog, res, note in C.RISK_ACTIONS:
        a = RiskAction(risk=risks_by_n[n], title=title, control=ctrl.get(cref), owner_id=uid(owner), due_date=_d(j),
                       resources=res, note=note, progress=prog)
        a.set_status(RiskActionStatus(st))
        a.progress = prog
        db.session.add(a)

    incidents = []
    for i, (title, cat, sev, st, j, reporter, owner, cref, desc, impact, resol, jc) in enumerate(C.INCIDENTS, 1):
        inc = Incident(ref=f"INC-{y}-{i:04d}", title=title, description=desc, category=IncidentCategory(cat),
                       severity=IncidentSeverity(sev), status=IncidentStatus(st), detected_at=_d(j),
                       reporter=reporter, assignee_id=uid(owner), control_id=ctrl[cref].id,
                       impact=impact, resolution=resol or None, closed_at=_dt(jc))
        db.session.add(inc)
        incidents.append(inc)

    awareness = []
    for i, (title, typ, st, j, aud, part, rate, notes) in enumerate(C.AWARENESS, 1):
        a = AwarenessAction(ref=f"SENS-{y}-{i:04d}", title=title, atype=AwarenessType(typ),
                            status=AwarenessStatus(st), action_date=_d(j), audience=aud,
                            participants=part, completion_rate=rate, notes=notes)
        db.session.add(a)
        awareness.append(a)

    audits = []
    for spec in C.AUDITS:
        a = Audit(ref=spec["ref"].format(Y=y), title=spec["title"], scope=spec["scope"],
                  planned_date=_d(spec["j"]), status=AuditStatus(spec["status"]),
                  lead_auditor_id=uid(spec["lead"]), summary=spec["summary"] or None)
        db.session.add(a)
        db.session.flush()
        for fref, ftype, ftitle, fdesc, cref, clause, closed, actions in spec["findings"]:
            f = Finding(audit_id=a.id, ref=fref, type=FindingType(ftype), title=ftitle, description=fdesc,
                        control_id=ctrl[cref].id if cref else None, clause=clause, closed=closed)
            db.session.add(f)
            db.session.flush()
            for desc, owner, due, st, done in actions:
                db.session.add(CorrectiveAction(finding_id=f.id, description=desc, owner_id=uid(owner),
                                                due_date=_d(due), status=ActionStatus(st), completed_at=_dt(done)))
        audits.append(a)

    reviews = []
    for spec in C.REVIEWS:
        rv = ManagementReview(ref=spec["ref"].format(Y=y), title=spec["title"], review_date=_d(spec["j"]),
                              status=ReviewStatus(spec["status"]), participants=spec["participants"],
                              inputs=spec["inputs"] or None, decisions=spec["decisions"] or None)
        db.session.add(rv)
        db.session.flush()
        for desc, owner, due, st in spec["actions"]:
            db.session.add(ReviewAction(review_id=rv.id, description=desc, owner_id=uid(owner),
                                        due_date=_d(due), status=ActionStatus(st)))
        reviews.append(rv)

    documents = []
    for ref, title, typ, ver, st, owner, jappr, jnext, folder, note in C.DOCUMENTS:
        d = Document(ref=ref, title=title, doc_type=DocType(typ), version=ver, status=DocStatus(st),
                     owner_id=uid(owner), approved_at=_d(jappr), next_review_at=_d(jnext), note=note or None,
                     location=f"/docs/b/{folder}" if webdav.enabled() else None)
        db.session.add(d)
        documents.append(d)

    evidences = []
    for i, (title, desc, j, owner, refs) in enumerate(C.EVIDENCE, 1):
        e = Evidence(ref=f"PRV-{i:04d}", title=title, description=desc, collected_at=_d(j), owner_id=uid(owner))
        e.controls = [ctrl[x] for x in refs]
        db.session.add(e)
        evidences.append(e)

    db.session.flush()
    _p1_demo(users, documents, ctrl)
    _p2_demo(users, ctrl)
    _p3_demo(users)
    _links_demo()
    settings_svc.set_many({"org_name": C.ORG_NAME})  # commit
    log(f"Données chargées : {len(C.RISKS)} risques, {len(C.ASSETS)} actifs, {len(C.INCIDENTS)} incidents, "
        f"{len(C.AUDITS)} audits, {len(C.REVIEWS)} revues, {len(C.DOCUMENTS)} documents, {len(C.EVIDENCE)} preuves.")

    _files(users, audits, reviews, incidents, awareness, evidences, log)


# --------------------------------------------------------------------------
# Fichiers : pièces jointes et espace Docs (Nextcloud)
# --------------------------------------------------------------------------
def _meta(title, ref, version, owner, status):
    return [("title", title), ("subtitle", f"{C.ORG_NAME} - {ref} - version {version} - {status}"),
            ("table", [["Propriétaire", "Classification", "Diffusion"], [owner, "Interne", "Ensemble du personnel"]])]


def _pssi():
    return [
        ("h1", "1. Objet"),
        ("p", "La présente politique définit les principes de sécurité de l'information de Fictivia et l'engagement "
              "de la direction à protéger la confidentialité, l'intégrité et la disponibilité des informations qui lui "
              "sont confiées, en particulier les données de paie de ses clients."),
        ("h1", "2. Périmètre"), ("p", C.SCOPE),
        ("h1", "3. Engagements de la direction"),
        ("li", "Fournir les ressources nécessaires à l'établissement, la mise en œuvre et l'amélioration du SMSI."),
        ("li", "Satisfaire aux exigences légales, réglementaires et contractuelles applicables."),
        ("li", "Améliorer en continu le SMSI sur la base des audits, des incidents et des revues de direction."),
        ("h1", "4. Objectifs de sécurité"),
        ("table", [["Objectif", "Indicateur", "Cible"],
                   ["Disponibilité de la plateforme", "Taux de disponibilité mensuel", "≥ 99,9 %"],
                   ["Résistance à l'hameçonnage", "Taux de clic aux campagnes simulées", "< 5 %"],
                   ["Maîtrise des vulnérabilités", "Vulnérabilités critiques corrigées sous 15 j", "100 %"],
                   ["Maîtrise des accès", "Revues des droits réalisées dans les délais", "100 %"]]),
        ("h1", "5. Principes"),
        ("li", "Les informations sont classifiées et protégées selon leur niveau de sensibilité."),
        ("li", "L'accès est accordé selon le besoin d'en connaître et le principe du moindre privilège."),
        ("li", "Tout incident ou faiblesse de sécurité doit être signalé sans délai à securite@."),
        ("li", "Les risques sont appréciés au moins annuellement et à chaque changement significatif."),
        ("h1", "6. Rôles et responsabilités"),
        ("p", "La direction générale approuve la politique. Le RSSI pilote le SMSI. Chaque responsable d'actif "
              "met en œuvre les mesures de sécurité qui le concernent. Chaque collaborateur respecte la charte "
              "informatique et les politiques thématiques."),
        ("h1", "7. Revue"),
        ("p", "La politique est revue au moins une fois par an en revue de direction, ou en cas de changement majeur."),
    ]


def _incident_proc():
    return [
        ("h1", "1. Objet et domaine d'application"),
        ("p", "Décrire la détection, la qualification, le traitement et le retour d'expérience des incidents de "
              "sécurité de l'information (mesures A.5.24 à A.5.28)."),
        ("h1", "2. Étapes"),
        ("table", [["Étape", "Responsable", "Délai"],
                   ["Signalement (securite@, bouton phishing, SOC)", "Tout collaborateur / SOC", "Immédiat"],
                   ["Qualification (gravité, impact, données personnelles)", "RSSI / astreinte", "≤ 1 h"],
                   ["Confinement et éradication", "Infrastructure / Développement", "Selon gravité"],
                   ["Notification (clients, autorité de protection des données)", "DPO", "≤ 72 h"],
                   ["Retour d'expérience et actions d'amélioration", "RSSI", "≤ 15 j après clôture"]]),
        ("h1", "3. Grille de gravité"),
        ("li", "Mineur : impact limité, aucune donnée client concernée."),
        ("li", "Majeur : impact sur un client ou sur des données personnelles."),
        ("li", "Critique : impact sur plusieurs clients, indisponibilité prolongée ou violation de données à grande échelle."),
        ("h1", "4. Enregistrements"),
        ("p", "Chaque incident est enregistré dans le module Incidents du SMSI avec sa chronologie, son impact, "
              "son traitement et les leçons apprises."),
    ]


def _generic(title):
    return [
        ("h1", "1. Objet"), ("p", f"Ce document décrit les règles et dispositions retenues par Fictivia pour : {title.lower()}."),
        ("h1", "2. Domaine d'application"), ("p", C.SCOPE),
        ("h1", "3. Exigences"),
        ("li", "Les exigences sont proportionnées aux risques identifiés dans l'appréciation des risques."),
        ("li", "Leur application est vérifiée lors des contrôles trimestriels et de l'audit interne."),
        ("h1", "4. Responsabilités"), ("p", "Le propriétaire du document en assure la mise à jour et la diffusion."),
        ("h1", "5. Documents associés"), ("li", "DOC-002 - Politique de sécurité de l'information (PSSI)"),
        ("li", "DOC-004 - Méthode d'appréciation et de traitement des risques"),
    ]


def _soa_rows():
    rows = [["Mesure", "Intitulé", "Applicable", "Justification", "Statut", "Mise en œuvre", "Responsable"]]
    for c in Control.of().order_by(Control.id).all():
        rows.append([c.annex_ref, c.title, "Oui" if c.applicable else "Non", c.justification or "",
                     c.status.label, c.implementation or "", c.owner.name if c.owner else ""])
    return rows


def _risk_rows():
    rows = [["Réf.", "Risque", "Actif", "Menace", "Vulnérabilité", "V", "I", "Score inhérent",
             "Traitement", "V rés.", "I rés.", "Score résiduel", "Statut", "Mesures", "Propriétaire"]]
    for r in Risk.query.order_by(Risk.ref).all():
        rows.append([r.ref, r.title, r.asset, r.threat, r.vulnerability, r.likelihood, r.impact, r.inherent_score,
                     r.treatment.label, r.residual_likelihood or "", r.residual_impact or "", r.residual_score or "",
                     r.status.label, ", ".join(c.annex_ref for c in r.controls), r.owner.name if r.owner else ""])
    return rows


def _attach(entity_type, obj, filename, data, user):
    fs = FileStorage(stream=io.BytesIO(data), filename=filename,
                     content_type="application/octet-stream")
    att, msg = att_svc.save_upload(fs, entity_type, obj.id, user)
    return att is not None


def _files(users, audits, reviews, incidents, awareness, evidences, log):
    rssi = users["rssi"]
    owners = {u.id: u.name for u in users.values()}
    n_att = 0

    # Pièces jointes
    a1 = audits[0]
    report = _meta(f"Rapport d'audit interne {a1.ref}", a1.ref, "1.0", owners[a1.lead_auditor_id], "Final") + [
        ("h1", "1. Synthèse"), ("p", a1.summary),
        ("h1", "2. Périmètre et méthode"), ("p", a1.scope),
        ("p", "Méthode : entretiens, observation et échantillonnage, selon ISO 19011 et la procédure DOC-018."),
        ("h1", "3. Constats"),
        ("table", [["Réf.", "Type", "Constat", "Référence"]] +
                  [[f.ref, f.type.short, f.title, f.clause or ""] for f in a1.findings]),
        ("h1", "4. Conclusion"),
        ("p", "Sous réserve du traitement de la non-conformité majeure C-01, le SMSI peut être présenté à l'audit de certification."),
    ]
    n_att += _attach("audit", a1, f"Rapport d'audit {a1.ref}.docx", docgen.docx(report), users["audit"])

    rv = reviews[0]
    pv = _meta(f"Procès-verbal - {rv.title}", rv.ref, "1.0", "Leïla Ben Salah", "Validé") + [
        ("h1", "Participants"), ("p", rv.participants),
        ("h1", "Données d'entrée (clause 9.3.2)"), ("p", rv.inputs),
        ("h1", "Décisions et résultats (clause 9.3.3)"), ("p", rv.decisions),
    ]
    n_att += _attach("review", rv, f"PV {rv.ref}.docx", docgen.docx(pv), rssi)

    inc = incidents[0]
    rex = _meta(f"Retour d'expérience - {inc.ref}", inc.ref, "1.0", "Leïla Ben Salah", "Clôturé") + [
        ("h1", "Chronologie"),
        ("table", [["Heure", "Événement"], ["09:12", "Saisie des identifiants sur une fausse page SSO"],
                   ["09:14", "Acceptation d'une notification MFA frauduleuse"],
                   ["09:31", "Alerte SOC : connexion depuis un pays inhabituel"],
                   ["09:52", "Compte bloqué, sessions révoquées"]]),
        ("h1", "Causes"), ("li", "Fatigue MFA (notifications répétées)."), ("li", "Page d'hameçonnage très réaliste."),
        ("h1", "Actions"), ("li", "MFA avec correspondance de nombres."), ("li", "Campagne de sensibilisation ciblée."),
    ]
    n_att += _attach("incident", inc, f"Retour d'expérience {inc.ref}.docx", docgen.docx(rex), rssi)

    camp = awareness[3]
    depts = [("Commercial", 32, 4, 15), ("Support", 41, 3, 19), ("Développement", 38, 1, 22),
             ("Finance", 14, 2, 5), ("RH", 9, 0, 4), ("Infrastructure", 12, 0, 8), ("Direction", 8, 1, 2),
             ("Produit", 27, 0, 0)]
    rows = [["Service", "Destinataires", "Clics", "Signalements", "Taux de clic"]] + \
           [[d, n, c, s, f"{100 * c / n:.0f} %"] for d, n, c, s in depts]
    n_att += _attach("awareness", camp, "Résultats campagne phishing T3.xlsx", docgen.xlsx([("Résultats", rows)]), rssi)

    ev = evidences[2]
    acc = [["Compte", "Application", "Rôle", "Décision", "Validé par"],
           ["k.trabelsi", "Bastion", "Administrateur", "Maintenu", "Karim Trabelsi"],
           ["y.haddad", "Bastion", "Administrateur", "Maintenu", "Karim Trabelsi"],
           ["ext.prestataire", "Bastion", "Opérateur", "Supprimé (fin de mission)", "Karim Trabelsi"],
           ["s.ancien", "Base de production", "Lecture", "Supprimé (départ)", "Karim Trabelsi"],
           ["m.chaabane", "Base de production", "Lecture", "Réduit (lecture seule recette)", "Karim Trabelsi"]]
    n_att += _attach("evidence", ev, "Revue des accès production.xlsx", docgen.xlsx([("Revue", acc)]), users["dsi"])
    log(f"{n_att} pièces jointes générées.")

    # Espace Docs : un fichier par document du SMSI, rangé par dossier
    if not webdav.enabled():
        log("Docs (Nextcloud) désactivé : fichiers Docs non générés.")
        return
    folders = sorted({d[8] for d in C.DOCUMENTS})
    for f in folders:
        webdav.mkdir("", f)
    n_docs = 0
    for ref, title, typ, ver, st, owner, *_rest in C.DOCUMENTS:
        folder = _rest[2]
        status = DocStatus(st).label
        if ref == "DOC-005":
            name, data = f"{ref} {title}.xlsx", docgen.xlsx([("DdA", _soa_rows())])
        elif ref == "DOC-006":
            name, data = f"{ref} {title}.xlsx", docgen.xlsx([("Plan de traitement", _risk_rows())])
        else:
            body = _pssi() if ref == "DOC-002" else _incident_proc() if ref == "DOC-012" else _generic(title)
            name = f"{ref} {title}.docx"
            data = docgen.docx(_meta(title, ref, ver, users[owner].name, status) + body)
        webdav.upload(folder, name.replace("/", "-"), data)
        n_docs += 1
    webdav.upload("02 Risques", "Registre des risques.xlsx", docgen.xlsx([("Registre", _risk_rows())]))
    log(f"{n_docs + 1} fichiers déposés dans Docs ({webdav.docs_root(current_org())}).")


# --------------------------------------------------------------------------
# Maîtrise documentaire, acceptation des risques et journal d'activité
# --------------------------------------------------------------------------
def _p1_demo(users, documents, ctrl):
    rssi, dg = users["rssi"], users["dg"]
    for d in documents:
        owner = d.owner_id or rssi.id
        if d.status == DocStatus.APPROUVE and d.approved_at:
            appr = datetime.combine(d.approved_at, datetime.min.time()) + timedelta(hours=15)
            if d.ref == "DOC-002":   # PSSI : la 2.0 a été remplacée par la 2.1
                db.session.add(DocumentVersion(document_id=d.id, version="2.0", change_summary="Refonte complète pour ISO/IEC 27001:2022.",
                                               submitted_by_id=owner, submitted_at=appr - timedelta(days=290),
                                               approved_by_id=dg.id, approved_at=appr - timedelta(days=285), retired_at=appr))
            db.session.add(DocumentVersion(document_id=d.id, version=d.version,
                                           change_summary="Intégration des objectifs de sécurité mesurables." if d.ref == "DOC-002" else "Version initiale validée en comité sécurité.",
                                           submitted_by_id=owner, submitted_at=appr - timedelta(days=4),
                                           approved_by_id=dg.id if d.ref in ("DOC-001", "DOC-002") else rssi.id, approved_at=appr))
            d.approved_by_id = dg.id if d.ref in ("DOC-001", "DOC-002") else rssi.id
            d.submitted_by_id, d.submitted_at = owner, appr - timedelta(days=4)
        elif d.status == DocStatus.EN_REVUE:
            d.submitted_by_id, d.submitted_at = owner, _dt(-3)
            d.change_summary = d.note or "Mise à jour suite à l'audit interne."
    # Acceptation formelle : R-0001 acceptée par son propriétaire ; R-0004 reste à accepter
    y = date.today().year
    r1 = Risk.query.filter_by(ref=f"R-{y}-0001").one()
    r1.accepted_by_id, r1.accepted_at, r1.accepted_score = r1.owner_id, _dt(-20), r1.effective_score
    r1.acceptance_note = ("Risque résiduel jugé acceptable : sauvegardes immuables testées mensuellement, EDR et SOC "
                          "en place ; un traitement supplémentaire aurait un coût disproportionné.")
    r1.acceptance_until = _d(345)
    _demo_journal(users)


def _demo_journal(users):
    """Quelques semaines d'activité plausible pour illustrer la piste d'audit."""
    y = date.today().year
    u = {k: v for k, v in users.items()}
    events = [
        (-34, "rssi", "login", None, None, "Connexion réussie (mot de passe + code TOTP)", None),
        (-34, "rssi", "workflow", "Document", "DOC-006", "Version 1.3 approuvée", None),
        (-33, "dsi", "update", "Control", "5.18", None, {"status": ["Non démarré", "En cours"], "implementation": [None, "Revue trimestrielle des droits mise en place après la NC majeure de l'audit interne."]}),
        (-21, "infra", "login", None, None, "Connexion réussie (mot de passe + code TOTP)", None),
        (-20, "infra", "accept", "Risk", f"R-{y}-0001", "Risque résiduel accepté au score 10", None),
        (-18, "audit", "update", "Finding", "C-01", None, {"closed": ["Non", "Non"]}),
        (-14, "infra", "update", "Risk", f"R-{y}-0004", None, {"residual_impact": ["3", "5"]}),
        (-12, "infra", "create", "Incident", f"INC-{y}-0005", None, {"title": [None, "Dégradation des performances suite à un incident du fournisseur IaaS"]}),
        (-9, "dg", "login_failed", None, None, "Mot de passe incorrect", None),
        (-9, "dg", "login", None, None, "Connexion réussie (mot de passe + code TOTP)", None),
        (-7, "rssi", "update", "Control", "8.16", None, {"implementation": ["SOC externalisé en cours de sélection.", "SOC externalisé en phase de déploiement ; règles de détection couvrant 70 % des cas d'usage."]}),
        (-5, "rssi", "export", None, None, "Export Déclaration d'applicabilité (PDF)", None),
        (-3, "infra", "workflow", "Document", "DOC-014", "Version 1.1 soumise pour approbation", None),
        (-2, "infra", "create", "Incident", f"INC-{y}-0006", None, {"severity": [None, "Critique"]}),
        (-1, "audit", "export", None, None, "Export Plan de traitement des risques (XLSX)", None),
    ]
    refs = {"Document": Document, "Control": Control, "Risk": Risk, "Incident": Incident, "Finding": Finding}
    for j, who, action, etype, ref, summary, changes in events:
        obj = refs[etype].query.filter_by(ref=ref).first() if etype else None
        db.session.add(ActivityLog(created_at=_dt(j) + timedelta(minutes=37 * (abs(j) % 7)), user_id=u[who].id,
                                   user_name=u[who].name, action=action, entity_type=etype,
                                   entity_id=obj.id if obj else None,
                                   entity_ref=audit_trail.label_of(obj) if obj else None,
                                   summary=summary, changes=changes, ip="10.20.0." + str(10 + abs(j))))


# --------------------------------------------------------------------------
# P2 : contexte, objectifs et indicateurs, non-conformités, fournisseurs, exigences
# --------------------------------------------------------------------------
def _month_end(months_ago):
    """Dernier jour du mois, il y a `months_ago` mois (1 = mois dernier)."""
    t = date.today().replace(day=1)
    for _ in range(months_ago - 1):
        t = (t - timedelta(days=1)).replace(day=1)
    return t - timedelta(days=1)


def _series(values, frequency):
    step = {"MENSUELLE": 1, "TRIMESTRIELLE": 3, "SEMESTRIELLE": 6, "ANNUELLE": 12}[frequency]
    n = len(values)
    return [(_month_end(1 + step * (n - 1 - k)), v) for k, v in enumerate(values)]


def _indicator(spec, users, ctrl, objective, n):
    name, unit, direction, target, alert, freq, method, owner, analyst, cref, values = spec
    ind = Indicator(ref=f"KPI-{n:03d}", name=name, unit=unit, direction=Direction(direction), target=target, alert=alert,
                    frequency=Frequency(freq), method=method, owner_id=users[owner].id, analyst=analyst,
                    control_id=ctrl[cref].id, objective_id=objective.id if objective else None,
                    created_at=datetime.utcnow() - timedelta(days=400))
    db.session.add(ind)
    db.session.flush()
    for period, value in _series(values, freq):
        state = ind.evaluate(value)
        comment = {"hors_cible": "Écart analysé en comité sécurité.", "alerte": "Sous surveillance."}.get(state)
        db.session.add(Measurement(indicator_id=ind.id, period=period, value=value, comment=comment,
                                   recorded_by_id=users[owner].id))
    return ind


def _p2_demo(users, ctrl):
    y = date.today().year
    settings_svc.set_many({**C.SCOPE_TEXT, "scope_updated": _d(-120).isoformat()})
    risks = {int(r.ref[-4:]): r for r in Risk.query.all()}
    for n, (kind, cat, title, desc, effect, resp, rnums) in enumerate(C.ISSUES, 1):
        i = ContextIssue(ref=f"ENJ-{n:03d}", kind=IssueKind(kind), category=IssueCategory(cat), title=title,
                         description=desc, effect=effect, response=resp)
        i.risks = [risks[k] for k in rnums if k in risks]
        db.session.add(i)
    parties = []
    for n, (name, cat, exp, retained, resp, infl) in enumerate(C.PARTIES, 1):
        p = InterestedParty(ref=f"PI-{n:03d}", name=name, category=PartyCategory(cat), expectations=exp,
                            retained=retained, response=resp or None, influence=infl)
        db.session.add(p)
        parties.append(p)
    db.session.flush()
    for n, (title, typ, src, issuer, obl, resp, st, pnum, crefs, jrev) in enumerate(C.REQUIREMENTS, 1):
        r = Requirement(ref=f"EXG-{n:03d}", title=title, req_type=RequirementType(typ), source=src, issuer=issuer,
                        obligation=obl, response=resp, status=ComplianceStatus(st),
                        party_id=parties[pnum - 1].id if pnum else None, owner_id=users["dpo"].id,
                        last_review=_d(jrev - 365), next_review=_d(jrev))
        r.controls = [ctrl[c] for c in crefs]
        db.session.add(r)
    owners = {"CLOUD": "infra", "LOGICIEL": "dsi", "SECURITE": "rssi", "INFOGERANCE": "dsi", "CONSEIL": "rssi",
              "TELECOM": "infra", "AUTRE": "infra"}
    for n, (name, cat, svc, crit, data, st, clauses, dpa, certs, res, jlast, jnext) in enumerate(C.SUPPLIERS, 1):
        db.session.add(Supplier(ref=f"FRN-{n:03d}", name=name, category=SupplierCategory(cat), service=svc,
                                criticality=Criticality(crit), data_access=DataAccess(data), status=SupplierStatus(st),
                                security_clauses=clauses, dpa=dpa, certifications=certs or None,
                                assessment_result=AssessmentResult(res), last_assessment=_d(jlast),
                                next_assessment=_d(jnext), owner_id=users[owners[cat]].id,
                                contract_ref=f"CT-{y - 1}-{n:03d}", contract_end=_d(200 + 30 * n)))
    k = 0
    for n, (title, desc, actions, res, owner, jdue, ev, st, inds) in enumerate(C.OBJECTIVES, 1):
        o = Objective(ref=f"OBJ-{y}-{n:02d}", title=title, description=desc, actions=actions, resources=res,
                      owner_id=users[owner].id, due_date=_d(jdue), evaluation=ev, status=ObjectiveStatus(st))
        db.session.add(o)
        db.session.flush()
        for spec in inds:
            k += 1
            _indicator(spec, users, ctrl, o, k)
    for spec in C.SURVEILLANCE:
        k += 1
        _indicator(spec, users, ctrl, None, k)
    for n, (title, src, sev, st, j, who, link, desc, corr, method, cause, extent, changes, actions, eff) \
            in enumerate(C.NONCONFORMITIES, 1):
        nc = NonConformity(ref=f"NC-{y}-{n:03d}", title=title, source=NcSource(src), severity=NcSeverity(sev),
                           status=NcStatus(st), detected_at=_d(j), detected_by=who.format(Y=y), description=desc,
                           correction=corr or None, cause_method=method, root_cause=cause or None, extent=extent or None,
                           isms_changes=changes or None, owner_id=users["rssi"].id, effectiveness_due=_d(j + 75),
                           created_at=_dt(j))
        if link and link[0] == "finding":
            f = Finding.query.join(Audit).filter(Audit.ref == link[1].format(Y=y), Finding.ref == link[2]).one()
            nc.finding_id, nc.control_id, nc.clause = f.id, f.control_id, f.clause
        elif link and link[0] == "incident":
            inc = Incident.query.filter_by(ref=link[1].format(Y=y)).one()
            nc.incident_id, nc.control_id = inc.id, inc.control_id
        if eff:
            nc.effectiveness_note, nc.effectiveness_by_id = eff[0], users[eff[1]].id
            nc.effectiveness_at = nc.closed_at = _dt(eff[2])
        db.session.add(nc)
        db.session.flush()
        for desc_a, owner, due, ast in actions:
            db.session.add(CorrectiveAction(nonconformity_id=nc.id, description=desc_a, owner_id=users[owner].id,
                                            due_date=_d(due), status=ActionStatus(ast),
                                            completed_at=_dt(due) if ast in ("REALISEE", "VERIFIEE") else None))


# --------------------------------------------------------------------------
# P3 : programme d'audit, compétences, continuité, changements, actifs <-> risques
# --------------------------------------------------------------------------
def _links_demo():
    """Maillage SMI : risques liés aux incidents, fournisseurs, activités de la BIA, changements."""
    from app.models import RiskLink, Incident, Supplier, BusinessProcess, ChangeRequest
    from app.services import risk_links
    y = date.today().year
    refs = {"Incident": lambda n: (Incident, f"INC-{y}-{n:04d}"), "Supplier": lambda n: (Supplier, f"FRN-{n:03d}"),
            "BusinessProcess": lambda n: (BusinessProcess, f"PROC-{n:03d}"),
            "ChangeRequest": lambda n: (ChangeRequest, f"CHG-{y}-{n:03d}")}
    db.session.flush()
    risks = {int(r.ref[-4:]): r for r in Risk.query.all()}

    def obj(etype, n):
        model, ref = refs[etype](n)
        return model.query.filter_by(ref=ref).first()
    for n, items in C.RISK_LINKS.items():
        for etype, k in items:
            o = obj(etype, k)
            if o is not None and n in risks:
                risks[n].links.append(RiskLink(entity_type=etype, entity_id=o.id))
    n, (etype, k) = C.RISK_REASSESS
    o = obj(etype, k)
    if o is not None and n in risks:
        risk_links.add(risks[n], etype, o.id)
    db.session.flush()


def _p3_demo(users):
    y = date.today().year
    assets = {int(a.ref[-4:]): a for a in Asset.query.all()}
    for r in Risk.query.all():
        r.assets = [assets[n] for n in C.RISK_ASSETS.get(int(r.ref[-4:]), []) if n in assets]
    for dy, dom, q, who, aud, note in C.AUDIT_PROGRAMME:
        a = Audit.query.filter_by(ref=aud.format(Y=y)).first() if aud else None
        db.session.add(AuditPlanItem(year=y + dy, domain=dom, quarter=q, auditor_id=users[who].id,
                                     audit_id=a.id if a else None, note=note or None))
    reqs = []
    for title, desc, months, people in C.COMPETENCES:
        r = CompetenceRequirement(title=title, description=desc, validity_months=months)
        r.users = [users[k] for k in people]
        db.session.add(r)
        reqs.append(r)
    db.session.flush()
    for who, n, title, typ, prov, jo, je in C.COMPETENCE_RECORDS:
        req = reqs[n - 1] if n else None
        exp = _d(je) if je is not None else (
            _d(jo) + timedelta(days=round(req.validity_months * 30.44)) if req and req.validity_months else None)
        db.session.add(CompetenceRecord(user_id=users[who].id, requirement_id=req.id if req else None, title=title,
                                        ctype=CompetenceType(typ), provider=prov, obtained_at=_d(jo), expires_at=exp))
    docs = {d.ref: d for d in Document.query.all()}
    procs = []
    for n, (name, desc, owner, crit, impacts, mtpd, rto, rpo, deps, strat, anums, plan) in enumerate(C.PROCESSES, 1):
        p = BusinessProcess(ref=f"PROC-{n:03d}", name=name, description=desc, owner_id=users[owner].id, criticality=crit,
                            impacts=impacts, mtpd_hours=mtpd, rto_hours=rto, rpo_hours=rpo, dependencies=deps,
                            strategy=strat, plan_id=docs[plan].id if plan in docs else None)
        p.assets = [assets[k] for k in anums if k in assets]
        db.session.add(p)
        procs.append(p)
    db.session.flush()
    tests = sorted(C.CONTINUITY_TESTS, key=lambda t: t[2])
    per_year = {}
    for title, typ, j, obj, res, rto, findings, pnums, owner in tests:
        ty = _d(j).year                      # numérotation par année de l'exercice
        per_year[ty] = per_year.get(ty, 0) + 1
        t = ContinuityTest(ref=f"EXE-{ty}-{per_year[ty]:02d}", title=title, ttype=TestType(typ), test_date=_d(j), objectives=obj,
                           result=TestResult(res), achieved_rto_hours=rto, findings=findings or None,
                           owner_id=users[owner].id)
        t.processes = [procs[k - 1] for k in pnums]
        db.session.add(t)
    for n, (title, kind, risk, urgent, req, st, appr, j, desc, why, impact, rb, dec, rev, anums) in enumerate(C.CHANGES, 1):
        c = ChangeRequest(ref=f"CHG-{y}-{n:03d}", title=title, kind=ChangeKind(kind), risk_level=ChangeRisk(risk),
                          emergency=urgent, requested_by_id=users[req].id, status=ChangeStatus(st), planned_date=_d(j),
                          description=desc, reason=why, security_impact=impact, rollback=rb or None,
                          created_at=_dt(j - 12))
        if appr:
            c.approved_by_id, c.approved_at, c.decision_note = users[appr].id, _dt(j - 5), dec or None
        if st in ("REALISE", "CLOTURE"):
            c.done_at = _dt(j)
        if st == "CLOTURE":
            c.review_note, c.reviewed_at = rev, _dt(j + 7)
        c.assets = [assets[k] for k in anums if k in assets]
        db.session.add(c)
