from datetime import date, datetime, timezone
from typing import Any
from decimal import Decimal
from sqlalchemy.orm import validates
from app.extensions import db
from app.models.enums import ScrutinyStatus, ValidityStatus


class FDRRecord(db.Model):
    """Fixed Deposit Receipt (FDR) record submitted by an institution."""

    __tablename__ = "fdr_records"
    __table_args__ = (
        db.UniqueConstraint(
            "institution_id", "fdr_number", name="uq_institution_fdr_number"
        ),
        db.Index("idx_fdr_maturity_date", "maturity_date"),
        db.Index("idx_fdr_scrutiny_status", "scrutiny_status"),
        db.Index("idx_fdr_validity_status", "validity_status"),
        db.Index("idx_fdr_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fdr_number = db.Column(db.String(100), nullable=False, index=True)
    bank_name = db.Column(db.String(150), nullable=False)
    branch_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Numeric(precision=15, scale=2), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    maturity_date = db.Column(db.Date, nullable=False)
    scrutiny_status = db.Column(
        db.String(32),
        nullable=False,
        default=ScrutinyStatus.DRAFT.value,
    )
    validity_status = db.Column(
        db.String(32),
        nullable=False,
        default=ValidityStatus.ACTIVE.value,
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
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
    institution = db.relationship("Institution", back_populates="fdrs")
    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_fdrs",
    )
    documents = db.relationship(
        "Document",
        back_populates="fdr",
        cascade="all, delete-orphan",
    )
    workflow_history = db.relationship(
        "FDRWorkflowHistory",
        back_populates="fdr",
        cascade="all, delete-orphan",
        order_by="FDRWorkflowHistory.created_at.asc()",
    )
    renewal_history = db.relationship(
        "FDRRenewalHistory",
        back_populates="fdr",
        cascade="all, delete-orphan",
        order_by="FDRRenewalHistory.created_at.desc()",
    )
    bank_verifications = db.relationship(
        "BankVerificationLog",
        back_populates="fdr",
        cascade="all, delete-orphan",
        order_by="BankVerificationLog.created_at.desc()",
    )

    @validates("amount")
    def validate_amount(self, key, value):
        if value is None:
            raise ValueError("FDR amount is required.")
        decimal_val = Decimal(str(value))
        if decimal_val <= Decimal("0"):
            raise ValueError("FDR amount must be a positive value.")
        return decimal_val

    @validates("issue_date")
    def validate_issue_date(self, key, value):
        if value is None:
            raise ValueError("Issue date is required.")
        if not isinstance(value, (date, datetime)):
            raise ValueError("Issue date must be a valid date object.")
        issue_d = value.date() if isinstance(value, datetime) else value
        if self.maturity_date:
            mat_d = (
                self.maturity_date.date()
                if isinstance(self.maturity_date, datetime)
                else self.maturity_date
            )
            if mat_d < issue_d:
                raise ValueError("Maturity date cannot be earlier than issue date.")
        return issue_d

    @validates("maturity_date")
    def validate_maturity_date(self, key, value):
        if value is None:
            raise ValueError("Maturity date is required.")
        if not isinstance(value, (date, datetime)):
            raise ValueError("Maturity date must be a valid date object.")
        mat_d = value.date() if isinstance(value, datetime) else value
        if self.issue_date:
            iss_d = (
                self.issue_date.date()
                if isinstance(self.issue_date, datetime)
                else self.issue_date
            )
            if mat_d < iss_d:
                raise ValueError("Maturity date cannot be earlier than issue date.")
        return mat_d

    @validates("scrutiny_status")
    def validate_scrutiny_status(self, key, status):
        valid_statuses = ScrutinyStatus.values()
        val = status.value if isinstance(status, ScrutinyStatus) else str(status)
        if val not in valid_statuses:
            raise ValueError(
                f"Invalid scrutiny status '{val}'. Valid options: {valid_statuses}"
            )
        return val

    @validates("validity_status")
    def validate_validity_status(self, key, status):
        valid_statuses = ValidityStatus.values()
        val = status.value if isinstance(status, ValidityStatus) else str(status)
        if val not in valid_statuses:
            raise ValueError(
                f"Invalid validity status '{val}'. Valid options: {valid_statuses}"
            )
        return val

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        days_rem = None
        if self.maturity_date:
            mat_d = self.maturity_date.date() if isinstance(self.maturity_date, datetime) else self.maturity_date
            days_rem = (mat_d - datetime.now(timezone.utc).date()).days

        latest_req = None
        try:
            req_obj = self.requests.order_by(db.text("id DESC")).first()
            if req_obj:
                latest_req = req_obj.to_dict()
        except Exception:
            pass

        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "institution_name": self.institution.name if self.institution else None,
            "fdr_number": self.fdr_number,
            "fdrNumber": self.fdr_number,
            "bank_name": self.bank_name,
            "bankName": self.bank_name,
            "branch_name": self.branch_name,
            "branchName": self.branch_name,
            "amount": f"{self.amount:.2f}" if self.amount is not None else None,
            "depositAmount": float(self.amount) if self.amount is not None else 0.0,
            "deposit_amount": float(self.amount) if self.amount is not None else 0.0,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "issueDate": self.issue_date.isoformat() if self.issue_date else None,
            "maturity_date": (
                self.maturity_date.isoformat() if self.maturity_date else None
            ),
            "maturityDate": (
                self.maturity_date.isoformat() if self.maturity_date else None
            ),
            "scrutiny_status": self.scrutiny_status,
            "validity_status": self.validity_status,
            "daysRemaining": days_rem,
            "days_remaining": days_rem,
            "created_by": self.created_by,
            "creator_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "latest_request": latest_req,
            "latestRequest": latest_req,
            "renewal_history": [r.to_dict() for r in self.renewal_history] if self.renewal_history else [],
            "latest_bank_verification": self.bank_verifications[0].to_dict() if self.bank_verifications else None,
            "bank_verification_history": [v.to_dict() for v in self.bank_verifications[:5]] if self.bank_verifications else [],
        }

    def __repr__(self) -> str:
        return f"<FDRRecord id={self.id} number='{self.fdr_number}' amount={self.amount}>"
