from datetime import datetime, timezone
from typing import Any
from app.extensions import db


class FDRRenewalHistory(db.Model):
    """Immutable audit trail of verified renewals for an FDR record."""

    __tablename__ = "fdr_renewal_history"
    __table_args__ = (
        db.Index("idx_renewal_fdr_id", "fdr_id"),
        db.Index("idx_renewal_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fdr_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Previous FDR parameters before renewal verification
    previous_fdr_number = db.Column(db.String(100), nullable=False)
    previous_issue_date = db.Column(db.Date, nullable=False)
    previous_maturity_date = db.Column(db.Date, nullable=False)
    previous_amount = db.Column(db.Numeric(precision=15, scale=2), nullable=False)

    # Verified renewed FDR parameters
    new_fdr_number = db.Column(db.String(100), nullable=False)
    new_issue_date = db.Column(db.Date, nullable=False)
    new_maturity_date = db.Column(db.Date, nullable=False)
    new_amount = db.Column(db.Numeric(precision=15, scale=2), nullable=False)

    renewal_document = db.Column(db.String(255), nullable=True)
    verified_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    fdr = db.relationship("FDRRecord", back_populates="renewal_history")
    request = db.relationship("FDRRequest", backref=db.backref("renewal_records", lazy="dynamic"))
    verifier = db.relationship("User", foreign_keys=[verified_by])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fdr_id": self.fdr_id,
            "request_id": self.request_id,
            "previous_fdr_number": self.previous_fdr_number,
            "previous_issue_date": self.previous_issue_date.isoformat() if self.previous_issue_date else None,
            "previous_maturity_date": self.previous_maturity_date.isoformat() if self.previous_maturity_date else None,
            "previous_amount": float(self.previous_amount) if self.previous_amount is not None else 0.0,
            "new_fdr_number": self.new_fdr_number,
            "new_issue_date": self.new_issue_date.isoformat() if self.new_issue_date else None,
            "new_maturity_date": self.new_maturity_date.isoformat() if self.new_maturity_date else None,
            "new_amount": float(self.new_amount) if self.new_amount is not None else 0.0,
            "renewal_document": self.renewal_document,
            "verified_by": self.verified_by,
            "verifier_name": self.verifier.full_name if self.verifier else None,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<FDRRenewalHistory id={self.id} fdr_id={self.fdr_id} old_mat={self.previous_maturity_date} new_mat={self.new_maturity_date}>"
