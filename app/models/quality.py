"""ISO 9001:2015 - management de la qualité : cartographie des processus (4.4), satisfaction
client (9.1.2) et réclamations. Les risques et opportunités (6.1) et les produits non conformes
(8.7) prolongent les registres communs (Risk, NonConformity) par des colonnes facultatives."""
import enum
from datetime import datetime, date, timedelta

from app.extensions import db
from app.models.organization import TenantMixin


def _enum(e, default=None, **kw):
    return db.Column(db.Enum(e, native_enum=False, length=24), default=default, **kw)


class _Labelled(str, enum.Enum):
    @property
    def label(self):
        return self._labels()[self.value]


# --- Prolongements des registres communs (valeurs NULL = comportement historique) ---------
RISK_DOMAINS = {"QUALITE": "Qualité"}                     # NULL = sécurité de l'information
RISK_NATURES = {"OPPORTUNITE": "Opportunité"}             # NULL = risque
NC_KINDS = {"PRODUIT": "Produit ou service non conforme"}  # NULL = non-conformité du système
NC_DISPOSITIONS = {"CORRECTION": "Correction", "REPRISE": "Reprise / retouche", "DEROGATION": "Acceptation par dérogation",
                   "RETOUR": "Retour / remplacement", "SUSPENSION": "Suspension de la prestation",
                   "REBUT": "Mise au rebut", "AUTRE": "Autre"}


# --- Cartographie des processus (4.4) --------------------------------------------------
class ProcessType(_Labelled):
    MANAGEMENT = "MANAGEMENT"
    REALISATION = "REALISATION"
    SUPPORT = "SUPPORT"

    @staticmethod
    def _labels():
        return {"MANAGEMENT": "Processus de management", "REALISATION": "Processus de réalisation",
                "SUPPORT": "Processus support"}


class QmsProcessStatus(_Labelled):
    EN_PROJET = "EN_PROJET"
    ACTIF = "ACTIF"
    RETIRE = "RETIRE"

    @staticmethod
    def _labels():
        return {"EN_PROJET": "En cours de définition", "ACTIF": "En vigueur", "RETIRE": "Retiré"}


