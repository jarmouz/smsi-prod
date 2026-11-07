"""Modèles P2 : contexte de l'organisme (4.1, 4.2), objectifs et indicateurs
(6.2, 9.1), non-conformités (10.2), fournisseurs (A.5.19-5.22) et exigences
légales, réglementaires et contractuelles (A.5.31)."""
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import (
    IssueKind, IssueCategory, PartyCategory, ObjectiveStatus, Frequency, Direction, NcSource, NcSeverity,
    NcStatus, SupplierCategory, Criticality, DataAccess, AssessmentResult, SupplierStatus, RequirementType,
    ComplianceStatus,
)


def _enum(e, default=None, **kw):
    return db.Column(db.Enum(e, native_enum=False, length=24), default=default, **kw)


issue_risks = db.Table(
    "issue_risks",
    db.Column("issue_id", db.Integer, db.ForeignKey("context_issues.id", ondelete="CASCADE"), primary_key=True),
    db.Column("risk_id", db.Integer, db.ForeignKey("risks.id", ondelete="CASCADE"), primary_key=True),
)

requirement_controls = db.Table(
    "requirement_controls",
    db.Column("requirement_id", db.Integer, db.ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True),
    db.Column("control_id", db.Integer, db.ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
)


# --- 4.1 / 4.2 -----------------------------------------------------------------
class ContextIssue(TenantMixin, db.Model):
    """Enjeu interne ou externe pertinent pour le SMSI (4.1)."""

    __tablename__ = "context_issues"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_context_issues_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # ENJ-001
    kind = _enum(IssueKind, IssueKind.EXTERNE, nullable=False)
    category = _enum(IssueCategory, IssueCategory.ORGANISATIONNEL, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    effect = db.Column(db.Text, nullable=True)        # effet sur la capacité du SMSI à atteindre ses résultats
    response = db.Column(db.Text, nullable=True)      # prise en compte (risques, objectifs, mesures)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    risks = db.relationship("Risk", secondary=issue_risks)


class InterestedParty(TenantMixin, db.Model):
    """Partie intéressée et ses exigences (4.2)."""

    __tablename__ = "interested_parties"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_interested_parties_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # PI-001
    name = db.Column(db.String(300), nullable=False)
    category = _enum(PartyCategory, PartyCategory.CLIENT, nullable=False)
    expectations = db.Column(db.Text, nullable=True)   # besoins et attentes
    retained = db.Column(db.Boolean, default=True, nullable=False)   # exigences traitées par le SMSI (4.2 c)
    response = db.Column(db.Text, nullable=True)       # comment le SMSI y répond
    influence = db.Column(db.Integer, default=2, nullable=False)     # 1 faible .. 3 forte
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requirements = db.relationship("Requirement", back_populates="party")


# --- 6.2 / 9.1 -------------------------------------------------------------------
class Objective(TenantMixin, db.Model):
    """Objectif de sécurité de l'information mesurable (6.2)."""

    __tablename__ = "objectives"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_objectives_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # OBJ-2026-01
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    actions = db.Column(db.Text, nullable=True)        # ce qui sera fait (6.2 f)
    resources = db.Column(db.Text, nullable=True)      # ressources requises (6.2 g)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)   # responsable (6.2 h)
    due_date = db.Column(db.Date, nullable=True)       # échéance (6.2 i)
    evaluation = db.Column(db.Text, nullable=True)     # comment les résultats seront évalués (6.2 j)
    status = _enum(ObjectiveStatus, ObjectiveStatus.EN_COURS, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    indicators = db.relationship("Indicator", back_populates="objective", order_by="Indicator.ref")

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < date.today()
                    and self.status in (ObjectiveStatus.PLANIFIE, ObjectiveStatus.EN_COURS))


class Indicator(TenantMixin, db.Model):
    """Indicateur de surveillance et de mesure (9.1) : quoi, comment, quand, qui."""

    __tablename__ = "indicators"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_indicators_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # KPI-001
    name = db.Column(db.String(300), nullable=False)
    objective_id = db.Column(db.Integer, db.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True)
    control_id = db.Column(db.Integer, db.ForeignKey("controls.id", ondelete="SET NULL"), nullable=True)
    unit = db.Column(db.String(24), nullable=True)                      # %, j, nb...
    direction = _enum(Direction, Direction.HAUSSE, nullable=False)
    target = db.Column(db.Float, nullable=False)
    alert = db.Column(db.Float, nullable=True)          # seuil d'alerte (entre la cible et l'inacceptable)
    frequency = _enum(Frequency, Frequency.MENSUELLE, nullable=False)
    method = db.Column(db.Text, nullable=True)          # méthode / source de mesure
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)   # qui mesure
    analyst = db.Column(db.String(255), nullable=True)  # qui analyse et évalue
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    objective = db.relationship("Objective", back_populates="indicators")
    control = db.relationship("Control")
    owner = db.relationship("User")
    measurements = db.relationship("Measurement", back_populates="indicator", cascade="all, delete-orphan",
                                   order_by="Measurement.period.desc()")

    PERIOD_DAYS = {"MENSUELLE": 31, "TRIMESTRIELLE": 92, "SEMESTRIELLE": 183, "ANNUELLE": 366}

    @property
    def last(self):
        return self.measurements[0] if self.measurements else None

    def evaluate(self, value):
        """ok | alerte | hors_cible | None."""
        if value is None:
            return None
        better = (lambda a, b: a >= b) if self.direction == Direction.HAUSSE else (lambda a, b: a <= b)
        if better(value, self.target):
            return "ok"
        if self.alert is not None and better(value, self.alert):
            return "alerte"
        return "hors_cible"

    @property
    def state(self):
        return self.evaluate(self.last.value) if self.last else None

    @property
    def trend(self):
        """+1 amélioration, -1 dégradation, 0 stable, None si moins de 2 mesures."""
        if len(self.measurements) < 2:
            return None
        delta = self.measurements[0].value - self.measurements[1].value
        if delta == 0:
            return 0
        return (1 if delta > 0 else -1) * (1 if self.direction == Direction.HAUSSE else -1)

    @property
    def measurement_due(self):
        """Mesure attendue (dernière mesure plus ancienne que la périodicité)."""
        if not self.active:
            return False
        ref = self.last.period if self.last else self.created_at.date()
        return (date.today() - ref).days > self.PERIOD_DAYS[self.frequency.value] + 15

    def fmt(self, value):
        if value is None:
            return "-"
        v = f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") if value != int(value) else str(int(value))
        return f"{v} {self.unit}".strip() if self.unit else v


class Measurement(TenantMixin, db.Model):
    """Valeur mesurée d'un indicateur pour une période, avec analyse (9.1 e/f)."""

    __tablename__ = "measurements"

    id = db.Column(db.Integer, primary_key=True)
    indicator_id = db.Column(db.Integer, db.ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False, index=True)
    period = db.Column(db.Date, nullable=False)
    value = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=True)        # analyse / explication de l'écart
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    indicator = db.relationship("Indicator", back_populates="measurements")
    recorded_by = db.relationship("User")

    @property
    def ref(self):   # libellé dans le journal d'activité
        return f"{self.indicator.ref if self.indicator else 'KPI'} {self.period:%d/%m/%Y}"


