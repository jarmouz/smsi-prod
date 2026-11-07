from datetime import datetime, timedelta

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import DocStatus, DocType
from app.models.control import evidence_controls


class Document(TenantMixin, db.Model):
    """Document du système de management (politique, procédure, enregistrement) - clause 7.5.
    Versionné, avec cycle d'approbation et date de prochaine revue."""

    __tablename__ = "documents"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_documents_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(32), nullable=False, index=True)  # DOC-001
    title = db.Column(db.String(300), nullable=False)
    doc_type = db.Column(db.Enum(DocType, native_enum=False), nullable=False, default=DocType.PROCEDURE)
    version = db.Column(db.String(16), default="1.0", nullable=False)
    status = db.Column(db.Enum(DocStatus, native_enum=False),
                       default=DocStatus.BROUILLON, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    location = db.Column(db.String(500), nullable=True)   # lien / emplacement
    approved_at = db.Column(db.Date, nullable=True)
    next_review_at = db.Column(db.Date, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Circuit d'approbation (7.5.2 / 7.5.3)
    change_summary = db.Column(db.Text, nullable=True)         # modifications de la version en cours
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Lecture et acceptation par les personnes (3.10) : 5.2 et 7.3 des normes, 27001 A.5.1 et A.6.3.
    # ack_roles : rôles concernés séparés par des virgules (vide = tous les comptes actifs).
    ack_required = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    ack_roles = db.Column(db.String(80), nullable=True)
    ack_days = db.Column(db.Integer, nullable=False, default=30, server_default="30")   # délai après approbation
    # Page de confiance (3.11) : NULL = privé, PUBLIC = téléchargeable, DEMANDE = sur demande accordée
    trust_visibility = db.Column(db.String(12), nullable=True)

    owner = db.relationship("User", foreign_keys=[owner_id])
    submitted_by = db.relationship("User", foreign_keys=[submitted_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    versions = db.relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan",
                               order_by="DocumentVersion.approved_at.desc()")

    @property
    def review_overdue(self):
        return bool(self.next_review_at and self.next_review_at < datetime.utcnow().date()
                    and self.status != DocStatus.OBSOLETE)

    @property
    def review_soon(self):
        if not self.next_review_at or self.status == DocStatus.OBSOLETE:
            return False
        delta = (self.next_review_at - datetime.utcnow().date()).days
        return 0 <= delta <= 30

    # --- lecture et acceptation ---------------------------------------------------
    @property
    def ack_role_list(self):
        return [r for r in (self.ack_roles or "").split(",") if r]

    @property
    def ack_active(self):
        """Acceptation demandée sur la version en vigueur (document approuvé)."""
        return bool(self.ack_required and self.status == DocStatus.APPROUVE)

    @property
    def ack_due(self):
        return self.approved_at + timedelta(days=self.ack_days or 30) if self.approved_at else None

    def ack_audience(self):
        """Comptes actifs concernés (hors comptes en lecture seule : visiteurs, auditeurs externes)."""
        from app.models.user import User
        roles = self.ack_role_list
        return [u for u in User.query.filter_by(is_active_flag=True).order_by(User.name).all()
                if not u.is_readonly and (not roles or u.role.value in roles)]

    def current_acceptances(self):
        return PolicyAcceptance.query.filter_by(document_id=self.id, version=self.version).all()

    def ack_status(self):
        """{"audience", "accepted" (acceptations par user_id), "pending", "rate", "overdue"}."""
        audience = self.ack_audience()
        acc = {a.user_id: a for a in self.current_acceptances()}
        pending = [u for u in audience if u.id not in acc]
        done = [u for u in audience if u.id in acc]
        due = self.ack_due
        return {"audience": audience, "accepted": acc, "done": done, "pending": pending,
                "rate": round(100 * len(done) / len(audience)) if audience else 100,
                "overdue": bool(pending and due and due < datetime.utcnow().date())}

    def __repr__(self):
        return f"<Document {self.ref} v{self.version}>"


class DocumentVersion(TenantMixin, db.Model):
    """Version approuvée d'un document : historique non modifiable des versions."""

    __tablename__ = "document_versions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.String(16), nullable=False)
    change_summary = db.Column(db.Text, nullable=True)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    retired_at = db.Column(db.DateTime, nullable=True)        # remplacée ou rendue obsolète

    document = db.relationship("Document", back_populates="versions")
    submitted_by = db.relationship("User", foreign_keys=[submitted_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self):
        return f"<DocumentVersion {self.document_id} v{self.version}>"


class Evidence(TenantMixin, db.Model):
    """Preuve / élément d'auditabilité, rattaché à une ou plusieurs mesures.
    C'est ce qu'un auditeur demande pour vérifier la mise en œuvre."""

    __tablename__ = "evidence"
    __table_args__ = (db.UniqueConstraint("organization_id", "ref", name="uq_evidence_org_ref"),)

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(32), nullable=False, index=True)  # PRV-0001
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    collected_at = db.Column(db.Date, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    location = db.Column(db.String(500), nullable=True)   # lien / emplacement du fichier
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    owner = db.relationship("User")
    controls = db.relationship("Control", secondary=evidence_controls, back_populates="evidences")

    def __repr__(self):
        return f"<Evidence {self.ref}>"


class PolicyAcceptance(TenantMixin, db.Model):
    """Lecture et acceptation d'une version d'un document par une personne (3.10).
    Une nouvelle version approuvée demande une nouvelle acceptation."""

    __tablename__ = "policy_acceptances"
    __table_args__ = (db.UniqueConstraint("document_id", "user_id", "version", name="uq_policy_acceptances"),)

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = db.Column(db.String(16), nullable=False)
    accepted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip = db.Column(db.String(64), nullable=True)

    document = db.relationship("Document")
    user = db.relationship("User")

