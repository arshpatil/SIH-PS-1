from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import validates
from app.extensions import db
from app.models.enums import DocumentProcessingStatus


class Document(db.Model):
    """Uploaded supporting document (e.g. scanned FDR receipt, bank lien letter, verification certificate)."""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fdr_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True, index=True)
    file_type = db.Column(db.String(50), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    processing_status = db.Column(
        db.String(32),
        nullable=False,
        default=DocumentProcessingStatus.PENDING.value,
        index=True,
    )
    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    fdr = db.relationship("FDRRecord", back_populates="documents")
    uploader = db.relationship(
        "User",
        foreign_keys=[uploaded_by],
        back_populates="uploaded_documents",
    )

    @validates("file_size")
    def validate_file_size(self, key, value):
        if value is None or int(value) <= 0:
            raise ValueError("Document file size must be a positive integer.")
        return int(value)

    @validates("processing_status")
    def validate_processing_status(self, key, status):
        valid_statuses = DocumentProcessingStatus.values()
        val = (
            status.value
            if isinstance(status, DocumentProcessingStatus)
            else str(status)
        )
        if val not in valid_statuses:
            raise ValueError(
                f"Invalid processing status '{val}'. Valid options: {valid_statuses}"
            )
        return val

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fdr_id": self.fdr_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "processing_status": self.processing_status,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename='{self.original_filename}' status='{self.processing_status}'>"
