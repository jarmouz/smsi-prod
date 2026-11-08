from datetime import date, datetime, timedelta

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import (AssetCategory, Classification, AssetStatus,
                              IncidentCategory, IncidentSeverity, IncidentStatus,
                              AwarenessType, AwarenessStatus)


# Dépendances (3.13) : une valeur métier (information, processus) repose sur des biens supports
asset_dependencies = db.Table(
    "asset_dependencies",
    db.Column("business_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    db.Column("support_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)

NEED_LEVELS = {1: "Faible", 2: "Modéré", 3: "Fort", 4: "Critique"}
NEED_KEYS = (("c", "Confidentialité"), ("i", "Intégrité"), ("a", "Disponibilité"), ("t", "Traçabilité"))
DISPOSAL_METHODS = {
    "EFFACEMENT": "Effacement sécurisé (logiciel certifié)",
    "DESTRUCTION": "Destruction physique du support",
    "CHIFFREMENT": "Effacement cryptographique (clé détruite)",
    "RESTITUTION": "Restitution au fournisseur / loueur avec certificat",
    "PRESTATAIRE": "Prestataire de destruction avec certificat",
    "AUCUNE_DONNEE": "Sans données (aucun effacement requis)",
}
EOS_WARN_DAYS = 180


class Asset(TenantMixin, db.Model):
    """Actif de l'inventaire (mesure A.5.9 - inventaire des actifs).
    3.13 : valeurs métier (informations, processus) cotées en DIC+T, biens supports qui les portent
    (dépendances, besoins hérités), cycle de vie (acquisition, fin de support, détenteur, élimination)."""

    __tablename__ = "assets"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_assets_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # ACT-2026-0001
    name = db.Column(db.String(300), nullable=False)
    category = db.Column(db.Enum(AssetCategory, native_enum=False, length=16), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    custodian = db.Column(db.String(255), nullable=True)     # dépositaire / gestionnaire
    classification = db.Column(db.Enum(Classification, native_enum=False),
                               default=Classification.INTERNE, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    # besoins de sécurité (1 faible à 4 critique) : propres à l'actif ; un bien support hérite en plus
    # du besoin le plus élevé des valeurs métier qu'il porte
    need_c = db.Column(db.Integer, nullable=True)
    need_i = db.Column(db.Integer, nullable=True)
    need_a = db.Column(db.Integer, nullable=True)
    need_t = db.Column(db.Integer, nullable=True)
    # cycle de vie
    acquired_on = db.Column(db.Date, nullable=True)
    end_of_support = db.Column(db.Date, nullable=True)          # fin de support / garantie / maintenance éditeur
    holder_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # détenteur
    disposed_on = db.Column(db.Date, nullable=True)
    disposal_method = db.Column(db.String(20), nullable=True)
    disposal_proof = db.Column(db.String(300), nullable=True)   # n° de certificat, PV, référence de preuve
    status = db.Column(db.Enum(AssetStatus, native_enum=False),
                       default=AssetStatus.ACTIF, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User", foreign_keys=[owner_id])
    holder = db.relationship("User", foreign_keys=[holder_id])
    supports = db.relationship("Asset", secondary=asset_dependencies,
                               primaryjoin=lambda: Asset.id == asset_dependencies.c.business_id,
                               secondaryjoin=lambda: Asset.id == asset_dependencies.c.support_id,
                               backref=db.backref("supported", order_by="Asset.ref"), order_by="Asset.ref")
    risks = db.relationship("Risk", secondary="asset_risks", back_populates="assets", order_by="Risk.ref")
    processes = db.relationship("BusinessProcess", secondary="process_assets", back_populates="assets")

    def __repr__(self):
        return f"<Asset {self.ref}>"

    # --- rôle et besoins DIC+T ------------------------------------------------------------
    @property
    def is_business(self):
        return self.category.is_business

    def own_needs(self):
        return {k: getattr(self, f"need_{k}") for k, _ in NEED_KEYS}

    def needs(self):
        """Besoins effectifs : propres, et pour un bien support le maximum des valeurs métier portées.
        Retourne {clé: (niveau, source)} ; source = None (propre) ou la valeur métier déterminante."""
        out = {}
        for k, _ in NEED_KEYS:
            best, src = getattr(self, f"need_{k}"), None
            if not self.is_business:
                for b in self.supported:
                    v = getattr(b, f"need_{k}")
                    if v and (best is None or v > best):
                        best, src = v, b
            out[k] = (best, src)
        return out

    @property
    def criticality(self):
        vals = [v for v, _ in self.needs().values() if v]
        return max(vals) if vals else None

    @property
    def criticality_label(self):
        return NEED_LEVELS.get(self.criticality, "Non évaluée")

    @property
    def dict_label(self):
        """Ex. « C3 I4 D2 T2 » (besoins effectifs)."""
        n = self.needs()
        letters = {"c": "C", "i": "I", "a": "D", "t": "T"}
        return " ".join(f"{letters[k]}{v}" for k, (v, _) in n.items() if v) or "-"

    # --- cycle de vie ---------------------------------------------------------------------
    @property
    def in_service(self):
        return self.status != AssetStatus.RETIRE

    @property
    def eos_state(self):
        """dépassée | proche (moins de 180 jours) | None."""
        if not self.end_of_support or not self.in_service:
            return None
        today = date.today()
        if self.end_of_support < today:
            return "depassee"
        return "proche" if self.end_of_support <= today + timedelta(days=EOS_WARN_DAYS) else None

    @property
    def disposal_missing(self):
        """Matériel ou logiciel retiré sans preuve d'élimination sécurisée (A.7.14)."""
        return (self.status == AssetStatus.RETIRE and self.category.value in ("MATERIEL", "LOGICIEL")
                and not (self.disposal_method and (self.disposal_proof or self.disposal_method == "AUCUNE_DONNEE")))

    @property
    def to_recover(self):
        """Détenu par un compte désactivé : à restituer (A.5.11)."""
        return bool(self.in_service and self.holder is not None and not self.holder.is_active_flag)

    @property
    def disposal_label(self):
        return DISPOSAL_METHODS.get(self.disposal_method, "")


class Incident(TenantMixin, db.Model):
    """Incident de sécurité de l'information (mesures A.5.24 à A.5.28)."""

    __tablename__ = "incidents"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_incidents_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # INC-2026-0001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.Enum(IncidentCategory, native_enum=False), nullable=False)
    severity = db.Column(db.Enum(IncidentSeverity, native_enum=False), nullable=False, index=True)
    status = db.Column(db.Enum(IncidentStatus, native_enum=False), nullable=False, index=True)
    detected_at = db.Column(db.Date, nullable=True)
    reporter = db.Column(db.String(255), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    control_id = db.Column(db.Integer, db.ForeignKey("controls.id"), nullable=True)
    impact = db.Column(db.Text, nullable=True)
    resolution = db.Column(db.Text, nullable=True)       # traitement / leçons apprises
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assignee = db.relationship("User")
    control = db.relationship("Control")

    def __repr__(self):
        return f"<Incident {self.ref}>"


class AwarenessAction(TenantMixin, db.Model):
    """Action de sensibilisation / formation (mesure A.6.3)."""

    __tablename__ = "awareness_actions"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_awareness_actions_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # SENS-2026-0001
    title = db.Column(db.String(300), nullable=False)
    atype = db.Column(db.Enum(AwarenessType, native_enum=False), nullable=False)
    status = db.Column(db.Enum(AwarenessStatus, native_enum=False), nullable=False, index=True)
    action_date = db.Column(db.Date, nullable=True)
    audience = db.Column(db.String(255), nullable=True)
    participants = db.Column(db.Integer, nullable=True)
    completion_rate = db.Column(db.Integer, nullable=True)   # % de réalisation / réussite
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AwarenessAction {self.ref}>"
