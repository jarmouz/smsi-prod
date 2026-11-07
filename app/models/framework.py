"""Référentiels (normes de systèmes de management) et leur activation par organisation.

Niveau plateforme (partagé par toutes les organisations, sans TenantMixin) :
  Framework      une norme et sa version (ISO/IEC 27001:2022, ISO 22301:2019...)
  FrameworkItem  ses chapitres, exigences et mesures (référence + intitulé court)
  ItemMapping    correspondances entre éléments de normes différentes

Niveau organisation (TenantMixin) :
  OrgFramework   normes activées par l'organisation
  FrameworkLink  rattachement d'un élément commun (audit, revue, document...) à des normes

Le texte normatif n'est jamais stocké : seulement des références et des intitulés courts.
"""
from datetime import datetime

from sqlalchemy.types import TypeDecorator, String

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import Theme


ISO27001 = "ISO27001"


class GroupType(TypeDecorator):
    """Groupe d'une mesure : un Theme pour l'ISO 27001 (comportement historique :
    .label, .annex), une simple chaîne pour les autres référentiels."""

    impl = String(40)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.value if isinstance(value, Theme) else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return Theme(value)
        except ValueError:
            return value


class Framework(db.Model):
    __tablename__ = "frameworks"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False)          # ISO27001
    name = db.Column(db.String(120), nullable=False)                      # ISO/IEC 27001:2022
    short_name = db.Column(db.String(40), nullable=False)                 # 27001
    domain = db.Column(db.String(120), nullable=False)                    # Sécurité de l'information
    # "controls" : catalogue de mesures + déclaration d'applicabilité ; "requirements" : exigences seules
    kind = db.Column(db.String(16), nullable=False, default="controls")
    available = db.Column(db.Boolean, nullable=False, default=True)       # activable par les organisations
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    items = db.relationship("FrameworkItem", back_populates="framework", order_by="FrameworkItem.sort_order",
                            cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Framework {self.code}>"


class FrameworkItem(db.Model):
    __tablename__ = "framework_items"
    __table_args__ = (db.UniqueConstraint("framework_id", "kind", "ref", name="uq_framework_items_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    framework_id = db.Column(db.Integer, db.ForeignKey("frameworks.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False, default="control")    # "clause" | "control"
    ref = db.Column(db.String(24), nullable=False)
    group = db.Column(db.String(40), nullable=True)                       # thème / chapitre
    title = db.Column(db.String(300), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    framework = db.relationship("Framework", back_populates="items")


class ItemMapping(db.Model):
    __tablename__ = "item_mappings"
    __table_args__ = (db.UniqueConstraint("source_id", "target_id", name="uq_item_mappings"),)

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("framework_items.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey("framework_items.id", ondelete="CASCADE"), nullable=False, index=True)
    relation = db.Column(db.String(16), nullable=False, default="partielle")  # "equivalente" | "partielle"
    note = db.Column(db.String(300), nullable=True)


class OrgFramework(TenantMixin, db.Model):
    __tablename__ = "org_frameworks"
    __table_args__ = (db.UniqueConstraint("organization_id", "framework_id", name="uq_org_frameworks"),)

    id = db.Column(db.Integer, primary_key=True)
    framework_id = db.Column(db.Integer, db.ForeignKey("frameworks.id"), nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    scope = db.Column(db.Text, nullable=True)                 # périmètre propre à cette norme
    target_date = db.Column(db.Date, nullable=True)           # certification visée
    certifier = db.Column(db.String(200), nullable=True)      # organisme de certification
    certified_on = db.Column(db.Date, nullable=True)
    enabled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    framework = db.relationship("Framework")


class FrameworkLink(TenantMixin, db.Model):
    """Rattache un élément commun (audit, revue, objectif, document, non-conformité...)
    à une ou plusieurs normes. Sans lien, l'élément concerne toutes les normes actives."""

    __tablename__ = "framework_links"
    __table_args__ = (db.UniqueConstraint("entity_type", "entity_id", "framework_id", name="uq_framework_links"),)

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    framework_id = db.Column(db.Integer, db.ForeignKey("frameworks.id", ondelete="CASCADE"), nullable=False, index=True)

    framework = db.relationship("Framework")


db.Index("ix_framework_links_entity", FrameworkLink.entity_type, FrameworkLink.entity_id)
