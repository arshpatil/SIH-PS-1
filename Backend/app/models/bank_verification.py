from datetime import datetime, timezone
import json
from typing import Any, Optional
from app.extensions import db


class BankVerificationLog(db.Model):
    """
    Audit log of all bank verification queries dispatched to a participating bank
    or prototype mock provider. Captures field matches, discrepancies, and provider mode.
    """

    __tablename__ = "bank_verification_logs"

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
    requested_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider_name = db.Column(db.String(64), nullable=False)
    provider_mode = db.Column(db.String(16), nullable=False, default="DEMO")
    verification_status = db.Column(db.String(32), nullable=False, index=True)
    bank_reference = db.Column(db.String(128), nullable=True)
    matched_fields_json = db.Column(db.Text, nullable=True)
    mismatched_fields_json = db.Column(db.Text, nullable=True)
    raw_details_json = db.Column(db.Text, nullable=True)
    message = db.Column(db.Text, nullable=True)
    disclaimer = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    fdr = db.relationship("FDRRecord", back_populates="bank_verifications")
    institution = db.relationship("Institution", back_populates="bank_verifications")
    requester = db.relationship("User", foreign_keys=[requested_by])

    def to_dict(self) -> dict[str, Any]:
        matched = {}
        mismatched = {}
        raw = None
        if self.matched_fields_json:
            try:
                matched = json.loads(self.matched_fields_json)
            except Exception:
                matched = {}
        if self.mismatched_fields_json:
            try:
                mismatched = json.loads(self.mismatched_fields_json)
            except Exception:
                mismatched = {}
        if self.raw_details_json:
            try:
                raw = json.loads(self.raw_details_json)
            except Exception:
                raw = None

        return {
            "id": self.id,
            "fdr_id": self.fdr_id,
            "institution_id": self.institution_id,
            "requested_by": self.requested_by,
            "requester_name": self.requester.full_name if self.requester else None,
            "provider_name": self.provider_name,
            "provider_mode": self.provider_mode,
            "is_demo": self.provider_mode == "DEMO",
            "is_mock": self.provider_mode == "DEMO",
            "verification_status": self.verification_status,
            "bank_reference": self.bank_reference,
            "matched_fields": matched,
            "mismatched_fields": mismatched,
            "bank_details": raw,
            "message": self.message,
            "disclaimer": self.disclaimer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
