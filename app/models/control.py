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
    # kind : "control" (mesure d'annexe : Annexe A 27001, 27701, 42001) ou "clause" (exigence des
    # chapitres 4 à 10). La 27001 a les deux avec les mêmes numéros (« 5.1 ») : kind est dans la clé.
    __table_args__ = (db.UniqueConstraint("organization_id", "framework_id", "kind", "ref",
                                          name="uq_controls_org_fw_kind_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    framework_id = db.Column(db.Integer, db.ForeignKey("frameworks.id"), nullable=False, index=True)
    ref = db.Column(db.String(16), nullable=False, index=True)  # ex. "5.1"
    kind = db.Column(db.String(16), nullable=False, default="control", server_default="control")
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

    # Socle commun SMI (structure harmonisée) : exigence de la norme rattachée à une
    # exigence du socle. inherit = True : évaluée une seule fois dans le socle (statut,
    # applicabilité et responsable recopiés) ; False : évaluée séparément dans la norme.
    common_id = db.Column(db.Integer, db.ForeignKey("controls.id", ondelete="SET NULL"), nullable=True, index=True)
    inherit = db.Column(db.Boolean, nullable=False, default=False)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    framework = db.relationship("Framework")
    risks = db.relationship("Risk", secondary=risk_controls, back_populates="controls")
    evidences = db.relationship("Evidence", secondary=evidence_controls, back_populates="controls")
    common = db.relationship("Control", remote_side=[id], foreign_keys=[common_id])

    @property
    def inherited(self):
        """Exigence évaluée dans le socle commun (pas de saisie propre)."""
        return bool(self.inherit and self.common_id)

    @property
    def all_evidences(self):
        """Preuves propres + preuves du socle commun pour une exigence qui en hérite."""
        if self.inherited and self.common:
            seen = {e.id for e in self.evidences}
            return list(self.evidences) + [e for e in self.common.evidences if e.id not in seen]
        return list(self.evidences)

    @classmethod
    def of(cls, code=ISO27001, kind=None):
        """Éléments évalués d'un référentiel (par défaut l'ISO 27001) pour l'organisation courante.
        kind None : les mesures d'annexe pour une norme à mesures (DdA : jamais ses exigences de
        chapitres), les exigences pour une norme d'exigences ou le socle commun."""
        from app.models.framework import Framework
        fid = db.select(Framework.id).where(Framework.code == code).scalar_subquery()
        if kind is None:
            fkind = db.select(Framework.kind).where(Framework.code == code).scalar_subquery()
            kind = db.case((fkind == "controls", "control"), else_="clause")
        return cls.query.filter(cls.framework_id == fid, cls.kind == kind)

    @property
    def is_clause(self):
        """Exigence d'un chapitre 4 à 10 (et non mesure d'annexe)."""
        return self.kind == "clause"

    @property
    def annex_ref(self):
        """« A.5.1 » pour une mesure de l'ISO 27001 (références stockées sans préfixe), « §6.1.2 »
        pour une exigence de chapitre, la référence telle quelle pour les mesures des autres
        référentiels (« A.2.2 », « B.8.2.1 »)."""
        if self.kind == "clause":
            return f"§{self.ref}"
        if self.ref[:1].isalpha():
            return self.ref
        from app.models.framework import Framework
        fw = self.framework or (db.session.get(Framework, self.framework_id) if self.framework_id else None)
        return f"A.{self.ref}" if fw is None or fw.code == ISO27001 else f"§{self.ref}"

    @property
    def coverage(self):
        """Nombre de preuves rattachées - signal d'auditabilité."""
        return len(self.evidences)

    def __repr__(self):
        return f"<Control {self.kind} {self.ref}>"
