from datetime import datetime, timezone
from app.extensions import db


class FDRRequest(db.Model):
    """Statutory Renewal and Lien Release petitions submitted by institutions."""

    __tablename__ = "fdr_requests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fdr_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_type = db.Column(
        db.String(32), nullable=False, index=True
    )  # "Renewal", "Release"
    status = db.Column(
        db.String(32), nullable=False, default="Submitted", index=True
    )  # "Submitted", "Under Review", "Approved", "Rejected"
    stage = db.Column(db.String(64), nullable=False, default="Desk Review")
    reason = db.Column(db.Text, nullable=False)
    supporting_document = db.Column(db.String(255), nullable=True)
    document_size = db.Column(db.Integer, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    fdr = db.relationship(
        "FDRRecord",
        backref=db.backref("requests", lazy="dynamic", cascade="all, delete-orphan"),
    )
    institution = db.relationship(
        "Institution",
        backref=db.backref("fdr_requests", lazy="dynamic"),
    )
    creator = db.relationship(
        "User",
        backref=db.backref("fdr_requests", lazy="dynamic"),
    )

    def to_dict(self) -> dict:
        return {
            "id": f"REQ-{self.id:04d}",
            "raw_id": self.id,
            "fdrId": self.fdr_id,
            "fdrNumber": self.fdr.fdr_number if self.fdr else "",
            "bankName": self.fdr.bank_name if self.fdr else "",
            "depositAmount": float(self.fdr.amount) if self.fdr and self.fdr.amount else 0.0,
            "institutionId": self.institution_id,
            "institutionName": self.institution.name if self.institution else "",
            "requestType": self.request_type,
            "status": self.status,
            "stage": self.stage,
            "reason": self.reason,
            "supportingDocument": self.supporting_document,
            "documentSize": self.document_size,
            "remarks": self.remarks,
            "submissionDate": self.created_at.isoformat() if self.created_at else None,
            "lastUpdated": self.updated_at.isoformat() if self.updated_at else None,
            "createdBy": self.created_by,
        }

    def __repr__(self) -> str:
        return f"<FDRRequest id={self.id} fdr_id={self.fdr_id} type='{self.request_type}' status='{self.status}'>"
