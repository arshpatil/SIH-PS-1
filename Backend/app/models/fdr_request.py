from datetime import datetime, timezone
from typing import Any
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
    assigned_to = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Renewed FDR details submitted by institution after petition approval
    renewal_fdr_number = db.Column(db.String(100), nullable=True)
    renewal_issue_date = db.Column(db.Date, nullable=True)
    renewal_maturity_date = db.Column(db.Date, nullable=True)
    renewal_amount = db.Column(db.Numeric(precision=15, scale=2), nullable=True)
    renewal_document = db.Column(db.String(255), nullable=True)
    renewal_document_size = db.Column(db.Integer, nullable=True)
    renewal_remarks = db.Column(db.Text, nullable=True)
    renewal_submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    renewal_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    renewal_verified_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    renewal_is_synthetic = db.Column(db.Boolean, default=False, nullable=True)
    renewal_ocr_data = db.Column(db.Text, nullable=True)

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
        foreign_keys=[created_by],
        backref=db.backref("fdr_requests", lazy="dynamic"),
    )
    assigned_officer = db.relationship(
        "User",
        foreign_keys=[assigned_to],
        backref=db.backref("assigned_petitions", lazy="dynamic"),
    )
    renewal_verifier = db.relationship(
        "User",
        foreign_keys=[renewal_verified_by],
    )
    assignment_history = db.relationship(
        "PetitionAssignmentHistory",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="PetitionAssignmentHistory.created_at.desc()",
    )

    @property
    def maturity_date(self):
        return self.fdr.maturity_date if self.fdr else None

    @property
    def days_remaining(self) -> int | None:
        if not self.fdr or not self.fdr.maturity_date:
            return None
        mat_d = self.fdr.maturity_date.date() if isinstance(self.fdr.maturity_date, datetime) else self.fdr.maturity_date
        return (mat_d - datetime.now(timezone.utc).date()).days

    @property
    def is_overdue(self) -> bool:
        if not self.created_at:
            return False
        created_dt = self.created_at if self.created_at.tzinfo else self.created_at.replace(tzinfo=timezone.utc)
        pending_days = (datetime.now(timezone.utc) - created_dt).days
        return pending_days > 14 and self.status in [
            "Submitted",
            "Under Review",
            "Documents Required",
            "Resubmitted / Awaiting Review",
        ]

    @property
    def priority(self) -> str:
        days = self.days_remaining
        if self.status in ["Approved", "Rejected", "Closed"]:
            return "LOW"

        # 1. CRITICAL: FDR maturity within 7 days (or already matured)
        if days is not None and days <= 7:
            return "CRITICAL"

        # 2. HIGH: FDR maturity within 15 days or petition overdue (>14 days)
        if (days is not None and days <= 15) or self.is_overdue:
            return "HIGH"

        # 3. MEDIUM: Normal pending petitions (e.g. maturity within 60 days, or standard pending)
        if days is not None and days <= 60:
            return "MEDIUM"

        # 4. LOW: Recently submitted petitions with sufficient time remaining
        return "LOW"

    @property
    def priority_reason(self) -> str:
        days = self.days_remaining
        if self.status in ["Approved", "Rejected", "Closed"]:
            return f"Petition review completed and finalized ({self.status})."

        if days is not None and days < 0:
            return f"CRITICAL: FDR matured {abs(days)} day(s) ago. Immediate regulatory intervention mandatory."
        if days is not None and days <= 7:
            return f"CRITICAL: FDR matures in {days} day(s) (within 7-day critical window). Urgent scrutiny required."

        if self.is_overdue:
            created_dt = self.created_at if self.created_at.tzinfo else self.created_at.replace(tzinfo=timezone.utc)
            pending_days = (datetime.now(timezone.utc) - created_dt).days
            return f"HIGH: Petition pending review for {pending_days} days (exceeds 14-day statutory turnaround limit)."
        if days is not None and days <= 15:
            return f"HIGH: FDR matures in {days} day(s) (within 15-day expedited review threshold)."

        if days is not None and days <= 60:
            return f"MEDIUM: Normal desk scrutiny queue ({days} day(s) remaining before FDR maturity)."

        return f"LOW: Recently submitted petition with adequate regulatory time remaining ({days if days is not None else 'N/A'} days)."

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        is_overdue = self.is_overdue
        priority_val = self.priority
        priority_reason_val = self.priority_reason

        return {
            "id": f"REQ-{self.id:04d}",
            "raw_id": self.id,
            "fdrId": self.fdr_id,
            "fdr_id": self.fdr_id,
            "fdrNumber": self.fdr.fdr_number if self.fdr else "",
            "fdr_number": self.fdr.fdr_number if self.fdr else "",
            "bankName": self.fdr.bank_name if self.fdr else "",
            "bank_name": self.fdr.bank_name if self.fdr else "",
            "depositAmount": float(self.fdr.amount) if self.fdr and self.fdr.amount else 0.0,
            "deposit_amount": float(self.fdr.amount) if self.fdr and self.fdr.amount else 0.0,
            "institutionId": self.institution_id,
            "institution_id": self.institution_id,
            "institutionName": self.institution.name if self.institution else "",
            "institution_name": self.institution.name if self.institution else "",
            "institutionCode": self.institution.institution_code if self.institution else "",
            "institution_code": self.institution.institution_code if self.institution else "",
            "requestType": self.request_type,
            "request_type": self.request_type,
            "status": self.status,
            "stage": self.stage,
            "reason": self.reason,
            "supportingDocument": self.supporting_document,
            "supporting_document": self.supporting_document,
            "documentSize": self.document_size,
            "document_size": self.document_size,
            "remarks": self.remarks,
            "submissionDate": self.created_at.isoformat() if self.created_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "lastUpdated": self.updated_at.isoformat() if self.updated_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "createdBy": self.created_by,
            "created_by": self.created_by,
            "assignedTo": self.assigned_to,
            "assigned_to": self.assigned_to,
            "assignedOfficerName": self.assigned_officer.full_name if self.assigned_officer else None,
            "assigned_officer_name": self.assigned_officer.full_name if self.assigned_officer else None,
            "maturityDate": self.fdr.maturity_date.isoformat() if self.fdr and self.fdr.maturity_date else None,
            "maturity_date": self.fdr.maturity_date.isoformat() if self.fdr and self.fdr.maturity_date else None,
            "daysRemaining": self.days_remaining,
            "days_remaining": self.days_remaining,
            "priority": priority_val,
            "priority_reason": priority_reason_val,
            "priorityReason": priority_reason_val,
            "is_overdue": is_overdue,
            "isOverdue": is_overdue,
            "renewalFdrNumber": self.renewal_fdr_number,
            "renewal_fdr_number": self.renewal_fdr_number,
            "renewalIssueDate": self.renewal_issue_date.isoformat() if self.renewal_issue_date else None,
            "renewal_issue_date": self.renewal_issue_date.isoformat() if self.renewal_issue_date else None,
            "renewalMaturityDate": self.renewal_maturity_date.isoformat() if self.renewal_maturity_date else None,
            "renewal_maturity_date": self.renewal_maturity_date.isoformat() if self.renewal_maturity_date else None,
            "renewalAmount": float(self.renewal_amount) if self.renewal_amount is not None else None,
            "renewal_amount": float(self.renewal_amount) if self.renewal_amount is not None else None,
            "renewalDocument": self.renewal_document,
            "renewal_document": self.renewal_document,
            "renewalDocumentSize": self.renewal_document_size,
            "renewal_document_size": self.renewal_document_size,
            "renewalRemarks": self.renewal_remarks,
            "renewal_remarks": self.renewal_remarks,
            "renewalSubmittedAt": self.renewal_submitted_at.isoformat() if self.renewal_submitted_at else None,
            "renewal_submitted_at": self.renewal_submitted_at.isoformat() if self.renewal_submitted_at else None,
            "renewalVerifiedAt": self.renewal_verified_at.isoformat() if self.renewal_verified_at else None,
            "renewal_verified_at": self.renewal_verified_at.isoformat() if self.renewal_verified_at else None,
            "renewalVerifiedBy": self.renewal_verified_by,
            "renewal_verified_by": self.renewal_verified_by,
            "renewalVerifierName": self.renewal_verifier.full_name if self.renewal_verifier else None,
            "renewal_verifier_name": self.renewal_verifier.full_name if self.renewal_verifier else None,
            "renewalIsSynthetic": bool(self.renewal_is_synthetic),
            "renewal_is_synthetic": bool(self.renewal_is_synthetic),
            "renewalOcrData": self.renewal_ocr_data,
            "renewal_ocr_data": self.renewal_ocr_data,
        }

    def __repr__(self) -> str:
        return f"<FDRRequest id={self.id} fdr_id={self.fdr_id} type='{self.request_type}' status='{self.status}'>"


