"""Jetons d'accès à l'API (3.14). Seule l'empreinte du jeton est conservée : il n'est affiché qu'à sa création."""
import hashlib
import secrets
from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin

SCOPE_ASSETS_READ = "actifs:lecture"
TOKEN_DURATIONS = {30: "30 jours", 90: "90 jours", 180: "180 jours", 365: "1 an"}
PREFIX = "itg_"


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token():
    return PREFIX + secrets.token_urlsafe(32)


class ApiToken(TenantMixin, db.Model):
    __tablename__ = "api_tokens"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    token_prefix = db.Column(db.String(16), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    scopes = db.Column(db.String(120), nullable=False, default=SCOPE_ASSETS_READ)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    last_used_ip = db.Column(db.String(64), nullable=True)
    window_minute = db.Column(db.Integer, nullable=False, default=0)   # limitation de débit par minute
    window_count = db.Column(db.Integer, nullable=False, default=0)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    revoked_by = db.relationship("User", foreign_keys=[revoked_by_id])

    @property
    def state(self):
        if self.revoked_at:
            return "revoque"
        return "expire" if self.expires_at <= datetime.utcnow() else "actif"

    def allows(self, scope):
        return scope in (self.scopes or "").split()

    def __repr__(self):
        return f"<ApiToken {self.token_prefix}>"
