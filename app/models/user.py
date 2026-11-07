from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import Role


class User(UserMixin, TenantMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role, native_enum=False), nullable=False, default=Role.LECTEUR)
    job_title = db.Column(db.String(255), nullable=True)
    is_active_flag = db.Column("is_active", db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    # Super-administrateur de la plateforme : gère les organisations et peut
    # basculer de l'une à l'autre (indépendant du rôle SMSI dans son organisation).
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False)
    # Lecture seule : toute modification est refusée, quel que soit le rôle
    # (ex. compte de démonstration avec la vue d'un administrateur).
    is_readonly = db.Column(db.Boolean, default=False, nullable=False)
    # Double authentification (TOTP) et politique de mot de passe
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_last_step = db.Column(db.BigInteger, nullable=True)     # anti-rejeu
    recovery_codes = db.Column(db.Text, nullable=True)            # empreintes JSON des codes de secours
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    # Récapitulatif des échéances par e-mail
    digest_frequency = db.Column(db.String(12), default="HEBDO", nullable=False)
    last_digest_at = db.Column(db.DateTime, nullable=True)

    organization = db.relationship("Organization")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)
        self.password_changed_at = datetime.utcnow()

    @property
    def mfa_enabled(self):
        return bool(self.totp_secret)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_active(self):
        return self.is_active_flag

    @property
    def role_label(self):
        return self.role.label if self.role else ""

    @property
    def is_admin(self):
        return self.role == Role.RSSI

    @property
    def can_edit(self):
        return self.role in (Role.RSSI, Role.CONTRIBUTEUR) and not self.is_readonly

    @property
    def can_view_platform(self):
        """Console Plateforme : super-admin, ou administrateur en lecture seule
        (limité à sa propre organisation)."""
        return self.is_superadmin or (self.is_readonly and self.role == Role.RSSI)

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p]
        return "".join(p[0].upper() for p in parts[:2]) or "?"

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    def register_failure(self, max_attempts, lockout_minutes):
        from datetime import timedelta
        self.failed_logins = (self.failed_logins or 0) + 1
        if self.failed_logins >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
            self.failed_logins = 0

    def reset_failures(self):
        self.failed_logins = 0
        self.locked_until = None

    def __repr__(self):
        return f"<User {self.email}>"
