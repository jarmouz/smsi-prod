from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import Theme, ControlStatus


# Tables d'association (maillage entre modules)
risk_controls = db.Table(
    "risk_controls",
    db.Column("risk_id", db.Integer, db.ForeignKey("risks.id", ondelete="CASCADE"), primary_key=True),
    db.Column("control_id", db.Integer, db.ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
)

evidence_controls = db.Table(
    "evidence_controls",
    db.Column("evidence_id", db.Integer, db.ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
    db.Column("control_id", db.Integer, db.ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
)


class Control(TenantMixin, db.Model):
    """Mesure de l'Annexe A ISO/IEC 27001:2022 + son état dans la Déclaration
    d'applicabilité (DdA). Le catalogue des 93 mesures est semé à l'initialisation."""

    __tablename__ = "controls"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_controls_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(16), nullable=False, index=True)  # ex. "5.1"
    theme = db.Column(db.Enum(Theme, native_enum=False), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)

    # État DdA
    applicable = db.Column(db.Boolean, default=True, nullable=False)
    justification = db.Column(db.Text, nullable=True)       # inclusion / exclusion
    status = db.Column(db.Enum(ControlStatus, native_enum=False),
                       default=ControlStatus.NON_DEMARRE, nullable=False)
    implementation = db.Column(db.Text, nullable=True)       # comment c'est mis en œuvre
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    risks = db.relationship("Risk", secondary=risk_controls, back_populates="controls")
    evidences = db.relationship("Evidence", secondary=evidence_controls, back_populates="controls")

    @property
    def annex_ref(self):
        return f"A.{self.ref}"

    @property
    def coverage(self):
        """Nombre de preuves rattachées - signal d'auditabilité."""
        return len(self.evidences)

    def __repr__(self):
        return f"<Control A.{self.ref}>"
