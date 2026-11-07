from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import ControlStatus
from app.models.framework import GroupType, ISO27001


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
    """Mesure d'un référentiel (Annexe A ISO/IEC 27001:2022 à l'origine) + son état dans
    la déclaration d'applicabilité de l'organisation. Copiée depuis le catalogue du
    référentiel (FrameworkItem) quand l'organisation active la norme."""

    __tablename__ = "controls"
    __table_args__ = (db.UniqueConstraint("organization_id", "framework_id", "ref", name="uq_controls_org_fw_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    framework_id = db.Column(db.Integer, db.ForeignKey("frameworks.id"), nullable=False, index=True)
    ref = db.Column(db.String(16), nullable=False, index=True)  # ex. "5.1"
    # Thème (Theme) pour l'ISO 27001, groupe libre pour les autres référentiels
    theme = db.Column(GroupType(), nullable=False, index=True)
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
    framework = db.relationship("Framework")
    risks = db.relationship("Risk", secondary=risk_controls, back_populates="controls")
    evidences = db.relationship("Evidence", secondary=evidence_controls, back_populates="controls")

    @classmethod
    def of(cls, code=ISO27001):
        """Mesures d'un référentiel (par défaut l'ISO 27001) pour l'organisation courante."""
        from app.models.framework import Framework
        fid = db.select(Framework.id).where(Framework.code == code).scalar_subquery()
        return cls.query.filter(cls.framework_id == fid)

    @property
    def annex_ref(self):
        return f"A.{self.ref}"

    @property
    def coverage(self):
        """Nombre de preuves rattachées - signal d'auditabilité."""
        return len(self.evidences)

    def __repr__(self):
        return f"<Control A.{self.ref}>"
