from datetime import datetime

from app.extensions import db


class Setting(db.Model):
    """Réglages applicatifs (clé/valeur) : configuration SMTP, URL publique, etc.
    Modifiables par le gérant depuis l'administration, sans redéploiement.
    organization_id NULL = réglage global de la plateforme, utilisé par défaut
    par les organisations qui ne l'ont pas surchargé."""

    __tablename__ = "settings"
    __table_args__ = (
        db.Index("uq_settings_org_key", db.func.coalesce(db.text("organization_id"), 0), "key", unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    key = db.Column(db.String(80), nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Setting {self.organization_id}:{self.key}>"
