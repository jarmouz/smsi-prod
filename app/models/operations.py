"""Modèles P3 : programme d'audit (9.2.2), compétences (7.2), continuité
d'activité (A.5.29, A.5.30), gestion des changements (6.3, A.8.32) et lien
actifs <-> risques."""
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import (CompetenceType, TestType, TestResult, ChangeKind, ChangeRisk, ChangeStatus)


def _enum(e, default=None, **kw):
    return db.Column(db.Enum(e, native_enum=False, length=24), default=default, **kw)


asset_risks = db.Table(
    "asset_risks",
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    db.Column("risk_id", db.Integer, db.ForeignKey("risks.id", ondelete="CASCADE"), primary_key=True),
)
process_assets = db.Table(
    "process_assets",
    db.Column("process_id", db.Integer, db.ForeignKey("business_processes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)
test_processes = db.Table(
    "test_processes",
    db.Column("test_id", db.Integer, db.ForeignKey("continuity_tests.id", ondelete="CASCADE"), primary_key=True),
    db.Column("process_id", db.Integer, db.ForeignKey("business_processes.id", ondelete="CASCADE"), primary_key=True),
)
change_assets = db.Table(
    "change_assets",
    db.Column("change_id", db.Integer, db.ForeignKey("change_requests.id", ondelete="CASCADE"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)
competence_users = db.Table(
    "competence_users",
    db.Column("requirement_id", db.Integer, db.ForeignKey("competence_requirements.id", ondelete="CASCADE"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

# Domaines couverts par le programme d'audit : clauses 4 à 10 et thèmes de l'Annexe A
AUDIT_DOMAINS = [
    ("C4", "4 - Contexte de l'organisme"), ("C5", "5 - Leadership"), ("C6", "6 - Planification"),
    ("C7", "7 - Support"), ("C8", "8 - Fonctionnement"), ("C9", "9 - Évaluation des performances"),
    ("C10", "10 - Amélioration"), ("A5", "A.5 - Mesures organisationnelles"), ("A6", "A.6 - Mesures liées aux personnes"),
    ("A7", "A.7 - Mesures physiques"), ("A8", "A.8 - Mesures technologiques"),
]


# --- 9.2.2 -----------------------------------------------------------------------
class AuditPlanItem(TenantMixin, db.Model):
    """Case du programme d'audit : un domaine planifié une année donnée."""

    __tablename__ = "audit_plan_items"
    __table_args__ = (db.UniqueConstraint("organization_id", "year", "domain", name="uq_audit_plan_org_year_domain"),)

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    domain = db.Column(db.String(8), nullable=False)
    quarter = db.Column(db.Integer, nullable=True)                 # 1..4
    audit_id = db.Column(db.Integer, db.ForeignKey("audits.id", ondelete="SET NULL"), nullable=True)
    auditor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    note = db.Column(db.String(300), nullable=True)

    audit = db.relationship("Audit")
    auditor = db.relationship("User")

    @property
    def ref(self):
        return f"{self.year} {self.domain}"


# --- 7.2 ---------------------------------------------------------------------------
class CompetenceRequirement(TenantMixin, db.Model):
    """Compétence requise pour des personnes dont le travail a une incidence sur la sécurité."""

    __tablename__ = "competence_requirements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    validity_months = db.Column(db.Integer, nullable=True)        # renouvellement (ex. formation annuelle)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship("User", secondary=competence_users, order_by="User.name")
    records = db.relationship("CompetenceRecord", back_populates="requirement")

    def valid_record(self, user_id):
        today = date.today()
        best = None
        for r in self.records:
            if r.user_id == user_id and (r.expires_at is None or r.expires_at >= today):
                if best is None or (r.obtained_at or date.min) > (best.obtained_at or date.min):
                    best = r
        return best

    @property
    def gaps(self):
        return [u for u in self.users if u.is_active_flag and self.valid_record(u.id) is None]


class CompetenceRecord(TenantMixin, db.Model):
    """Preuve de compétence d'une personne (formation, certification, expérience...)."""

    __tablename__ = "competence_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = db.Column(db.Integer, db.ForeignKey("competence_requirements.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    ctype = _enum(CompetenceType, CompetenceType.FORMATION, nullable=False)
    provider = db.Column(db.String(255), nullable=True)
    obtained_at = db.Column(db.Date, nullable=True)
    expires_at = db.Column(db.Date, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
    requirement = db.relationship("CompetenceRequirement", back_populates="records")

    @property
    def ref(self):
        return f"{self.user.name if self.user else ''} - {self.title}"

    @property
    def expired(self):
        return bool(self.expires_at and self.expires_at < date.today())

    @property
    def expires_soon(self):
        return bool(self.expires_at and 0 <= (self.expires_at - date.today()).days <= 60)


# --- A.5.29 / A.5.30 -----------------------------------------------------------------
class BusinessProcess(TenantMixin, db.Model):
    """Activité / processus et son analyse d'impact (BIA)."""

    __tablename__ = "business_processes"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_business_processes_org_ref"),)

    TEST_MONTHS = 12

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # PROC-001
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    criticality = db.Column(db.Integer, default=2, nullable=False)     # 1 faible .. 4 vitale
    impacts = db.Column(db.Text, nullable=True)                        # conséquences d'une interruption dans le temps
    mtpd_hours = db.Column(db.Float, nullable=True)                    # durée maximale d'interruption admissible
    rto_hours = db.Column(db.Float, nullable=True)
    rpo_hours = db.Column(db.Float, nullable=True)
    dependencies = db.Column(db.Text, nullable=True)                   # personnes, fournisseurs, sites...
    strategy = db.Column(db.Text, nullable=True)                       # stratégie de continuité / mode dégradé
    plan_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    plan = db.relationship("Document")
    assets = db.relationship("Asset", secondary=process_assets, back_populates="processes")
    tests = db.relationship("ContinuityTest", secondary=test_processes, back_populates="processes",
                            order_by="ContinuityTest.test_date.desc()")

    CRITICALITY = {1: "Faible", 2: "Importante", 3: "Critique", 4: "Vitale"}

    @property
    def criticality_label(self):
        return self.CRITICALITY.get(self.criticality, "-")

    @property
    def last_test(self):
        done = [t for t in self.tests if t.result != TestResult.PLANIFIE and t.test_date]
        return done[0] if done else None

    @property
    def test_overdue(self):
        """Processus critique ou vital non testé depuis plus de 12 mois."""
        if self.criticality < 3:
            return False
        lt = self.last_test
        return lt is None or (date.today() - lt.test_date).days > self.TEST_MONTHS * 31

    @property
    def rto_ok(self):
        """RTO compatible avec la durée maximale admissible et démontré par le dernier test."""
        lt = self.last_test
        if lt is None or lt.achieved_rto_hours is None or self.rto_hours is None:
            return None
        return lt.achieved_rto_hours <= self.rto_hours


class ContinuityTest(TenantMixin, db.Model):
    """Exercice ou test de continuité / reprise (A.5.30 : préparation des TIC)."""

    __tablename__ = "continuity_tests"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_continuity_tests_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # EXE-2026-01
    title = db.Column(db.String(300), nullable=False)
    ttype = _enum(TestType, TestType.TABLE_TOP, nullable=False)
    test_date = db.Column(db.Date, nullable=True)
    objectives = db.Column(db.Text, nullable=True)
    result = _enum(TestResult, TestResult.PLANIFIE, nullable=False)
    achieved_rto_hours = db.Column(db.Float, nullable=True)
    findings = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    owner = db.relationship("User")
    processes = db.relationship("BusinessProcess", secondary=test_processes, back_populates="tests")


# --- 6.3 / A.8.32 --------------------------------------------------------------------
class ChangeRequest(TenantMixin, db.Model):
    """Demande de changement : analyse d'impact sécurité, approbation, retour
    arrière, réalisation et revue post-changement."""

    __tablename__ = "change_requests"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_change_requests_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # CHG-2026-001
    title = db.Column(db.String(300), nullable=False)
    kind = _enum(ChangeKind, ChangeKind.TECHNIQUE, nullable=False)
    description = db.Column(db.Text, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    security_impact = db.Column(db.Text, nullable=True)      # analyse d'impact sur la sécurité
    risk_level = _enum(ChangeRisk, ChangeRisk.FAIBLE, nullable=False)
    rollback = db.Column(db.Text, nullable=True)             # plan de retour arrière
    emergency = db.Column(db.Boolean, default=False, nullable=False)
    status = _enum(ChangeStatus, ChangeStatus.DEMANDE, nullable=False, index=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    decision_note = db.Column(db.Text, nullable=True)
    planned_date = db.Column(db.Date, nullable=True)
    done_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)          # revue post-changement
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    assets = db.relationship("Asset", secondary=change_assets)
