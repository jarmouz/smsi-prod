import enum
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import Treatment, RiskStatus
from app.models.control import risk_controls


# --- Registre commun du SMI (3.6) -----------------------------------------------------
# Domaine d'un risque -> (libellé, normes concernées par défaut). Stocké dans risk_domain ;
# NULL = sécurité de l'information (comportement historique, avant la 3.6).
SECURITE = "SECURITE"
DOMAINS = {
    SECURITE: ("Sécurité de l'information", ("ISO27001",)),
    "VIE_PRIVEE": ("Vie privée", ("ISO27701", "ISO27001")),     # la 27701 prolonge le SMSI
    "IA": ("Intelligence artificielle", ("ISO42001",)),
    "CONTINUITE": ("Continuité d'activité", ("ISO22301",)),
    "SERVICES": ("Services informatiques", ("ISO20000",)),
    "QUALITE": ("Qualité", ("ISO9001",)),
}
RISK_DOMAINS = {k: v[0] for k, v in DOMAINS.items() if k != SECURITE}   # valeurs stockées (hors NULL)
RISK_NATURES = {"OPPORTUNITE": "Opportunité"}                            # NULL = risque
OPPORTUNITE = "OPPORTUNITE"


def domain_label(key):
    return DOMAINS.get(key or SECURITE, DOMAINS[SECURITE])[0]


def domains_for(active_codes, current=None):
    """Domaines proposés : sécurité (historique) + ceux dont une norme est active (+ la valeur actuelle)."""
    return [(k, v[0]) for k, v in DOMAINS.items()
            if k == SECURITE or set(v[1]) & set(active_codes) or k == (current or SECURITE)]


