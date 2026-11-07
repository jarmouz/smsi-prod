from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin


class ActivityLog(TenantMixin, db.Model):
    """Journal d'activité (piste d'audit) : qui a fait quoi, quand, avec les
    valeurs avant / après. Alimenté automatiquement (app.services.audit_trail),
    jamais modifié ni supprimé par l'application. user_id n'a volontairement pas
    de clé étrangère : l'entrée survit à la suppression du compte."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    user_name = db.Column(db.String(255), nullable=True)
    action = db.Column(db.String(32), nullable=False, index=True)   # create, update, delete, login...
    entity_type = db.Column(db.String(40), nullable=True, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    entity_ref = db.Column(db.String(300), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    changes = db.Column(db.JSON, nullable=True)                    # {champ: [avant, après]}
    ip = db.Column(db.String(64), nullable=True)

    ACTION_LABELS = {
        "create": "Création", "update": "Modification", "delete": "Suppression",
        "login": "Connexion", "login_failed": "Échec de connexion", "logout": "Déconnexion",
        "mfa": "Double authentification", "password": "Mot de passe", "export": "Export",
        "workflow": "Circuit d'approbation", "accept": "Acceptation de risque", "admin": "Administration",
    }

    @property
    def action_label(self):
        return self.ACTION_LABELS.get(self.action, self.action)

    def __repr__(self):
        return f"<ActivityLog {self.action} {self.entity_type}#{self.entity_id}>"
