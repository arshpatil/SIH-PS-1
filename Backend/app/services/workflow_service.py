from datetime import datetime, timezone
import json
from flask import current_app

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import NotificationType, ScrutinyStatus, UserRole
from app.models.fdr import FDRRecord
from app.models.notification import Notification
from app.models.user import User
from app.models.workflow_history import FDRWorkflowHistory
from app.services.fdr_service import (
    FDRNotFoundError,
    FDRPermissionError,
    FDRServiceError,
    FDRValidationError,
    get_authorized_fdr,
)


class WorkflowServiceError(FDRServiceError):
    """Base exception for scrutiny workflow transition errors."""

    pass


class WorkflowTransitionError(WorkflowServiceError):
    """Exception raised when an invalid or disallowed scrutiny status transition is attempted."""

    def __init__(
        self,
        message: str,
        code: str = "INVALID_TRANSITION",
        status_code: int = 400,
    ):
        super().__init__(message=message, code=code, status_code=status_code)


class WorkflowPermissionError(FDRPermissionError, WorkflowServiceError):
    """Exception raised when a user role is not authorized for the requested workflow transition."""

    def __init__(
        self,
        message: str = "You do not have permission to execute this workflow transition.",
        code: str = "WORKFLOW_PERMISSION_DENIED",
    ):
        super().__init__(message=message, code=code)


class WorkflowValidationError(FDRValidationError, WorkflowServiceError):
    """Exception raised when transition payload validation fails (e.g., missing remarks)."""

    def __init__(self, errors: dict):
        super().__init__(errors=errors)
        self.message = "Workflow decision validation failed."


# Maximum permitted character length for decision remarks
MAX_REMARKS_LENGTH = 2000

# Canonical allowed scrutiny workflow transitions and their role permissions
ALLOWED_SCRUTINY_TRANSITIONS: dict[tuple[str, str], dict] = {
    (ScrutinyStatus.DRAFT.value, ScrutinyStatus.SUBMITTED.value): {
        "roles": {"INSTITUTION", "ADMIN"},
        "requires_remarks": False,
        "description": "Institution submits draft FDR for AICTE verification.",
    },
    (ScrutinyStatus.RETURNED.value, ScrutinyStatus.SUBMITTED.value): {
        "roles": {"INSTITUTION", "ADMIN"},
        "requires_remarks": False,
        "description": "Institution resubmits rectified FDR for verification.",
    },
    (ScrutinyStatus.SUBMITTED.value, ScrutinyStatus.PENDING_VERIFICATION.value): {
        "roles": {"AICTE_OFFICER", "ADMIN"},
        "requires_remarks": False,
        "description": "Officer takes up submitted FDR for active verification.",
    },
    (ScrutinyStatus.PENDING_VERIFICATION.value, ScrutinyStatus.VERIFIED.value): {
        "roles": {"AICTE_OFFICER", "ADMIN"},
        "requires_remarks": False,
        "description": "Officer approves and marks the FDR deposit as verified.",
    },
    (ScrutinyStatus.PENDING_VERIFICATION.value, ScrutinyStatus.RETURNED.value): {
        "roles": {"AICTE_OFFICER", "ADMIN"},
        "requires_remarks": True,
        "description": "Officer returns FDR to institution for correction/rectification.",
    },
    (ScrutinyStatus.PENDING_VERIFICATION.value, ScrutinyStatus.REJECTED.value): {
        "roles": {"AICTE_OFFICER", "ADMIN"},
        "requires_remarks": True,
        "description": "Officer rejects the FDR submission.",
    },
}

TERMINAL_STATUSES = {
    ScrutinyStatus.VERIFIED.value,
    ScrutinyStatus.REJECTED.value,
}


