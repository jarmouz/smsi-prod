"""Phase 2 : plans de continuité (ISO 22301) et management des services informatiques
(ISO/IEC 20000-1) : catalogue de services et niveaux de service, problèmes, mises en production."""
import enum
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.organization import TenantMixin


def _enum(e, default=None, **kw):
    return db.Column(db.Enum(e, native_enum=False, length=24), default=default, **kw)


class _Labelled(str, enum.Enum):
    @property
    def label(self):
        return self._labels()[self.value]


# ============================================================================
# ISO 22301 - Plans de continuité
# ============================================================================
class PlanType(_Labelled):
    PCA = "PCA"
    PRA = "PRA"
    CRISE = "CRISE"
    COMMUNICATION = "COMMUNICATION"

    @staticmethod
    def _labels():
        return {"PCA": "Plan de continuité d'activité", "PRA": "Plan de reprise informatique",
                "CRISE": "Gestion de crise", "COMMUNICATION": "Communication de crise"}


class PlanStatus(_Labelled):
    BROUILLON = "BROUILLON"
    VALIDE = "VALIDE"
    OBSOLETE = "OBSOLETE"

    @staticmethod
    def _labels():
        return {"BROUILLON": "En rédaction", "VALIDE": "Validé", "OBSOLETE": "Obsolète"}


plan_processes = db.Table(
    "plan_processes",
    db.Column("plan_id", db.Integer, db.ForeignKey("continuity_plans.id", ondelete="CASCADE"), primary_key=True),
    db.Column("process_id", db.Integer, db.ForeignKey("business_processes.id", ondelete="CASCADE"), primary_key=True),
)
plan_tests = db.Table(
    "plan_tests",
    db.Column("plan_id", db.Integer, db.ForeignKey("continuity_plans.id", ondelete="CASCADE"), primary_key=True),
    db.Column("test_id", db.Integer, db.ForeignKey("continuity_tests.id", ondelete="CASCADE"), primary_key=True),
)


