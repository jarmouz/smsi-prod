from datetime import datetime

from sqlalchemy.orm import declared_attr

from app.extensions import db


class Organization(db.Model):
    """Organisation cliente (tenant). Toutes les données du SMSI lui sont
    rattachées ; le filtrage est automatique (voir app.services.tenancy)."""

    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # Dossier racine Nextcloud du module Docs (défaut : <NEXTCLOUD_DOCS_FOLDER>/<slug>)
    docs_folder = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Organization {self.slug}>"


class TenantMixin:
    """Rattache un modèle à une organisation. Les requêtes sont filtrées et
    organization_id est renseigné automatiquement à l'insertion."""

    @declared_attr
    def organization_id(cls):
        return db.Column(db.Integer, db.ForeignKey("organizations.id"),
                         nullable=False, index=True)
