"""Page de confiance publique (3.11) : demandes d'accès aux documents réservés.

Un visiteur (client, prospect, auditeur de second partie) demande l'accès aux documents
« sur demande » ; le RSSI accorde (lien personnel valable N jours) ou refuse.
"""
from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin

TRUST_STATUSES = {"EN_ATTENTE": "En attente", "ACCORDEE": "Accordée", "REFUSEE": "Refusée", "REVOQUEE": "Révoquée"}
DOC_VISIBILITY = {"PUBLIC": "Public (téléchargeable)", "DEMANDE": "Sur demande (accès accordé)"}


class TrustRequest(TenantMixin, db.Model):
    __tablename__ = "trust_requests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    company = db.Column(db.String(200), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(12), nullable=False, default="EN_ATTENTE", index=True)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    downloads = db.Column(db.Integer, nullable=False, default=0)
    last_access_at = db.Column(db.DateTime, nullable=True)

    decided_by = db.relationship("User")

    @property
    def status_label(self):
        return TRUST_STATUSES.get(self.status, self.status)

    @property
    def active(self):
        return self.status == "ACCORDEE" and self.expires_at is not None and self.expires_at > datetime.utcnow()
