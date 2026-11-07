"""Protection de la vie privée (ISO/IEC 27701) : registre des traitements et demandes
des personnes concernées. Les données des personnes elles-mêmes ne sont pas stockées ici :
seulement ce qui décrit le traitement ou trace la demande (minimisation)."""
import enum
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.organization import TenantMixin


def _enum(e, default=None, **kw):
    return db.Column(db.Enum(e, native_enum=False, length=24), default=default, **kw)


class LegalBasis(str, enum.Enum):
    A_DETERMINER = "A_DETERMINER"
    CONSENTEMENT = "CONSENTEMENT"
    CONTRAT = "CONTRAT"
    OBLIGATION_LEGALE = "OBLIGATION_LEGALE"
    INTERETS_VITAUX = "INTERETS_VITAUX"
    MISSION_PUBLIQUE = "MISSION_PUBLIQUE"
    INTERET_LEGITIME = "INTERET_LEGITIME"

    @property
    def label(self):
        return {"A_DETERMINER": "À déterminer", "CONSENTEMENT": "Consentement", "CONTRAT": "Exécution d'un contrat",
                "OBLIGATION_LEGALE": "Obligation légale", "INTERETS_VITAUX": "Intérêts vitaux",
                "MISSION_PUBLIQUE": "Mission d'intérêt public", "INTERET_LEGITIME": "Intérêt légitime"}[self.value]


class ProcessingRole(str, enum.Enum):
    RESPONSABLE = "RESPONSABLE"
    CO_RESPONSABLE = "CO_RESPONSABLE"
    SOUS_TRAITANT = "SOUS_TRAITANT"

    @property
    def label(self):
        return {"RESPONSABLE": "Responsable de traitement", "CO_RESPONSABLE": "Responsable conjoint",
                "SOUS_TRAITANT": "Sous-traitant"}[self.value]


class DpiaStatus(str, enum.Enum):
    A_EVALUER = "A_EVALUER"
    NON_REQUISE = "NON_REQUISE"
    A_REALISER = "A_REALISER"
    REALISEE = "REALISEE"

    @property
    def label(self):
        return {"A_EVALUER": "Nécessité à évaluer", "NON_REQUISE": "Non requise", "A_REALISER": "À réaliser",
                "REALISEE": "Réalisée"}[self.value]


class ProcessingStatus(str, enum.Enum):
    EN_PROJET = "EN_PROJET"
    ACTIF = "ACTIF"
    ARRETE = "ARRETE"

    @property
    def label(self):
        return {"EN_PROJET": "En projet", "ACTIF": "En cours", "ARRETE": "Arrêté"}[self.value]


class RequestType(str, enum.Enum):
    ACCES = "ACCES"
    RECTIFICATION = "RECTIFICATION"
    EFFACEMENT = "EFFACEMENT"
    OPPOSITION = "OPPOSITION"
    LIMITATION = "LIMITATION"
    PORTABILITE = "PORTABILITE"
    RETRAIT_CONSENTEMENT = "RETRAIT_CONSENTEMENT"
    AUTRE = "AUTRE"

    @property
    def label(self):
        return {"ACCES": "Accès", "RECTIFICATION": "Rectification", "EFFACEMENT": "Effacement",
                "OPPOSITION": "Opposition", "LIMITATION": "Limitation", "PORTABILITE": "Portabilité",
                "RETRAIT_CONSENTEMENT": "Retrait du consentement", "AUTRE": "Autre"}[self.value]


class RequestStatus(str, enum.Enum):
    RECUE = "RECUE"
    EN_COURS = "EN_COURS"
    CLOTUREE = "CLOTUREE"
    REJETEE = "REJETEE"

    @property
    def label(self):
        return {"RECUE": "Reçue", "EN_COURS": "En cours", "CLOTUREE": "Clôturée (réponse envoyée)",
                "REJETEE": "Rejetée (motivée)"}[self.value]

    @property
    def closed(self):
        return self.value in ("CLOTUREE", "REJETEE")