# --- 10.2 ------------------------------------------------------------------------
class NonConformity(TenantMixin, db.Model):
    """Non-conformité de toute origine (10.2) : réaction, analyse des causes,
    actions correctives, vérification de l'efficacité, modifications du SMSI."""

    __tablename__ = "nonconformities"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_nonconformities_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # NC-2026-001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source = _enum(NcSource, NcSource.AUDIT_INTERNE, nullable=False)
    severity = _enum(NcSeverity, NcSeverity.MINEURE, nullable=False)
    status = _enum(NcStatus, NcStatus.OUVERTE, nullable=False, index=True)
    detected_at = db.Column(db.Date, nullable=True)
    detected_by = db.Column(db.String(255), nullable=True)
    clause = db.Column(db.String(64), nullable=True)
    control_id = db.Column(db.Integer, db.ForeignKey("controls.id", ondelete="SET NULL"), nullable=True)
    finding_id = db.Column(db.Integer, db.ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    correction = db.Column(db.Text, nullable=True)            # 10.2 a) réaction immédiate
    cause_method = db.Column(db.String(40), nullable=True)    # 5 pourquoi, Ishikawa...
    root_cause = db.Column(db.Text, nullable=True)            # 10.2 b) causes
    extent = db.Column(db.Text, nullable=True)                # 10.2 b) NC similaires existantes ou potentielles
    isms_changes = db.Column(db.Text, nullable=True)          # 10.2 e) modifications du SMSI
    # ISO 9001 (8.7) : élément de sortie non conforme (NULL = non-conformité du système)
    nc_kind = db.Column(db.String(12), nullable=True)
    product = db.Column(db.String(300), nullable=True)        # produit ou service concerné
    disposition = db.Column(db.String(16), nullable=True)     # traitement : correction, dérogation, rebut...
    effectiveness_due = db.Column(db.Date, nullable=True)
    effectiveness_at = db.Column(db.DateTime, nullable=True)  # 10.2 d) revue d'efficacité
    effectiveness_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    effectiveness_note = db.Column(db.Text, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    control = db.relationship("Control")
    finding = db.relationship("Finding")
    incident = db.relationship("Incident")
    owner = db.relationship("User", foreign_keys=[owner_id])
    effectiveness_by = db.relationship("User", foreign_keys=[effectiveness_by_id])
    actions = db.relationship("CorrectiveAction", back_populates="nonconformity", cascade="all, delete-orphan",
                              order_by="CorrectiveAction.created_at")

    @property
    def actions_done(self):
        from app.models.enums import ActionStatus
        return bool(self.actions) and all(a.status in (ActionStatus.REALISEE, ActionStatus.VERIFIEE) for a in self.actions)

    @property
    def is_overdue(self):
        return any(a.is_overdue for a in self.actions)


# --- A.5.19 - A.5.22 ---------------------------------------------------------------
class Supplier(TenantMixin, db.Model):
    """Fournisseur / sous-traitant et suivi de sa sécurité."""

    __tablename__ = "suppliers"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_suppliers_org_ref"),)

    REVIEW_MONTHS = {"CRITIQUE": 12, "IMPORTANT": 24, "STANDARD": 36}

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # FRN-001
    name = db.Column(db.String(300), nullable=False)
    service = db.Column(db.Text, nullable=True)
    category = _enum(SupplierCategory, SupplierCategory.LOGICIEL, nullable=False)
    criticality = _enum(Criticality, Criticality.STANDARD, nullable=False, index=True)
    data_access = _enum(DataAccess, DataAccess.AUCUN, nullable=False)
    status = _enum(SupplierStatus, SupplierStatus.ACTIF, nullable=False)
    contact = db.Column(db.String(255), nullable=True)
    contract_ref = db.Column(db.String(120), nullable=True)
    contract_end = db.Column(db.Date, nullable=True)
    security_clauses = db.Column(db.Boolean, default=False, nullable=False)   # A.5.20
    dpa = db.Column(db.Boolean, default=False, nullable=False)                # accord de traitement des données
    certifications = db.Column(db.Text, nullable=True)
    assessment_result = _enum(AssessmentResult, AssessmentResult.NON_EVALUE, nullable=False)
    last_assessment = db.Column(db.Date, nullable=True)
    next_assessment = db.Column(db.Date, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")

    @property
    def assessment_overdue(self):
        if self.status != SupplierStatus.ACTIF:
            return False
        return self.next_assessment is None or self.next_assessment < date.today()

    @property
    def gaps(self):
        """Écarts visibles : clauses, DPA si données personnelles, évaluation."""
        out = []
        if self.status != SupplierStatus.ACTIF:
            return out
        if self.criticality != Criticality.STANDARD and not self.security_clauses:
            out.append("clauses de sécurité absentes")
        if self.data_access == DataAccess.PERSONNEL and not self.dpa:
            out.append("accord de traitement (DPA) absent")
        if self.assessment_result == AssessmentResult.NON_CONFORME:
            out.append("évaluation non conforme")
        if self.assessment_overdue:
            out.append("évaluation à réaliser")
        return out

    def default_next(self, from_date):
        months = self.REVIEW_MONTHS[self.criticality.value]
        return from_date + timedelta(days=round(months * 30.44))


# --- A.5.31 (et 4.2 b) ---------------------------------------------------------------
class Requirement(TenantMixin, db.Model):
    """Exigence légale, réglementaire, contractuelle ou normative applicable."""

    __tablename__ = "requirements"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_requirements_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)          # EXG-001
    title = db.Column(db.String(300), nullable=False)
    req_type = _enum(RequirementType, RequirementType.LEGALE, nullable=False)
    source = db.Column(db.String(300), nullable=True)      # texte de référence (loi, article, contrat...)
    issuer = db.Column(db.String(255), nullable=True)      # autorité / émetteur
    obligation = db.Column(db.Text, nullable=True)         # ce qui est exigé
    response = db.Column(db.Text, nullable=True)           # comment l'organisme s'y conforme
    status = _enum(ComplianceStatus, ComplianceStatus.A_EVALUER, nullable=False, index=True)
    party_id = db.Column(db.Integer, db.ForeignKey("interested_parties.id", ondelete="SET NULL"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_review = db.Column(db.Date, nullable=True)
    next_review = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    party = db.relationship("InterestedParty", back_populates="requirements")
    owner = db.relationship("User")
    controls = db.relationship("Control", secondary=requirement_controls)

    @property
    def review_overdue(self):
        return bool(self.next_review and self.next_review < date.today())
