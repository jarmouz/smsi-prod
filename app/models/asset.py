from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import (AssetCategory, Classification, AssetStatus,
                              IncidentCategory, IncidentSeverity, IncidentStatus,
                              AwarenessType, AwarenessStatus)


class Asset(TenantMixin, db.Model):
    """Actif de l'inventaire (mesure A.5.9 - inventaire des actifs)."""

    __tablename__ = "assets"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_assets_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # ACT-2026-0001
    name = db.Column(db.String(300), nullable=False)
    category = db.Column(db.Enum(AssetCategory, native_enum=False), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    custodian = db.Column(db.String(255), nullable=True)     # dépositaire / gestionnaire
    classification = db.Column(db.Enum(Classification, native_enum=False),
                               default=Classification.INTERNE, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.Enum(AssetStatus, native_enum=False),
                       default=AssetStatus.ACTIF, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    risks = db.relationship("Risk", secondary="asset_risks", back_populates="assets", order_by="Risk.ref")
    processes = db.relationship("BusinessProcess", secondary="process_assets", back_populates="assets")

    def __repr__(self):
        return f"<Asset {self.ref}>"


class Incident(TenantMixin, db.Model):
    """Incident de sécurité de l'information (mesures A.5.24 à A.5.28)."""

    __tablename__ = "incidents"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_incidents_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # INC-2026-0001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.Enum(IncidentCategory, native_enum=False), nullable=False)
    severity = db.Column(db.Enum(IncidentSeverity, native_enum=False), nullable=False, index=True)
    status = db.Column(db.Enum(IncidentStatus, native_enum=False), nullable=False, index=True)
    detected_at = db.Column(db.Date, nullable=True)
    reporter = db.Column(db.String(255), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    control_id = db.Column(db.Integer, db.ForeignKey("controls.id"), nullable=True)
    impact = db.Column(db.Text, nullable=True)
    resolution = db.Column(db.Text, nullable=True)       # traitement / leçons apprises
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assignee = db.relationship("User")
    control = db.relationship("Control")

    def __repr__(self):
        return f"<Incident {self.ref}>"


class AwarenessAction(TenantMixin, db.Model):
    """Action de sensibilisation / formation (mesure A.6.3)."""

    __tablename__ = "awareness_actions"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_awareness_actions_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # SENS-2026-0001
    title = db.Column(db.String(300), nullable=False)
    atype = db.Column(db.Enum(AwarenessType, native_enum=False), nullable=False)
    status = db.Column(db.Enum(AwarenessStatus, native_enum=False), nullable=False, index=True)
    action_date = db.Column(db.Date, nullable=True)
    audience = db.Column(db.String(255), nullable=True)
    participants = db.Column(db.Integer, nullable=True)
    completion_rate = db.Column(db.Integer, nullable=True)   # % de réalisation / réussite
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AwarenessAction {self.ref}>"
