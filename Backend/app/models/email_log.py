from datetime import datetime, timezone
from typing import Any
from app.extensions import db


class EmailNotificationLog(db.Model):
    """Immutable audit and delivery log for all statutory email notifications."""

    __tablename__ = "email_notification_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    recipient_email = db.Column(db.String(255), nullable=False, index=True)
    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject = db.Column(db.String(255), nullable=False)
    email_type = db.Column(db.String(64), nullable=False, index=True)
    fdr_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reminder_interval_days = db.Column(db.Integer, nullable=True, index=True)
    status = db.Column(db.String(32), nullable=False, default="SENT", index=True)  # SENT, FAILED, SUPPRESSED
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    institution = db.relationship("Institution", foreign_keys=[institution_id])
    fdr = db.relationship("FDRRecord", foreign_keys=[fdr_id])
    request = db.relationship("FDRRequest", foreign_keys=[request_id])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipient_email": self.recipient_email,
            "institution_id": self.institution_id,
            "subject": self.subject,
            "email_type": self.email_type,
            "fdr_id": self.fdr_id,
            "request_id": self.request_id,
            "reminder_interval_days": self.reminder_interval_days,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<EmailNotificationLog id={self.id} to='{self.recipient_email}' type='{self.email_type}' status='{self.status}'>"