class Risk(TenantMixin, db.Model):
    """Risque ou opportunité du système de management intégré (chapitre 6.1 commun aux normes,
    approche ISO/IEC 27005 / ISO 31000). Score = vraisemblance × impact, avant (inhérent) et
    après (résiduel) traitement. Le domaine donne les normes concernées par défaut ; des normes
    supplémentaires se rattachent par FrameworkLink. Le traitement s'appuie sur les mesures
    d'annexe des normes actives (27001, 27701, 42001 : maillage risque↔mesure)."""

    __tablename__ = "risks"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_risks_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)  # R-2026-0001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)

    asset = db.Column(db.String(255), nullable=True)          # actif / périmètre concerné
    threat = db.Column(db.String(255), nullable=True)         # menace
    vulnerability = db.Column(db.String(255), nullable=True)  # vulnérabilité
    # ISO 9001 (6.1) : domaine (NULL = sécurité de l'information, QUALITE) et nature (NULL = risque, OPPORTUNITE)
    risk_domain = db.Column(db.String(16), nullable=True, index=True)
    nature = db.Column(db.String(12), nullable=True)

    # Risque inhérent (échelles de l'organisation : 3 à 6 niveaux, voir risk_criteria)
    likelihood = db.Column(db.Integer, default=3, nullable=False)
    impact = db.Column(db.Integer, default=3, nullable=False)

    treatment = db.Column(db.Enum(Treatment, native_enum=False, length=16),
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

    # Réévaluation demandée (8.2 : incident, non-conformité ou changement lié) ; effacée
    # quand le risque est réévalué (enregistrement de sa fiche ou confirmation explicite)
    reassess_at = db.Column(db.DateTime, nullable=True)
    reassess_reason = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User", foreign_keys=[owner_id])
    accepted_by = db.relationship("User", foreign_keys=[accepted_by_id])
    controls = db.relationship("Control", secondary=risk_controls, back_populates="risks")
    assets = db.relationship("Asset", secondary="asset_risks", back_populates="risks", order_by="Asset.ref")
    links = db.relationship("RiskLink", back_populates="risk", cascade="all, delete-orphan")
    actions = db.relationship("RiskAction", back_populates="risk", cascade="all, delete-orphan",
                              order_by=lambda: [RiskAction.due_date.asc().nulls_last(), RiskAction.id])

    # --- domaine, nature, normes ------------------------------------------------
    @property
    def is_opportunity(self):
        return self.nature == OPPORTUNITE

    @property
    def domain_key(self):
        return self.risk_domain or SECURITE

    @property
    def domain_label(self):
        return domain_label(self.risk_domain)

    @property
    def framework_codes(self):
        """Normes concernées : celles du domaine + celles rattachées explicitement."""
        from app.services import frameworks as fw_svc
        codes = list(DOMAINS[self.domain_key][1]) if self.domain_key in DOMAINS else ["ISO27001"]
        if self.id:
            codes += [f.code for f in fw_svc.frameworks_of(self) if f.code not in codes]
        return codes

    def concerns(self, code):
        return code in self.framework_codes

    def flag_reassess(self, reason):
        """Demande une réévaluation (cumule les motifs tant qu'elle n'est pas faite)."""
        self.reassess_reason = (f"{self.reassess_reason} ; {reason}" if self.reassess_at and self.reassess_reason
                                else reason)[:300]
        self.reassess_at = datetime.utcnow()

    def clear_reassess(self):
        self.reassess_at = None
        self.reassess_reason = None

    # --- plan de traitement ------------------------------------------------------
    @property
    def open_actions(self):
        return [a for a in self.actions if a.status.is_open]

    @property
    def overdue_actions(self):
        return [a for a in self.actions if a.is_overdue]

    @property
    def plan_progress(self):
        """Avancement moyen des actions non abandonnées (None sans action)."""
        acts = [a for a in self.actions if a.status.value != "ABANDONNEE"]
        return round(sum(a.progress for a in acts) / len(acts)) if acts else None

    @property
    def plan_done(self):
        """Toutes les actions terminées, au moins une réalisée : le risque résiduel est à réévaluer."""
        return bool(self.actions) and not self.open_actions and any(a.status.value == "REALISEE" for a in self.actions)

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
        return self.is_opportunity or self.effective_score <= risk_criteria.acceptance_threshold()

    @property
    def acceptance_state(self):
        """valid | expired | outdated (cotation modifiée depuis) | required | not_required |
        not_applicable (opportunité : on décide de la saisir ou non, on ne l'accepte pas)."""
        if self.is_opportunity:
            return "not_applicable"
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

    @property
    def is_high(self):
        """Risque ouvert au niveau « élevé » ou au-delà (tableaux de bord, revue de direction) :
        jamais une opportunité, dont le score mesure un bénéfice."""
        from app.services import risk_criteria
        return (not self.is_opportunity and self.status.is_open
                and self.effective_score >= risk_criteria.high_threshold())

    # niveaux affichés : une opportunité n'a pas de couleur de gravité
    @property
    def display_inherent_level(self):
        return "opportunite" if self.is_opportunity else self.inherent_level

    @property
    def display_level(self):
        return "opportunite" if self.is_opportunity else self.residual_level

    def __repr__(self):
        return f"<Risk {self.ref} {self.inherent_score}>"


# --- Plan de traitement des risques (3.7) ----------------------------------------------
class RiskActionStatus(str, enum.Enum):
    PREVUE = "PREVUE"
    EN_COURS = "EN_COURS"
    REALISEE = "REALISEE"
    ABANDONNEE = "ABANDONNEE"

    @property
    def label(self):
        return {"PREVUE": "Prévue", "EN_COURS": "En cours", "REALISEE": "Réalisée",
                "ABANDONNEE": "Abandonnée"}[self.value]

    @property
    def is_open(self):
        return self.value in ("PREVUE", "EN_COURS")


class RiskAction(TenantMixin, db.Model):
    """Action du plan de traitement d'un risque (27001 / 42001 6.1.3 e) et 8.3, 6.1 des autres
    normes) : quoi, avec quelle mesure, qui, pour quand, avec quelles ressources, où en est-on.
    Pour une opportunité : action pour la saisir (plan d'action)."""

    __tablename__ = "risk_actions"

    id = db.Column(db.Integer, primary_key=True)
    risk_id = db.Column(db.Integer, db.ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    control_id = db.Column(db.Integer, db.ForeignKey("controls.id", ondelete="SET NULL"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    due_date = db.Column(db.Date, nullable=True)
    resources = db.Column(db.Text, nullable=True)                   # budget, moyens, prestataire
    status = db.Column(db.Enum(RiskActionStatus, native_enum=False, length=16),
                       default=RiskActionStatus.PREVUE, nullable=False, index=True)
    progress = db.Column(db.Integer, default=0, nullable=False)     # 0 à 100 %
    note = db.Column(db.Text, nullable=True)                        # résultat, blocage, preuve
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    risk = db.relationship("Risk", back_populates="actions")
    control = db.relationship("Control")
    owner = db.relationship("User")

    @property
    def is_overdue(self):
        return bool(self.status.is_open and self.due_date and self.due_date < date.today())

    @property
    def due_soon(self):
        return bool(self.status.is_open and self.due_date and not self.is_overdue
                    and self.due_date <= date.today() + timedelta(days=30))

    def set_status(self, status):
        """Change le statut et met l'avancement en cohérence (sans effet si le statut ne change pas)."""
        if status == self.status:
            return
        self.status = status
        if status == RiskActionStatus.REALISEE:
            self.progress = 100
            self.completed_at = self.completed_at or datetime.utcnow()
        else:
            self.completed_at = None
            if self.progress == 100:
                self.progress = 90

    def __repr__(self):
        return f"<RiskAction {self.id} {self.status.value}>"


# --- Maillage SMI (3.8) : risque <-> éléments des autres modules ----------------------
class RiskLink(TenantMixin, db.Model):
    """Lien entre un risque et un élément d'un autre module (système d'IA, traitement de
    données, activité de la BIA, plan de continuité, service IT, fournisseur, incident,
    changement, non-conformité). Types et pages : app/services/risk_links.py."""

    __tablename__ = "risk_links"
    __table_args__ = (db.UniqueConstraint("risk_id", "entity_type", "entity_id", name="uq_risk_links"),)

    id = db.Column(db.Integer, primary_key=True)
    risk_id = db.Column(db.Integer, db.ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    risk = db.relationship("Risk", back_populates="links")


db.Index("ix_risk_links_entity", RiskLink.entity_type, RiskLink.entity_id)