def validate_scrutiny_transition(
    current_status: str | ScrutinyStatus,
    target_status: str | ScrutinyStatus,
    user_role: str | UserRole,
    remarks: str | None = None,
) -> dict:
    """
    Centralized validator for FDR scrutiny workflow transitions.

    Validates:
    - Status enum validity.
    - Terminal state restrictions.
    - Transition matrix allowance.
    - Role permissions.
    - Mandatory non-empty remarks for RETURNED and REJECTED decisions.
    - Remarks character limit.

    Returns sanitized transition parameters on success.
    Raises WorkflowTransitionError, WorkflowPermissionError, or WorkflowValidationError on failure.
    """
    # 1. Normalize status values
    curr_val = (
        current_status.value
        if isinstance(current_status, ScrutinyStatus)
        else str(current_status).strip().upper()
    )
    targ_val = (
        target_status.value
        if isinstance(target_status, ScrutinyStatus)
        else str(target_status).strip().upper()
    )

    if curr_val not in ScrutinyStatus.values():
        raise WorkflowValidationError(
            {"current_status": f"Invalid current status '{curr_val}'."}
        )
    if targ_val not in ScrutinyStatus.values():
        raise WorkflowValidationError(
            {"target_status": f"Invalid target status '{targ_val}'."}
        )

    # 2. Check if current status is terminal
    if curr_val in TERMINAL_STATUSES:
        raise WorkflowTransitionError(
            f"Cannot transition from terminal scrutiny status '{curr_val}'. "
            "Verified or rejected records cannot undergo further workflow transitions.",
            code="TERMINAL_STATUS_LOCKED",
        )

    # 3. Disallow transition to self
    if curr_val == targ_val:
        raise WorkflowTransitionError(
            f"Record is already in scrutiny status '{curr_val}'.",
            code="NO_OP_TRANSITION",
        )

    # 4. Check transition matrix
    transition_key = (curr_val, targ_val)
    rule = ALLOWED_SCRUTINY_TRANSITIONS.get(transition_key)
    if not rule:
        raise WorkflowTransitionError(
            f"Transition from '{curr_val}' to '{targ_val}' is not permitted. "
            f"Allowed transitions from '{curr_val}': "
            f"{[dst for (src, dst) in ALLOWED_SCRUTINY_TRANSITIONS.keys() if src == curr_val]}.",
            code="INVALID_TRANSITION",
        )

    # 5. Enforce role permissions
    user_category = UserRole.normalize_category(user_role)
    if user_category not in rule["roles"]:
        raise WorkflowPermissionError(
            f"Role category '{user_category}' is not permitted to transition FDR from '{curr_val}' to '{targ_val}'. "
            f"Required role categories: {sorted(list(rule['roles']))}.",
            code="WORKFLOW_ROLE_RESTRICTED",
        )

    # 6. Validate remarks
    clean_remarks = str(remarks).strip() if remarks is not None else None
    if clean_remarks == "":
        clean_remarks = None

    if rule["requires_remarks"]:
        if not clean_remarks:
            raise WorkflowValidationError(
                {
                    "remarks": (
                        f"A non-empty reason/remarks field is required when transitioning to '{targ_val}'."
                    )
                }
            )

    if clean_remarks and len(clean_remarks) > MAX_REMARKS_LENGTH:
        raise WorkflowValidationError(
            {
                "remarks": f"Remarks must not exceed {MAX_REMARKS_LENGTH} characters (received {len(clean_remarks)})."
            }
        )

    return {
        "current_status": curr_val,
        "target_status": targ_val,
        "user_category": user_category,
        "remarks": clean_remarks,
        "rule": rule,
    }


def validate_submission_readiness(fdr: FDRRecord) -> None:
    """
    Validate that mandatory FDR attributes and supporting documentation are present
    before an institution can submit the record for scrutiny.
    """
    errors = {}

    if not fdr.fdr_number or not str(fdr.fdr_number).strip():
        errors["fdr_number"] = "FDR number is required for submission."
    if not fdr.bank_name or not str(fdr.bank_name).strip():
        errors["bank_name"] = "Bank name is required for submission."
    if not fdr.branch_name or not str(fdr.branch_name).strip():
        errors["branch_name"] = "Branch name is required for submission."
    if not fdr.amount or fdr.amount <= 0:
        errors["amount"] = "A valid positive amount is required for submission."
    if not fdr.issue_date:
        errors["issue_date"] = "Issue date is required for submission."
    if not fdr.maturity_date:
        errors["maturity_date"] = "Maturity date is required for submission."
    elif fdr.issue_date and fdr.maturity_date < fdr.issue_date:
        errors["maturity_date"] = "Maturity date cannot be earlier than issue date."

    # Verify at least one supporting document has been uploaded
    from app.models.document import Document

    doc_count = Document.query.filter_by(fdr_id=fdr.id).count()
    if doc_count == 0:
        errors["documents"] = (
            "At least one supporting FDR receipt document must be uploaded before submission."
        )

    if errors:
        raise WorkflowValidationError(errors)