qms_process_indicators = db.Table(
    "qms_process_indicators",
    db.Column("process_id", db.Integer, db.ForeignKey("qms_processes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("indicator_id", db.Integer, db.ForeignKey("indicators.id", ondelete="CASCADE"), primary_key=True),
)
qms_process_risks = db.Table(
    "qms_process_risks",
    db.Column("process_id", db.Integer, db.ForeignKey("qms_processes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("risk_id", db.Integer, db.ForeignKey("risks.id", ondelete="CASCADE"), primary_key=True),
)
qms_process_documents = db.Table(
    "qms_process_documents",
    db.Column("process_id", db.Integer, db.ForeignKey("qms_processes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("document_id", db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
)
qms_process_links = db.Table(            # interactions : processus clients (en aval)
    "qms_process_links",
    db.Column("process_id", db.Integer, db.ForeignKey("qms_processes.id", ondelete="CASCADE"), primary_key=True),
    db.Column("next_id", db.Integer, db.ForeignKey("qms_processes.id", ondelete="CASCADE"), primary_key=True),
)


class QmsProcess(TenantMixin, db.Model):
    __tablename__ = "qms_processes"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_qms_processes_org_ref"),)

    REVIEW_MONTHS = 12

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # PRC-01
    name = db.Column(db.String(300), nullable=False)
    process_type = _enum(ProcessType, ProcessType.REALISATION, nullable=False, index=True)
    purpose = db.Column(db.Text, nullable=True)                                # finalité
    pilot_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True) # pilote du processus
    inputs = db.Column(db.Text, nullable=True)                                 # éléments d'entrée
    outputs = db.Column(db.Text, nullable=True)                                # éléments de sortie
    beneficiaries = db.Column(db.Text, nullable=True)                          # clients du processus
    resources = db.Column(db.Text, nullable=True)
    activities = db.Column(db.Text, nullable=True)                             # principales activités
    status = _enum(QmsProcessStatus, QmsProcessStatus.ACTIF, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    last_review = db.Column(db.Date, nullable=True)
    next_review = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pilot = db.relationship("User")
    indicators = db.relationship("Indicator", secondary=qms_process_indicators)
    risks = db.relationship("Risk", secondary=qms_process_risks)
    documents = db.relationship("Document", secondary=qms_process_documents)
    next_processes = db.relationship("QmsProcess", secondary=qms_process_links,
                                     primaryjoin=id == qms_process_links.c.process_id,
                                     secondaryjoin=id == qms_process_links.c.next_id)

    @property
    def title(self):
        return self.name

    @property
    def gaps(self):
        if self.status == QmsProcessStatus.RETIRE:
            return []
        out = []
        if not self.pilot_id:
            out.append("sans pilote")
        if not (self.purpose or "").strip():
            out.append("finalité non définie")
        if not (self.inputs or "").strip() or not (self.outputs or "").strip():
            out.append("entrées ou sorties non décrites")
        if not self.indicators:
            out.append("aucun indicateur")
        if not self.risks:
            out.append("risques et opportunités non identifiés")
        if self.next_review and self.next_review < date.today():
            out.append("revue à faire")
        return out


# --- Satisfaction client (9.1.2) ----------------------------------------------------------
class SurveyMethod(_Labelled):
    ENQUETE = "ENQUETE"
    ENTRETIEN = "ENTRETIEN"
    NPS = "NPS"
    RETOURS = "RETOURS"
    AUTRE = "AUTRE"

    @staticmethod
    def _labels():
        return {"ENQUETE": "Questionnaire de satisfaction", "ENTRETIEN": "Entretiens / revues clients",
                "NPS": "Recommandation (NPS)", "RETOURS": "Analyse des retours et avis", "AUTRE": "Autre"}


class CustomerSurvey(TenantMixin, db.Model):
    """Mesure de la satisfaction des clients : enquête, entretiens, NPS..."""

    __tablename__ = "customer_surveys"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_customer_surveys_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # SAT-2026-01
    title = db.Column(db.String(300), nullable=False)
    method = _enum(SurveyMethod, SurveyMethod.ENQUETE, nullable=False)
    conducted_on = db.Column(db.Date, nullable=True)
    scope = db.Column(db.Text, nullable=True)                                  # clients, produits, période couverts
    respondents = db.Column(db.Integer, nullable=True)
    score = db.Column(db.Float, nullable=True)                                 # résultat (sur 100)
    target = db.Column(db.Float, nullable=True)                                # objectif (sur 100)
    strengths = db.Column(db.Text, nullable=True)
    improvements = db.Column(db.Text, nullable=True)                           # axes d'amélioration
    actions = db.Column(db.Text, nullable=True)                                # suites décidées
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")

    @property
    def below_target(self):
        return self.score is not None and self.target is not None and self.score < self.target


class ComplaintStatus(_Labelled):
    RECUE = "RECUE"
    EN_COURS = "EN_COURS"
    CLOTUREE = "CLOTUREE"
    REJETEE = "REJETEE"

    @staticmethod
    def _labels():
        return {"RECUE": "Reçue", "EN_COURS": "En traitement", "CLOTUREE": "Clôturée (réponse apportée)",
                "REJETEE": "Non recevable (motivée)"}

    @property
    def closed(self):
        return self.value in ("CLOTUREE", "REJETEE")


class ComplaintSeverity(_Labelled):
    MINEURE = "MINEURE"
    MAJEURE = "MAJEURE"
    CRITIQUE = "CRITIQUE"

    @staticmethod
    def _labels():
        return {"MINEURE": "Mineure", "MAJEURE": "Majeure", "CRITIQUE": "Critique"}


class Complaint(TenantMixin, db.Model):
    """Réclamation client : réception, traitement, réponse, lien vers une non-conformité."""

    __tablename__ = "complaints"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_complaints_org_ref"),)

    RESPONSE_DAYS = 15

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(24), nullable=False, index=True)                 # REC-2026-0001
    customer = db.Column(db.String(200), nullable=False)
    received_on = db.Column(db.Date, nullable=False, default=date.today)
    channel = db.Column(db.String(120), nullable=True)
    product = db.Column(db.String(300), nullable=True)                         # produit ou service concerné
    description = db.Column(db.Text, nullable=True)
    severity = _enum(ComplaintSeverity, ComplaintSeverity.MINEURE, nullable=False)
    status = _enum(ComplaintStatus, ComplaintStatus.RECUE, nullable=False, index=True)
    due_on = db.Column(db.Date, nullable=True)
    analysis = db.Column(db.Text, nullable=True)                               # analyse, cause
    response = db.Column(db.Text, nullable=True)                               # réponse apportée au client
    justified = db.Column(db.Boolean, nullable=True)                           # réclamation fondée ?
    customer_satisfied = db.Column(db.Boolean, nullable=True)                  # satisfait de la réponse ?
    nonconformity_id = db.Column(db.Integer, db.ForeignKey("nonconformities.id", ondelete="SET NULL"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    closed_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User")
    nonconformity = db.relationship("NonConformity")

    @property
    def title(self):
        return f"{self.customer} - {self.product or 'réclamation'}"

    @property
    def overdue(self):
        return not self.status.closed and self.due_on is not None and self.due_on < date.today()

    def default_due(self, d):
        return d + timedelta(days=self.RESPONSE_DAYS)
