from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import Treatment, RiskStatus
from app.models.control import risk_controls


class Risk(TenantMixin, db.Model):
    """Risque de sécurité de l'information (approche ISO/IEC 27005).
    Score = vraisemblance × impact, avant (inhérent) et après (résiduel) traitement.
    Le traitement s'appuie sur des mesures de l'Annexe A (maillage risque↔mesure)."""

    __tablename__ = "risks"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_risks_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # R-2026-0001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)

    asset = db.Column(db.String(255), nullable=True)          # actif / périmètre concerné
    threat = db.Column(db.String(255), nullable=True)         # menace
    vulnerability = db.Column(db.String(255), nullable=True)  # vulnérabilité

    # Risque inhérent (échelles de l'organisation : 3 à 6 niveaux, voir risk_criteria)
    likelihood = db.Column(db.Integer, default=3, nullable=False)
    impact = db.Column(db.Integer, default=3, nullable=False)

    treatment = db.Column(db.Enum(Treatment, native_enum=False),
                          default=Treatment.REDUIRE, nullable=False)

    # Risque résiduel (après mesures)
    residual_likelihood = db.Column(db.Integer, nullable=True)
    residual_impact = db.Column(db.Integer, nullable=True)

    status = db.Column(db.Enum(RiskStatus, native_enum=False),
                       default=RiskStatus.IDENTIFIE, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    review_date = db.Column(db.Date, nullable=True)

    # Acceptation formelle du risque résiduel par son propriétaire (6.1.3 f)
    accepted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    accepted_score = db.Column(db.Integer, nullable=True)     # score résiduel au moment de l'acceptation
    acceptance_note = db.Column(db.Text, nullable=True)
    acceptance_until = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User", foreign_keys=[owner_id])
    accepted_by = db.relationship("User", foreign_keys=[accepted_by_id])
    controls = db.relationship("Control", secondary=risk_controls, back_populates="risks")
    assets = db.relationship("Asset", secondary="asset_risks", back_populates="risks", order_by="Asset.ref")

    @property
    def inherent_score(self):
        return (self.likelihood or 0) * (self.impact or 0)

    @property
    def residual_score(self):
        if self.residual_likelihood and self.residual_impact:
            return self.residual_likelihood * self.residual_impact
        return None

    @property
    def effective_score(self):
        return self.residual_score if self.residual_score is not None else self.inherent_score

    @staticmethod
    def level_of(score):
        from app.services import risk_criteria
        return risk_criteria.level_of(score)

    # --- acceptation du risque résiduel ------------------------------------
    @property
    def within_acceptance(self):
        """Score résiduel effectif dans les critères d'acceptation de l'organisation."""
        from app.services import risk_criteria
        return self.effective_score <= risk_criteria.acceptance_threshold()

    @property
    def acceptance_state(self):
        """valid | expired | outdated (cotation modifiée depuis) | required | not_required."""
        if self.accepted_at:
            if self.accepted_score != self.effective_score:
                return "outdated"
            if self.acceptance_until and self.acceptance_until < datetime.utcnow().date():
                return "expired"
            return "valid"
        if self.status == RiskStatus.CLOTURE or self.within_acceptance:
            return "not_required"
        return "required"

    @property
    def inherent_level(self):
        return self.level_of(self.inherent_score)

    @property
    def residual_level(self):
        return self.level_of(self.effective_score)

    def __repr__(self):
        return f"<Risk {self.ref} {self.inherent_score}>"