class ContinuityPlan(TenantMixin, db.Model):
    """Plan de continuité, de reprise ou de gestion de crise (22301 8.4)."""

    __tablename__ = "continuity_plans"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_continuity_plans_org_ref"),)

    REVIEW_MONTHS = 12

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # PLAN-001
    title = db.Column(db.String(300), nullable=False)
    plan_type = _enum(PlanType, PlanType.PCA, nullable=False)
    scope = db.Column(db.Text, nullable=True)                                  # sites, activités, scénarios couverts
    activation = db.Column(db.Text, nullable=True)                             # critères et autorité de déclenchement (8.4.2)
    response_team = db.Column(db.Text, nullable=True)                          # cellule de crise, suppléants
    alerting = db.Column(db.Text, nullable=True)                               # alerte et communication (8.4.3)
    procedures = db.Column(db.Text, nullable=True)                             # étapes de continuité / reprise (8.4.4, 8.4.5)
    resources = db.Column(db.Text, nullable=True)                              # ressources nécessaires (8.3.4)
    version = db.Column(db.String(16), nullable=True)
    status = _enum(PlanStatus, PlanStatus.BROUILLON, nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_review = db.Column(db.Date, nullable=True)
    next_review = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    document = db.relationship("Document")
    processes = db.relationship("BusinessProcess", secondary=plan_processes)
    tests = db.relationship("ContinuityTest", secondary=plan_tests)

    @property
    def last_exercise(self):
        dated = [t for t in self.tests if t.test_date]
        return max(dated, key=lambda t: t.test_date) if dated else None

    @property
    def gaps(self):
        if self.status == PlanStatus.OBSOLETE:
            return []
        out = []
        if not (self.activation or "").strip():
            out.append("critères de déclenchement non définis")
        if not (self.response_team or "").strip():
            out.append("structure de réponse non définie")
        if not (self.procedures or "").strip():
            out.append("procédures non décrites")
        if not self.processes:
            out.append("aucune activité couverte")
        last = self.last_exercise
        if last is None:
            out.append("jamais exercé")
        elif last.test_date < date.today() - timedelta(days=365):
            out.append("dernier exercice il y a plus d'un an")
        if self.next_review and self.next_review < date.today():
            out.append("revue à faire")
        return out

    def default_next(self, d):
        return d + timedelta(days=365 * self.REVIEW_MONTHS // 12)


# ============================================================================
# ISO/IEC 20000-1 - Catalogue de services et niveaux de service
# ============================================================================
class ServiceStatus(_Labelled):
    EN_PROJET = "EN_PROJET"
    ACTIF = "ACTIF"
    RETIRE = "RETIRE"

    @staticmethod
    def _labels():
        return {"EN_PROJET": "En conception", "ACTIF": "En service", "RETIRE": "Retiré"}


service_assets = db.Table(
    "service_assets",
    db.Column("service_id", db.Integer, db.ForeignKey("it_services.id", ondelete="CASCADE"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)
service_suppliers = db.Table(
    "service_suppliers",
    db.Column("service_id", db.Integer, db.ForeignKey("it_services.id", ondelete="CASCADE"), primary_key=True),
    db.Column("supplier_id", db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True),
)


class ItService(TenantMixin, db.Model):
    """Service du catalogue (20000-1 8.2.4) et son accord de niveau de service (8.3.3)."""

    __tablename__ = "it_services"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_it_services_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # SRV-001
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    customers = db.Column(db.Text, nullable=True)                              # clients / utilisateurs
    status = _enum(ServiceStatus, ServiceStatus.ACTIF, nullable=False, index=True)
    criticality = db.Column(db.Integer, default=2, nullable=False)             # 1 faible .. 4 vitale
    support_hours = db.Column(db.String(200), nullable=True)                   # plage de service
    availability_target = db.Column(db.Float, nullable=True)                   # % (ex. 99.5)
    response_time = db.Column(db.String(200), nullable=True)                   # délais de prise en charge
    resolution_time = db.Column(db.String(200), nullable=True)                 # délais de résolution
    sla_reference = db.Column(db.String(200), nullable=True)                   # accord / contrat
    sla_review = db.Column(db.Date, nullable=True)                             # prochaine revue de l'accord
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    assets = db.relationship("Asset", secondary=service_assets)
    suppliers = db.relationship("Supplier", secondary=service_suppliers)
    measures = db.relationship("ServiceMeasure", back_populates="service", cascade="all, delete-orphan",
                               order_by="ServiceMeasure.period.desc()")

    @property
    def last_measure(self):
        return self.measures[0] if self.measures else None

    @property
    def gaps(self):
        if self.status != ServiceStatus.ACTIF:
            return []
        out = []
        if self.availability_target is None and not (self.response_time or self.resolution_time):
            out.append("aucun niveau de service défini")
        if not self.owner_id:
            out.append("sans responsable")
        m = self.last_measure
        if m is None:
            out.append("aucune mesure de performance")
        elif m.breached:
            out.append(f"objectif non atteint en {m.period}")
        if self.sla_review and self.sla_review < date.today():
            out.append("revue de l'accord à faire")
        return out


class ServiceMeasure(TenantMixin, db.Model):
    """Mesure périodique d'un service (rapport de service, 20000-1 9.4)."""

    __tablename__ = "service_measures"
    __table_args__ = (db.UniqueConstraint("service_id", "period", name="uq_service_measures_period"),)

    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("it_services.id", ondelete="CASCADE"), nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False)                           # AAAA-MM
    availability = db.Column(db.Float, nullable=True)                          # % mesuré
    incidents = db.Column(db.Integer, nullable=True)
    sla_breaches = db.Column(db.Integer, nullable=True)                        # dépassements de délais
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    service = db.relationship("ItService", back_populates="measures")

    @property
    def breached(self):
        t = self.service.availability_target if self.service else None
        return bool((t is not None and self.availability is not None and self.availability < t)
                    or (self.sla_breaches or 0) > 0)


# ============================================================================
# ISO/IEC 20000-1 - Problèmes (8.6.3) et mises en production (8.5.3)
# ============================================================================
class ProblemStatus(_Labelled):
    OUVERT = "OUVERT"
    ANALYSE = "ANALYSE"
    ERREUR_CONNUE = "ERREUR_CONNUE"
    RESOLU = "RESOLU"
    CLOS = "CLOS"

    @staticmethod
    def _labels():
        return {"OUVERT": "Ouvert", "ANALYSE": "En analyse", "ERREUR_CONNUE": "Erreur connue (contournement)",
                "RESOLU": "Résolu", "CLOS": "Clos"}

    @property
    def closed(self):
        return self.value in ("RESOLU", "CLOS")


class Priority(_Labelled):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @staticmethod
    def _labels():
        return {"P1": "P1 - critique", "P2": "P2 - haute", "P3": "P3 - moyenne", "P4": "P4 - basse"}


problem_incidents = db.Table(
    "problem_incidents",
    db.Column("problem_id", db.Integer, db.ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True),
    db.Column("incident_id", db.Integer, db.ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True),
)


class Problem(TenantMixin, db.Model):
    __tablename__ = "problems"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_problems_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # PRB-2026-0001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey("it_services.id", ondelete="SET NULL"), nullable=True)
    priority = _enum(Priority, Priority.P3, nullable=False)
    status = _enum(ProblemStatus, ProblemStatus.OUVERT, nullable=False, index=True)
    root_cause = db.Column(db.Text, nullable=True)
    workaround = db.Column(db.Text, nullable=True)
    resolution = db.Column(db.Text, nullable=True)
    change_id = db.Column(db.Integer, db.ForeignKey("change_requests.id", ondelete="SET NULL"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    opened_on = db.Column(db.Date, nullable=False, default=date.today)
    resolved_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service = db.relationship("ItService")
    change = db.relationship("ChangeRequest")
    owner = db.relationship("User")
    incidents = db.relationship("Incident", secondary=problem_incidents)


class ReleaseStatus(_Labelled):
    PLANIFIEE = "PLANIFIEE"
    TESTEE = "TESTEE"
    DEPLOYEE = "DEPLOYEE"
    RETOUR_ARRIERE = "RETOUR_ARRIERE"
    ANNULEE = "ANNULEE"

    @staticmethod
    def _labels():
        return {"PLANIFIEE": "Planifiée", "TESTEE": "Testée, prête", "DEPLOYEE": "Déployée",
                "RETOUR_ARRIERE": "Retour arrière effectué", "ANNULEE": "Annulée"}


release_changes = db.Table(
    "release_changes",
    db.Column("release_id", db.Integer, db.ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True),
    db.Column("change_id", db.Integer, db.ForeignKey("change_requests.id", ondelete="CASCADE"), primary_key=True),
)


class Release(TenantMixin, db.Model):
    __tablename__ = "releases"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_releases_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # MEP-2026-0001
    title = db.Column(db.String(300), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("it_services.id", ondelete="SET NULL"), nullable=True)
    status = _enum(ReleaseStatus, ReleaseStatus.PLANIFIEE, nullable=False, index=True)
    planned_on = db.Column(db.Date, nullable=True)
    deployed_on = db.Column(db.Date, nullable=True)
    content = db.Column(db.Text, nullable=True)                                # contenu de la version
    tests = db.Column(db.Text, nullable=True)                                  # tests et critères d'acceptation
    rollback_plan = db.Column(db.Text, nullable=True)
    result = db.Column(db.Text, nullable=True)                                 # résultat, incidents liés au déploiement
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    service = db.relationship("ItService")
    owner = db.relationship("User")
    changes = db.relationship("ChangeRequest", secondary=release_changes)

    @property
    def gaps(self):
        if self.status in (ReleaseStatus.ANNULEE,):
            return []
        out = []
        if not (self.rollback_plan or "").strip() and self.status in (ReleaseStatus.PLANIFIEE, ReleaseStatus.TESTEE):
            out.append("plan de retour arrière manquant")
        if not (self.tests or "").strip() and self.status != ReleaseStatus.PLANIFIEE:
            out.append("tests non documentés")
        if not self.changes:
            out.append("aucun changement approuvé rattaché")
        return out
