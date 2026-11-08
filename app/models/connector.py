"""Connecteurs d'inventaire (3.15) : sources externes qui alimentent les actifs."""
from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin


class Connector(TenantMixin, db.Model):
    __tablename__ = "connectors"
    __table_args__ = (db.UniqueConstraint("organization_id", "kind", "name", name="uq_connectors_org_kind_name"),)

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)        # glpi, entra, intune, azure, aws, api
    name = db.Column(db.String(120), nullable=False)
    config = db.Column(db.JSON, nullable=True)             # paramètres non secrets
    secret_enc = db.Column(db.Text, nullable=True)         # secrets chiffrés (app.services.connectors.seal)
    auto = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(10), nullable=True)  # ok | erreur
    last_summary = db.Column(db.String(400), nullable=True)

    runs = db.relationship("ConnectorRun", back_populates="connector", cascade="all, delete-orphan",
                           order_by="ConnectorRun.id.desc()")

    def __repr__(self):
        return f"<Connector {self.kind}:{self.name}>"


class ConnectorRun(TenantMixin, db.Model):
    __tablename__ = "connector_runs"

    id = db.Column(db.Integer, primary_key=True)
    connector_id = db.Column(db.Integer, db.ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    summary = db.Column(db.String(400), nullable=True)

    connector = db.relationship("Connector", back_populates="runs")