class PetitionAssignmentHistory(db.Model):
    """Immutable audit trail for petition scrutiny officer assignments and reassignments."""

    __tablename__ = "petition_assignment_histories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    request_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_officer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    new_officer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignment_type = db.Column(
        db.String(32), nullable=False, default="AUTO_ASSIGNMENT", index=True
    )  # "AUTO_ASSIGNMENT", "MANUAL_ASSIGNMENT", "REASSIGNMENT", "SELF_CLAIM"
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    request = db.relationship("FDRRequest", back_populates="assignment_history")
    previous_officer = db.relationship("User", foreign_keys=[previous_officer_id])
    new_officer = db.relationship("User", foreign_keys=[new_officer_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "requestId": f"REQ-{self.request_id:04d}",
            "request_id": self.request_id,
            "previousOfficerId": self.previous_officer_id,
            "previous_officer_id": self.previous_officer_id,
            "previousOfficerName": self.previous_officer.full_name if self.previous_officer else None,
            "previous_officer_name": self.previous_officer.full_name if self.previous_officer else None,
            "newOfficerId": self.new_officer_id,
            "new_officer_id": self.new_officer_id,
            "newOfficerName": self.new_officer.full_name if self.new_officer else None,
            "new_officer_name": self.new_officer.full_name if self.new_officer else None,
            "assignedById": self.assigned_by_id,
            "assigned_by_id": self.assigned_by_id,
            "assignedByName": self.assigned_by.full_name if self.assigned_by else "System Auto-Assignment",
            "assigned_by_name": self.assigned_by.full_name if self.assigned_by else "System Auto-Assignment",
            "assignmentType": self.assignment_type,
            "assignment_type": self.assignment_type,
            "reason": self.reason,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<PetitionAssignmentHistory id={self.id} req={self.request_id} prev={self.previous_officer_id} new={self.new_officer_id}>"

