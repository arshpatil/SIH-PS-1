from datetime import date
from decimal import Decimal
import json
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import NotificationType, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.user import User
from app.services.fdr_service import FDRNotFoundError
from app.services.workflow_service import (
    ALLOWED_SCRUTINY_TRANSITIONS,
    WorkflowPermissionError,
    WorkflowTransitionError,
    WorkflowValidationError,
    transition_fdr_scrutiny_status,
    validate_scrutiny_transition,
)


@pytest.fixture
def seed_workflow_env(app):
    """Seed institutions, users across roles, and baseline FDR records for workflow tests."""
    inst_a = Institution(
        institution_code="AICTE-WF-A",
        name="Apex Engineering College",
        contact_email="principal@apex.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-WF-B",
        name="Zenith Polytechnic",
        contact_email="principal@zenith.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    user_a = User(
        full_name="Registrar Apex",
        email="registrar@apex.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a.set_password("ApexPass123!")

    user_b = User(
        full_name="Registrar Zenith",
        email="registrar@zenith.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_b.id,
        is_active=True,
    )
    user_b.set_password("ZenithPass123!")

    officer = User(
        full_name="AICTE Verification Officer",
        email="officer.verif@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="AICTE Portal Admin",
        email="admin.portal@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([user_a, user_b, officer, admin])
    db.session.commit()

    # Create baseline draft FDR for inst_a
    fdr_draft = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-WF-DRAFT-01",
        bank_name="State Bank of India",
        branch_name="University Campus",
        amount=Decimal("1000000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    db.session.add(fdr_draft)
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
        "fdr_draft": fdr_draft,
    }


# =====================================================================
# 1. Transition Validator Unit Tests (Allowed & Disallowed)
# =====================================================================


def test_validator_allowed_transitions():
    """Verify that all 6 canonical scrutiny transitions pass validation with authorized roles."""
    # 1. DRAFT -> SUBMITTED (INSTITUTION)
    res = validate_scrutiny_transition(
        current_status=ScrutinyStatus.DRAFT,
        target_status=ScrutinyStatus.SUBMITTED,
        user_role=UserRole.INSTITUTION,
    )
    assert res["target_status"] == ScrutinyStatus.SUBMITTED.value

    # 2. RETURNED -> SUBMITTED (INSTITUTION)
    res = validate_scrutiny_transition(
        current_status=ScrutinyStatus.RETURNED,
        target_status=ScrutinyStatus.SUBMITTED,
        user_role=UserRole.INSTITUTION,
    )
    assert res["target_status"] == ScrutinyStatus.SUBMITTED.value

    # 3. SUBMITTED -> PENDING_VERIFICATION (AICTE_OFFICER)
    res = validate_scrutiny_transition(
        current_status=ScrutinyStatus.SUBMITTED,
        target_status=ScrutinyStatus.PENDING_VERIFICATION,
        user_role=UserRole.AICTE_OFFICER,
    )
    assert res["target_status"] == ScrutinyStatus.PENDING_VERIFICATION.value

    # 4. PENDING_VERIFICATION -> VERIFIED (AICTE_OFFICER)
    res = validate_scrutiny_transition(
        current_status=ScrutinyStatus.PENDING_VERIFICATION,
        target_status=ScrutinyStatus.VERIFIED,
        user_role=UserRole.AICTE_OFFICER,
        remarks="Lien verified successfully.",
    )
    assert res["target_status"] == ScrutinyStatus.VERIFIED.value

    # 5. PENDING_VERIFICATION -> RETURNED (AICTE_OFFICER with remarks)
    res = validate_scrutiny_transition(
        current_status=ScrutinyStatus.PENDING_VERIFICATION,
        target_status=ScrutinyStatus.RETURNED,
        user_role=UserRole.AICTE_OFFICER,
        remarks="Bank confirmation letter is missing branch code.",
    )
    assert res["target_status"] == ScrutinyStatus.RETURNED.value
    assert res["remarks"] == "Bank confirmation letter is missing branch code."

    # 6. PENDING_VERIFICATION -> REJECTED (AICTE_OFFICER with remarks)
    res = validate_scrutiny_transition(
        current_status=ScrutinyStatus.PENDING_VERIFICATION,
        target_status=ScrutinyStatus.REJECTED,
        user_role=UserRole.AICTE_OFFICER,
        remarks="Fraudulent FDR certificate detected.",
    )
    assert res["target_status"] == ScrutinyStatus.REJECTED.value


def test_validator_admin_oversight_permissions():
    """Verify that administrators can perform all authorized scrutiny transitions."""
    for (src, dst), rule in ALLOWED_SCRUTINY_TRANSITIONS.items():
        remarks = "Admin oversight action" if rule["requires_remarks"] else None
        res = validate_scrutiny_transition(
            current_status=src,
            target_status=dst,
            user_role=UserRole.ADMIN,
            remarks=remarks,
        )
        assert res["target_status"] == dst


def test_validator_disallowed_transitions():
    """Verify that non-canonical transitions are strictly rejected."""
    # DRAFT -> VERIFIED is invalid
    with pytest.raises(WorkflowTransitionError) as exc_info:
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.DRAFT,
            target_status=ScrutinyStatus.VERIFIED,
            user_role=UserRole.ADMIN,
        )
    assert "not permitted" in str(exc_info.value)
    assert exc_info.value.code == "INVALID_TRANSITION"

    # DRAFT -> RETURNED is invalid
    with pytest.raises(WorkflowTransitionError):
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.DRAFT,
            target_status=ScrutinyStatus.RETURNED,
            user_role=UserRole.ADMIN,
            remarks="Invalid",
        )

    # SUBMITTED -> VERIFIED is invalid (must go through PENDING_VERIFICATION first)
    with pytest.raises(WorkflowTransitionError):
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.SUBMITTED,
            target_status=ScrutinyStatus.VERIFIED,
            user_role=UserRole.AICTE_OFFICER,
        )

    # SUBMITTED -> DRAFT is invalid
    with pytest.raises(WorkflowTransitionError):
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.SUBMITTED,
            target_status=ScrutinyStatus.DRAFT,
            user_role=UserRole.INSTITUTION,
        )

    # RETURNED -> VERIFIED is invalid
    with pytest.raises(WorkflowTransitionError):
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.RETURNED,
            target_status=ScrutinyStatus.VERIFIED,
            user_role=UserRole.AICTE_OFFICER,
        )