def get_available_workflow_actions(fdr: FDRRecord, current_user: User) -> list[str]:
    """
    Determine the permitted workflow action identifiers for the authenticated user and current status.
    Possible actions: 'submit', 'start-review', 'verify', 'return', 'reject'.
    """
    user_category = UserRole.normalize_category(current_user.role)
    status = fdr.scrutiny_status
    actions: list[str] = []

    # Institution users and Admins can submit DRAFT or RETURNED records
    if user_category in ("INSTITUTION", "ADMIN"):
        if status in (ScrutinyStatus.DRAFT.value, ScrutinyStatus.RETURNED.value):
            actions.append("submit")

    # Officers and Admins can start review on SUBMITTED records
    if user_category in ("AICTE_OFFICER", "ADMIN"):
        if status == ScrutinyStatus.SUBMITTED.value:
            actions.append("start-review")
        elif status == ScrutinyStatus.PENDING_VERIFICATION.value:
            actions.extend(["verify", "return", "reject"])

    return actions


def get_fdr_workflow_history(
    fdr: FDRRecord,
    current_user: User,
    page: int | None = None,
    per_page: int | None = None,
) -> tuple[list[dict], dict | None, list[dict]]:
    """
    Safely retrieve structured workflow decision history and deficiency notices from FDRWorkflowHistory.
    Never exposes passwords, tokens, or fabricated history.
    """
    user_category = UserRole.normalize_category(current_user.role)
    is_officer_or_admin = user_category in ("AICTE_OFFICER", "ADMIN")

    query = FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id).order_by(
        FDRWorkflowHistory.created_at.asc(), FDRWorkflowHistory.id.asc()
    )

    pagination_data = None
    if page is not None or per_page is not None:
        try:
            safe_page = max(1, int(page or 1))
        except (ValueError, TypeError):
            safe_page = 1
        try:
            safe_per_page = min(100, max(1, int(per_page or 20)))
        except (ValueError, TypeError):
            safe_per_page = 20

        paginated = query.paginate(
            page=safe_page, per_page=safe_per_page, error_out=False
        )
        items = paginated.items
        pagination_data = {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
        }
    else:
        items = query.all()

    history: list[dict] = [
        item.to_dict(include_actor_email=is_officer_or_admin) for item in items
    ]

    # Deficiencies: all records for this FDR marked as deficiency
    deficiency_records = (
        FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id, is_deficiency=True)
        .order_by(FDRWorkflowHistory.created_at.asc(), FDRWorkflowHistory.id.asc())
        .all()
    )
    deficiencies: list[dict] = [
        item.to_dict(include_actor_email=is_officer_or_admin)
        for item in deficiency_records
    ]

    return history, pagination_data, deficiencies


def transition_fdr_scrutiny_status(
    fdr_id: int,
    target_status: str | ScrutinyStatus,
    current_user: User,
    remarks: str | None = None,
    enforce_submission_requirements: bool = False,
) -> FDRRecord:
    """
    Execute a validated FDR scrutiny status transition with atomic audit logging,
    structured FDRWorkflowHistory recording, and notifications.

    Safety:
    - Never trusts client-supplied user IDs or roles.
    - Enforces institution data isolation via get_authorized_fdr (raises 404 for inaccessible records).
    - Preserves validity_status and all other FDR metadata unchanged.
    - Transactionally rolls back changes if any step fails.
    """
    # 1. Fetch authorized FDR (enforces tenant isolation and returns 404 on cross-institution access)
    fdr = get_authorized_fdr(fdr_id, current_user)

    # 2. If submitting and enforcement is requested, validate required fields & documents
    targ_val = (
        target_status.value
        if isinstance(target_status, ScrutinyStatus)
        else str(target_status).strip().upper()
    )
    if enforce_submission_requirements and targ_val == ScrutinyStatus.SUBMITTED.value:
        validate_submission_readiness(fdr)

    # 3. Validate transition rules, permissions, and decision remarks
    validated = validate_scrutiny_transition(
        current_status=fdr.scrutiny_status,
        target_status=target_status,
        user_role=current_user.role,
        remarks=remarks,
    )

    previous_status = validated["current_status"]
    new_status = validated["target_status"]
    clean_remarks = validated["remarks"]
    action_timestamp = datetime.now(timezone.utc)

    try:
        # 3. Update scrutiny status
        fdr.scrutiny_status = new_status
        fdr.updated_at = action_timestamp

        # 4. Record structured FDRWorkflowHistory entry
        is_deficiency = new_status == ScrutinyStatus.RETURNED.value
        resolution_status = "UNRESOLVED" if is_deficiency else None

        history_entry = FDRWorkflowHistory(
            fdr_id=fdr.id,
            from_status=previous_status,
            to_status=new_status,
            actor_id=current_user.id,
            remarks=clean_remarks,
            is_deficiency=is_deficiency,
            resolution_status=resolution_status,
            created_at=action_timestamp,
        )
        db.session.add(history_entry)

        # 5. Record comprehensive audit trail entry
        audit_details = json.dumps(
            {
                "previous_status": previous_status,
                "new_status": new_status,
                "actor_id": current_user.id,
                "actor_email": current_user.email,
                "actor_role": current_user.role,
                "remarks": clean_remarks,
                "timestamp": action_timestamp.isoformat(),
            }
        )

        audit = AuditLog(
            user_id=current_user.id,
            action=f"SCRUTINY_TRANSITION_{previous_status}_TO_{new_status}",
            entity_type="FDRRecord",
            entity_id=fdr.id,
            details=audit_details,
            created_at=action_timestamp,
        )
        db.session.add(audit)

        # 5. Generate contextual notifications for relevant users
        _generate_scrutiny_notifications(
            fdr=fdr,
            previous_status=previous_status,
            new_status=new_status,
            actor=current_user,
            remarks=clean_remarks,
        )

        db.session.commit()
        return fdr

    except Exception:
        db.session.rollback()
        raise


