from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin


class Attachment(TenantMixin, db.Model):
    """Pièce jointe générique, rattachable à n'importe quel objet du SMSI
    (audit, constat, revue, document, preuve) via (entity_type, entity_id)."""

    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    filename = db.Column(db.String(300), nullable=False)      # nom d'origine
    stored_name = db.Column(db.String(300), nullable=False)   # nom sur disque (unique)
    content_type = db.Column(db.String(120), nullable=True)
    size = db.Column(db.Integer, nullable=True)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    uploaded_by = db.relationship("User")

    @property
    def size_human(self):
        n = self.size or 0
        for unit in ("o", "Ko", "Mo", "Go"):
            if n < 1024:
                return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} To"

    @property
    def ext(self):
        return (self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else "")

    def __repr__(self):
        return f"<Attachment {self.entity_type}#{self.entity_id} {self.filename}>"