def test_validator_terminal_states_locked():
    """Verify that terminal states (VERIFIED, REJECTED) cannot undergo any further transitions."""
    for terminal in [ScrutinyStatus.VERIFIED, ScrutinyStatus.REJECTED]:
        with pytest.raises(WorkflowTransitionError) as exc_info:
            validate_scrutiny_transition(
                current_status=terminal,
                target_status=ScrutinyStatus.SUBMITTED,
                user_role=UserRole.ADMIN,
            )
        assert exc_info.value.code == "TERMINAL_STATUS_LOCKED"


def test_validator_self_transition_disallowed():
    """Verify that transitioning to the same status is rejected as a no-op."""
    with pytest.raises(WorkflowTransitionError) as exc_info:
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.DRAFT,
            target_status=ScrutinyStatus.DRAFT,
            user_role=UserRole.INSTITUTION,
        )
    assert exc_info.value.code == "NO_OP_TRANSITION"


# =====================================================================
# 2. Role Permissions & Decision Remarks Validation
# =====================================================================


def test_validator_role_permission_enforcement():
    """Verify that users cannot perform transitions outside their role boundaries."""
    # Institution user cannot move SUBMITTED to PENDING_VERIFICATION
    with pytest.raises(WorkflowPermissionError) as exc_info:
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.SUBMITTED,
            target_status=ScrutinyStatus.PENDING_VERIFICATION,
            user_role=UserRole.INSTITUTION,
        )
    assert exc_info.value.code == "WORKFLOW_ROLE_RESTRICTED"

    # Institution user cannot approve (VERIFIED)
    with pytest.raises(WorkflowPermissionError):
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.PENDING_VERIFICATION,
            target_status=ScrutinyStatus.VERIFIED,
            user_role=UserRole.INSTITUTION,
        )

    # Officer cannot submit a draft FDR for an institution
    with pytest.raises(WorkflowPermissionError):
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.DRAFT,
            target_status=ScrutinyStatus.SUBMITTED,
            user_role=UserRole.AICTE_OFFICER,
        )


