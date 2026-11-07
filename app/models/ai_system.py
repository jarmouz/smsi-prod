"""Intelligence artificielle (ISO/IEC 42001) : inventaire des systèmes d'IA et études d'impact."""
import enum
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.organization import TenantMixin


def _enum(e, default=None, **kw):
    return db.Column(db.Enum(e, native_enum=False, length=24), default=default, **kw)


class AiRole(str, enum.Enum):
    FOURNISSEUR = "FOURNISSEUR"
    DEPLOYEUR = "DEPLOYEUR"
    LES_DEUX = "LES_DEUX"

    @property
    def label(self):
        return {"FOURNISSEUR": "Fournisseur / développeur", "DEPLOYEUR": "Utilisateur / déployeur",
                "LES_DEUX": "Développe et utilise"}[self.value]


class AiType(str, enum.Enum):
    APPRENTISSAGE = "APPRENTISSAGE"
    GENERATIVE = "GENERATIVE"
    REGLES = "REGLES"
    AUTRE = "AUTRE"

    @property
    def label(self):
        return {"APPRENTISSAGE": "Apprentissage automatique", "GENERATIVE": "IA générative (LLM...)",
                "REGLES": "Système à base de règles", "AUTRE": "Autre"}[self.value]


class AiRiskLevel(str, enum.Enum):
    FAIBLE = "FAIBLE"
    LIMITE = "LIMITE"
    ELEVE = "ELEVE"
    INACCEPTABLE = "INACCEPTABLE"

    @property
    def label(self):
        return {"FAIBLE": "Faible", "LIMITE": "Limité", "ELEVE": "Élevé", "INACCEPTABLE": "Inacceptable"}[self.value]


class AiLifecycle(str, enum.Enum):
    CONCEPTION = "CONCEPTION"
    DEVELOPPEMENT = "DEVELOPPEMENT"
    VALIDATION = "VALIDATION"
    PRODUCTION = "PRODUCTION"
    RETIRE = "RETIRE"

    @property
    def label(self):
        return {"CONCEPTION": "Conception", "DEVELOPPEMENT": "Développement", "VALIDATION": "Vérification et validation",
                "PRODUCTION": "En production", "RETIRE": "Retiré"}[self.value]


class ImpactLevel(str, enum.Enum):
    FAIBLE = "FAIBLE"
    MOYEN = "MOYEN"
    ELEVE = "ELEVE"

    @property
    def label(self):
        return {"FAIBLE": "Faible", "MOYEN": "Moyen", "ELEVE": "Élevé"}[self.value]


class ImpactDecision(str, enum.Enum):
    EN_COURS = "EN_COURS"
    APPROUVE = "APPROUVE"
    APPROUVE_CONDITIONS = "APPROUVE_CONDITIONS"
    REFUSE = "REFUSE"

    @property
    def label(self):
        return {"EN_COURS": "Évaluation en cours", "APPROUVE": "Utilisation approuvée",
                "APPROUVE_CONDITIONS": "Approuvée sous conditions", "REFUSE": "Utilisation refusée"}[self.value]


ai_system_assets = db.Table(
    "ai_system_assets",
    db.Column("ai_system_id", db.Integer, db.ForeignKey("ai_systems.id", ondelete="CASCADE"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)


class AiSystem(TenantMixin, db.Model):
    """Système d'IA développé ou utilisé par l'organisation (42001 A.4, A.6, A.9)."""

    __tablename__ = "ai_systems"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_ai_systems_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # IA-001
    name = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    intended_use = db.Column(db.Text, nullable=True)                           # utilisation prévue (A.9.4)
    role = _enum(AiRole, AiRole.DEPLOYEUR, nullable=False)
    ai_type = _enum(AiType, AiType.GENERATIVE, nullable=False)
    provider = db.Column(db.String(300), nullable=True)                        # modèle / éditeur
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    data_used = db.Column(db.Text, nullable=True)                              # données d'entraînement / d'entrée (A.7)
    personal_data = db.Column(db.Boolean, default=False, nullable=False)
    processing_id = db.Column(db.Integer, db.ForeignKey("processing_activities.id", ondelete="SET NULL"), nullable=True)
    affected_parties = db.Column(db.Text, nullable=True)                       # personnes et groupes concernés
    automated_decisions = db.Column(db.Boolean, default=False, nullable=False) # décisions sans intervention humaine
    human_oversight = db.Column(db.Text, nullable=True)                        # supervision humaine
    risk_level = _enum(AiRiskLevel, AiRiskLevel.LIMITE, nullable=False, index=True)
    lifecycle = _enum(AiLifecycle, AiLifecycle.PRODUCTION, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    supplier = db.relationship("Supplier")
    processing = db.relationship("ProcessingActivity")
    assets = db.relationship("Asset", secondary=ai_system_assets)
    assessments = db.relationship("AiImpactAssessment", back_populates="system", cascade="all, delete-orphan",
                                  order_by="AiImpactAssessment.assessed_on.desc()")

    @property
    def last_assessment(self):
        return next((a for a in self.assessments if a.decision != ImpactDecision.EN_COURS), None)

    @property
    def gaps(self):
        if self.lifecycle == AiLifecycle.RETIRE:
            return []
        out = []
        if not (self.intended_use or "").strip():
            out.append("utilisation prévue non décrite")
        last = self.last_assessment
        if last is None:
            out.append("étude d'impact à réaliser")
        elif last.review_overdue:
            out.append("étude d'impact à revoir")
        elif last.decision == ImpactDecision.REFUSE and self.lifecycle == AiLifecycle.PRODUCTION:
            out.append("en production malgré une utilisation refusée")
        if self.risk_level in (AiRiskLevel.ELEVE, AiRiskLevel.INACCEPTABLE) and not (self.human_oversight or "").strip():
            out.append("supervision humaine non décrite")
        if self.risk_level == AiRiskLevel.INACCEPTABLE and self.lifecycle == AiLifecycle.PRODUCTION:
            out.append("risque inacceptable en production")
        if self.personal_data and self.processing_id is None:
            out.append("données personnelles sans traitement au registre")
        return out


class AiImpactAssessment(TenantMixin, db.Model):
    """Étude d'impact d'un système d'IA sur les personnes, les groupes et la société (42001 A.5)."""

    __tablename__ = "ai_impact_assessments"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_ai_impacts_org_ref"),)

    REVIEW_MONTHS = 12

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # EIA-2026-0001
    ai_system_id = db.Column(db.Integer, db.ForeignKey("ai_systems.id", ondelete="CASCADE"), nullable=False, index=True)
    assessed_on = db.Column(db.Date, nullable=False, default=date.today)
    assessor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    impacts_individuals = db.Column(db.Text, nullable=True)                    # A.5.4
    impacts_society = db.Column(db.Text, nullable=True)                        # A.5.5
    impact_level = _enum(ImpactLevel, ImpactLevel.MOYEN, nullable=False)
    measures = db.Column(db.Text, nullable=True)                               # mesures de réduction
    residual = db.Column(db.Text, nullable=True)                               # impact résiduel accepté
    decision = _enum(ImpactDecision, ImpactDecision.EN_COURS, nullable=False)
    next_review = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    system = db.relationship("AiSystem", back_populates="assessments")
    assessor = db.relationship("User")

    @property
    def title(self):
        return f"Étude d'impact - {self.system.name}" if self.system else "Étude d'impact"

    @property
    def review_overdue(self):
        return self.next_review is not None and self.next_review < date.today()

    def default_next(self, d):
        return d + timedelta(days=365 * self.REVIEW_MONTHS // 12)