processing_assets = db.Table(
    "processing_assets",
    db.Column("processing_id", db.Integer, db.ForeignKey("processing_activities.id", ondelete="CASCADE"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)
processing_suppliers = db.Table(
    "processing_suppliers",
    db.Column("processing_id", db.Integer, db.ForeignKey("processing_activities.id", ondelete="CASCADE"), primary_key=True),
    db.Column("supplier_id", db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True),
)


class ProcessingActivity(TenantMixin, db.Model):
    """Activité de traitement de données personnelles (registre ; 27701 A.7.2.8 / B.8.2.6)."""

    __tablename__ = "processing_activities"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_processing_org_ref"),)

    REVIEW_MONTHS = 12

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # TRT-001
    name = db.Column(db.String(300), nullable=False)
    purpose = db.Column(db.Text, nullable=True)                                # finalité(s)
    role = _enum(ProcessingRole, ProcessingRole.RESPONSABLE, nullable=False)
    legal_basis = _enum(LegalBasis, LegalBasis.A_DETERMINER, nullable=False)
    legal_basis_detail = db.Column(db.Text, nullable=True)                     # ex. intérêt poursuivi, texte de loi
    data_subjects = db.Column(db.Text, nullable=True)                          # catégories de personnes
    data_categories = db.Column(db.Text, nullable=True)                        # catégories de données
    sensitive_data = db.Column(db.Boolean, default=False, nullable=False)      # données sensibles / particulières
    sensitive_detail = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(300), nullable=True)                          # origine des données
    recipients = db.Column(db.Text, nullable=True)                             # destinataires internes et externes
    transfers = db.Column(db.Boolean, default=False, nullable=False)           # hors du pays
    transfer_detail = db.Column(db.Text, nullable=True)                        # pays + garanties
    retention = db.Column(db.String(300), nullable=True)                       # durées de conservation
    security_measures = db.Column(db.Text, nullable=True)
    dpia = _enum(DpiaStatus, DpiaStatus.A_EVALUER, nullable=False)
    dpia_date = db.Column(db.Date, nullable=True)
    status = _enum(ProcessingStatus, ProcessingStatus.ACTIF, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_review = db.Column(db.Date, nullable=True)
    next_review = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    assets = db.relationship("Asset", secondary=processing_assets)
    suppliers = db.relationship("Supplier", secondary=processing_suppliers)

    @property
    def review_overdue(self):
        return self.status == ProcessingStatus.ACTIF and (self.next_review is None or self.next_review < date.today())

    @property
    def gaps(self):
        """Points à traiter, visibles dans le registre."""
        if self.status == ProcessingStatus.ARRETE:
            return []
        out = []
        if self.legal_basis == LegalBasis.A_DETERMINER and self.role != ProcessingRole.SOUS_TRAITANT:
            out.append("base juridique à déterminer")
        if not (self.purpose or "").strip():
            out.append("finalité non décrite")
        if not (self.retention or "").strip():
            out.append("durée de conservation non définie")
        if self.dpia in (DpiaStatus.A_EVALUER, DpiaStatus.A_REALISER):
            out.append("analyse d'impact " + ("à évaluer" if self.dpia == DpiaStatus.A_EVALUER else "à réaliser"))
        if self.transfers and not (self.transfer_detail or "").strip():
            out.append("transfert sans garanties décrites")
        if any(not s.dpa for s in self.suppliers):
            out.append("sous-traitant sans accord de traitement (DPA)")
        if self.review_overdue:
            out.append("revue à faire")
        return out

    def default_next(self, d):
        return d + timedelta(days=365 * self.REVIEW_MONTHS // 12)


class SubjectRequest(TenantMixin, db.Model):
    """Demande d'exercice de droits d'une personne concernée (27701 A.7.3.9)."""

    __tablename__ = "subject_requests"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_subject_requests_org_ref"),)

    RESPONSE_DAYS = 30

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # DMD-2026-0001
    request_type = _enum(RequestType, RequestType.ACCES, nullable=False)
    requester = db.Column(db.String(200), nullable=False)                      # nom ou pseudonyme du demandeur
    channel = db.Column(db.String(120), nullable=True)                         # courriel, courrier, formulaire...
    received_on = db.Column(db.Date, nullable=False, default=date.today)
    due_on = db.Column(db.Date, nullable=True)
    processing_id = db.Column(db.Integer, db.ForeignKey("processing_activities.id", ondelete="SET NULL"), nullable=True)
    identity_verified = db.Column(db.Boolean, default=False, nullable=False)
    status = _enum(RequestStatus, RequestStatus.RECUE, nullable=False, index=True)
    handled_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    response = db.Column(db.Text, nullable=True)                               # réponse apportée / motif du rejet
    closed_on = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    processing = db.relationship("ProcessingActivity")
    handled_by = db.relationship("User")

    @property
    def title(self):
        return f"{self.request_type.label} - {self.requester}"

    @property
    def overdue(self):
        return not self.status.closed and self.due_on is not None and self.due_on < date.today()