def _generate_scrutiny_notifications(
    fdr: FDRRecord,
    previous_status: str,
    new_status: str,
    actor: User,
    remarks: str | None,
) -> None:
    """Generate notifications for institution users and officers based on the scrutiny decision."""
    # Active users of the owning institution
    institution_users = User.query.filter_by(
        institution_id=fdr.institution_id, is_active=True
    ).all()

    # Active officers/admins
    officers = User.query.filter(
        User.role.in_(
            [
                UserRole.AICTE_OFFICER.value,
                UserRole.ADMIN.value,
                UserRole.AICTE_ADMIN.value,
                UserRole.SYSTEM_ADMIN.value,
            ]
        ),
        User.is_active.is_(True),
    ).all()

    title = None
    message = None
    notif_type = NotificationType.INFO.value
    recipients: list[User] = []

    if new_status == ScrutinyStatus.SUBMITTED.value:
        action_verb = "resubmitted" if previous_status == ScrutinyStatus.RETURNED.value else "submitted"
        title = f"FDR {action_verb.capitalize()}: {fdr.fdr_number}"
        message = (
            f"Fixed Deposit Receipt {fdr.fdr_number} of {fdr.bank_name} (INR {fdr.amount}) "
            f"has been {action_verb} for AICTE scrutiny."
        )
        notif_type = NotificationType.INFO.value
        # Notify institution users as confirmation + notify officers for scrutiny queue
        recipients = list(set(institution_users + officers))

    elif new_status == ScrutinyStatus.PENDING_VERIFICATION.value:
        title = f"FDR Under Scrutiny: {fdr.fdr_number}"
        message = (
            f"Fixed Deposit Receipt {fdr.fdr_number} is now under active verification by AICTE. "
            f"Officer: {actor.full_name} ({actor.email})."
        )
        notif_type = NotificationType.INFO.value
        recipients = institution_users

    elif new_status == ScrutinyStatus.VERIFIED.value:
        title = f"FDR Verified: {fdr.fdr_number}"
        message = (
            f"Fixed Deposit Receipt {fdr.fdr_number} has been verified and approved by AICTE."
        )
        if remarks:
            message += f" Remarks: {remarks}"
        notif_type = NotificationType.INFO.value
        recipients = institution_users

    elif new_status == ScrutinyStatus.RETURNED.value:
        title = f"FDR Returned for Correction: {fdr.fdr_number}"
        message = (
            f"Fixed Deposit Receipt {fdr.fdr_number} has been returned by AICTE. "
            f"Reason: {remarks}. Please rectify the details or supporting documents and resubmit."
        )
        notif_type = NotificationType.ACTION_REQUIRED.value
        recipients = institution_users

    elif new_status == ScrutinyStatus.REJECTED.value:
        title = f"FDR Submission Rejected: {fdr.fdr_number}"
        message = (
            f"Fixed Deposit Receipt {fdr.fdr_number} has been rejected by AICTE. "
            f"Reason: {remarks}."
        )
        notif_type = NotificationType.ALERT.value
        recipients = institution_users

    if not title or not recipients:
        return

    for recipient in recipients:
        notif = Notification(
            user_id=recipient.id,
            title=title,
            message=message,
            notification_type=notif_type,
            is_read=False,
        )
        db.session.add(notif)
