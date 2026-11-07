from datetime import datetime

from app.extensions import db
from app.models.organization import TenantMixin
from app.models.enums import DocStatus, DocType
from app.models.control import evidence_controls


class Document(TenantMixin, db.Model):
    """Document du SMSI (politique, procédure, enregistrement) - clause 7.5.
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