def test_validator_decision_remarks_validation():
    """Verify that RETURNED and REJECTED transitions require non-empty remarks and enforce character limits."""
    # 1. Missing remarks on RETURNED -> error
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.PENDING_VERIFICATION,
            target_status=ScrutinyStatus.RETURNED,
            user_role=UserRole.AICTE_OFFICER,
            remarks=None,
        )
    assert "remarks" in exc_info.value.errors

    # 2. Whitespace-only remarks on REJECTED -> error
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.PENDING_VERIFICATION,
            target_status=ScrutinyStatus.REJECTED,
            user_role=UserRole.AICTE_OFFICER,
            remarks="   \t\n  ",
        )
    assert "remarks" in exc_info.value.errors

    # 3. Excessive length (> 2000 chars) -> error
    too_long = "A" * 2001
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_scrutiny_transition(
            current_status=ScrutinyStatus.PENDING_VERIFICATION,
            target_status=ScrutinyStatus.RETURNED,
            user_role=UserRole.AICTE_OFFICER,
            remarks=too_long,
        )
    assert "2000" in exc_info.value.errors["remarks"]


# =====================================================================
# 3. End-to-End Workflow Transitions & Scrutiny Lifecycles
# =====================================================================


def test_full_scrutiny_approval_lifecycle(seed_workflow_env):
    """Test full happy-path lifecycle: DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> VERIFIED."""
    env = seed_workflow_env
    fdr = env["fdr_draft"]

    # 1. Institution user submits DRAFT -> SUBMITTED
    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.SUBMITTED,
        current_user=env["user_a"],
    )
    assert fdr.scrutiny_status == ScrutinyStatus.SUBMITTED.value

    # Verify audit log created
    audit = AuditLog.query.filter_by(
        entity_id=fdr.id, action="SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED"
    ).first()
    assert audit is not None
    assert audit.user_id == env["user_a"].id
    details = json.loads(audit.details)
    assert details["previous_status"] == "DRAFT"
    assert details["new_status"] == "SUBMITTED"

    # 2. Officer takes up case: SUBMITTED -> PENDING_VERIFICATION
    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.PENDING_VERIFICATION,
        current_user=env["officer"],
    )
    assert fdr.scrutiny_status == ScrutinyStatus.PENDING_VERIFICATION.value

    # Check notification for institution user
    notif_scrutiny = Notification.query.filter_by(
        user_id=env["user_a"].id, title=f"FDR Under Scrutiny: {fdr.fdr_number}"
    ).first()
    assert notif_scrutiny is not None

    # 3. Officer approves deposit: PENDING_VERIFICATION -> VERIFIED
    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.VERIFIED,
        current_user=env["officer"],
        remarks="Lien confirmed with SBI main branch.",
    )
    assert fdr.scrutiny_status == ScrutinyStatus.VERIFIED.value

    # Check notification for institution user
    notif_verified = Notification.query.filter_by(
        user_id=env["user_a"].id, title=f"FDR Verified: {fdr.fdr_number}"
    ).first()
    assert notif_verified is not None
    assert "SBI main branch" in notif_verified.message

    # Validity status must remain ACTIVE and untouched
    assert fdr.validity_status == ValidityStatus.ACTIVE.value


