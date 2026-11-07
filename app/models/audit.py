from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import AuditStatus, FindingType, ActionStatus


class Audit(TenantMixin, db.Model):
    """Audit interne du SMSI (clause 9.2)."""

    __tablename__ = "audits"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_audits_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # AUD-2026-01
    title = db.Column(db.String(300), nullable=False)
    scope = db.Column(db.Text, nullable=True)
    planned_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum(AuditStatus, native_enum=False),
                       default=AuditStatus.PLANIFIE, nullable=False, index=True)
    lead_auditor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lead_auditor = db.relationship("User")
    findings = db.relationship("Finding", back_populates="audit",
                               cascade="all, delete-orphan",
                               order_by="Finding.created_at")

    @property
    def nc_count(self):
        return sum(1 for f in self.findings
                   if f.type in (FindingType.NC_MAJEURE, FindingType.NC_MINEURE))

    def __repr__(self):
        return f"<Audit {self.ref}>"


class Finding(TenantMixin, db.Model):
    """Constat d'audit : non-conformité, observation ou piste d'amélioration.
    Peut référencer une mesure de l'Annexe A et/ou une clause ISO."""

    __tablename__ = "findings"

    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey("audits.id"), nullable=False)
    ref = db.Column(db.String(24), nullable=False)             # C-01
    type = db.Column(db.Enum(FindingType, native_enum=False), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    control_id = db.Column(db.Integer, db.ForeignKey("controls.id"), nullable=True)
    clause = db.Column(db.String(64), nullable=True)            # ex. "9.2"
    closed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    audit = db.relationship("Audit", back_populates="findings")
    control = db.relationship("Control")
    actions = db.relationship("CorrectiveAction", back_populates="finding",
                              cascade="all, delete-orphan",
                              order_by="CorrectiveAction.created_at")

    @property
    def is_nonconformity(self):
        return self.type in (FindingType.NC_MAJEURE, FindingType.NC_MINEURE)

    def __repr__(self):
        return f"<Finding {self.ref} {self.type.value}>"


class CorrectiveAction(TenantMixin, db.Model):
    """Action corrective rattachée à un constat (clause 10.1)."""

    __tablename__ = "corrective_actions"

    id = db.Column(db.Integer, primary_key=True)
    # rattachée à un constat d'audit OU à une non-conformité (10.2)
    finding_id = db.Column(db.Integer, db.ForeignKey("findings.id"), nullable=True)
    nonconformity_id = db.Column(db.Integer, db.ForeignKey("nonconformities.id", ondelete="CASCADE"), nullable=True)
    description = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum(ActionStatus, native_enum=False),
                       default=ActionStatus.OUVERTE, nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    finding = db.relationship("Finding", back_populates="actions")
    nonconformity = db.relationship("NonConformity", back_populates="actions")
    owner = db.relationship("User")

    @property
    def origin_ref(self):
        if self.finding:
            return f"{self.finding.audit.ref} - {self.finding.ref}"
        return self.nonconformity.ref if self.nonconformity else "-"

    @property
    def is_overdue(self):
        return bool(self.status.is_open and self.due_date and self.due_date < datetime.utcnow().date())

    def __repr__(self):
        return f"<CorrectiveAction {self.id} {self.status.value}>"
