from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import ReviewStatus, ActionStatus


class ManagementReview(TenantMixin, db.Model):
    """Revue de direction du SMSI (clause 9.3).
    Les données d'entrée (9.3.2) et décisions/sorties (9.3.3) sont structurées."""

    __tablename__ = "management_reviews"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_management_reviews_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # RD-2026-01
    title = db.Column(db.String(300), nullable=False)
    review_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum(ReviewStatus, native_enum=False),
                       default=ReviewStatus.PLANIFIEE, nullable=False, index=True)
    participants = db.Column(db.Text, nullable=True)

    # Données d'entrée (clause 9.3.2) et conclusions (9.3.3)
    inputs = db.Column(db.Text, nullable=True)
    decisions = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    actions = db.relationship("ReviewAction", back_populates="review",
                              cascade="all, delete-orphan",
                              order_by="ReviewAction.created_at")

    def __repr__(self):
        return f"<ManagementReview {self.ref}>"


class ReviewAction(TenantMixin, db.Model):
    """Décision/action issue d'une revue de direction."""

    __tablename__ = "review_actions"

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("management_reviews.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum(ActionStatus, native_enum=False),
                       default=ActionStatus.OUVERTE, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    review = db.relationship("ManagementReview", back_populates="actions")
    owner = db.relationship("User")

    @property
    def is_overdue(self):
        return bool(self.status.is_open and self.due_date and self.due_date < datetime.utcnow().date())