def test_scrutiny_return_and_resubmission_lifecycle(seed_workflow_env):
    """Test return and resubmission: DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> RETURNED -> SUBMITTED."""
    env = seed_workflow_env
    fdr = env["fdr_draft"]

    # DRAFT -> SUBMITTED
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.SUBMITTED,
        current_user=env["user_a"],
    )

    # SUBMITTED -> PENDING_VERIFICATION
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.PENDING_VERIFICATION,
        current_user=env["officer"],
    )

    # PENDING_VERIFICATION -> RETURNED (with required remarks)
    reason = "FDR scan is blurry. Please upload high-resolution PDF with official bank seal."
    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.RETURNED,
        current_user=env["officer"],
        remarks=reason,
    )
    assert fdr.scrutiny_status == ScrutinyStatus.RETURNED.value

    # Check that institution user received actionable notification
    notif_returned = Notification.query.filter_by(
        user_id=env["user_a"].id,
        notification_type=NotificationType.ACTION_REQUIRED.value,
    ).first()
    assert notif_returned is not None
    assert "blurry" in notif_returned.message

    # Institution resubmits: RETURNED -> SUBMITTED
    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.SUBMITTED,
        current_user=env["user_a"],
    )
    assert fdr.scrutiny_status == ScrutinyStatus.SUBMITTED.value

    # Check audit log for resubmission
    audit_resubmit = AuditLog.query.filter_by(
        entity_id=fdr.id, action="SCRUTINY_TRANSITION_RETURNED_TO_SUBMITTED"
    ).first()
    assert audit_resubmit is not None


def test_scrutiny_rejection_lifecycle(seed_workflow_env):
    """Test rejection lifecycle: DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> REJECTED."""
    env = seed_workflow_env
    fdr = env["fdr_draft"]

    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.SUBMITTED,
        current_user=env["user_a"],
    )
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.PENDING_VERIFICATION,
        current_user=env["officer"],
    )

    rejection_reason = "Deposit receipt was encashed by the institution without AICTE NOC."
    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.REJECTED,
        current_user=env["officer"],
        remarks=rejection_reason,
    )
    assert fdr.scrutiny_status == ScrutinyStatus.REJECTED.value

    # Check alert notification
    notif_rejected = Notification.query.filter_by(
        user_id=env["user_a"].id,
        notification_type=NotificationType.ALERT.value,
    ).first()
    assert notif_rejected is not None
    assert rejection_reason in notif_rejected.message


# =====================================================================
# 4. Cross-Tenant Isolation & Transaction Rollback
# =====================================================================


def test_cross_tenant_isolation_on_transition(seed_workflow_env):
    """Verify that an institution user cannot access or transition an FDR belonging to another institution."""
    env = seed_workflow_env
    fdr_a = env["fdr_draft"]  # Belongs to Institution A

    # User B attempts to transition Institution A's FDR
    with pytest.raises(FDRNotFoundError):
        transition_fdr_scrutiny_status(
            fdr_id=fdr_a.id,
            target_status=ScrutinyStatus.SUBMITTED,
            current_user=env["user_b"],  # Belongs to Institution B
        )

    # Status must remain DRAFT
    refreshed = db.session.get(FDRRecord, fdr_a.id)
    assert refreshed is not None
    assert refreshed.scrutiny_status == ScrutinyStatus.DRAFT.value

    # Institution B user must have received zero notifications
    notifs_b = Notification.query.filter_by(user_id=env["user_b"].id).all()
    assert len(notifs_b) == 0


def test_transaction_rollback_on_failure(seed_workflow_env, monkeypatch):
    """Verify that if an error occurs during transition commit, the database rolls back completely."""
    env = seed_workflow_env
    fdr = env["fdr_draft"]

    # Monkeypatch db.session.commit to simulate database failure
    def mock_commit():
        raise RuntimeError("Simulated database failure during commit")

    monkeypatch.setattr(db.session, "commit", mock_commit)

    with pytest.raises(RuntimeError):
        transition_fdr_scrutiny_status(
            fdr_id=fdr.id,
            target_status=ScrutinyStatus.SUBMITTED,
            current_user=env["user_a"],
        )

    # Status in database must remain DRAFT
    db.session.rollback()
    refreshed = db.session.get(FDRRecord, fdr.id)
    assert refreshed is not None
    assert refreshed.scrutiny_status == ScrutinyStatus.DRAFT.value

    # No audit log or notifications should exist for this failed attempt
    audit = AuditLog.query.filter_by(
        entity_id=fdr.id, action="SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED"
    ).first()
    assert audit is None
