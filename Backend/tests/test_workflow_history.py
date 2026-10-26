from datetime import date, datetime, timezone
from decimal import Decimal
import json
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User
from app.models.workflow_history import FDRWorkflowHistory
from app.services.migration_service import run_workflow_history_migration
from app.services.workflow_service import transition_fdr_scrutiny_status


@pytest.fixture
def seed_history_env(app):
    """Seed test institutions, users, and baseline FDR for history tracking."""
    inst_a = Institution(
        institution_code="AICTE-HIST-A",
        name="Apex College of Engineering",
        contact_email="director@apex.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-HIST-B",
        name="Zenith Technical Institute",
        contact_email="director@zenith.edu",
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
        full_name="AICTE Scrutiny Officer",
        email="officer.scrutiny@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="AICTE Portal Admin",
        email="admin.scrutiny@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([user_a, user_b, officer, admin])
    db.session.commit()

    # Draft FDR for Institution A
    fdr_a = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-HIST-001",
        bank_name="State Bank of India",
        branch_name="Main Campus",
        amount=Decimal("1500000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    db.session.add(fdr_a)
    db.session.commit()

    # Attach supporting document
    doc = Document(
        fdr_id=fdr_a.id,
        original_filename="receipt.pdf",
        stored_filename="fdr_hist_stored.pdf",
        file_type="application/pdf",
        file_size=204800,
        processing_status="PROCESSED",
        uploaded_by=user_a.id,
    )
    db.session.add(doc)
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
        "fdr_a": fdr_a,
    }


def login_and_get_csrf(client, email, password="ApexPass123!"):
    """Helper to authenticate and extract session CSRF token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


# =====================================================================
# 1. Structured History Recording & Rollback Safety
# =====================================================================


def test_history_created_for_every_successful_transition(seed_history_env):
    """Verify that every scrutiny transition generates an immutable FDRWorkflowHistory row."""
    env = seed_history_env
    fdr = env["fdr_a"]

    # 1. DRAFT -> SUBMITTED
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.SUBMITTED,
        current_user=env["user_a"],
        remarks="Submitted with official receipt",
    )
    history1 = FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id).all()
    assert len(history1) == 1
    assert history1[0].from_status == "DRAFT"
    assert history1[0].to_status == "SUBMITTED"
    assert history1[0].actor_id == env["user_a"].id
    assert history1[0].remarks == "Submitted with official receipt"
    assert history1[0].is_deficiency is False

    # 2. SUBMITTED -> PENDING_VERIFICATION
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.PENDING_VERIFICATION,
        current_user=env["officer"],
    )
    history2 = FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id).order_by(
        FDRWorkflowHistory.id.asc()
    ).all()
    assert len(history2) == 2
    assert history2[1].from_status == "SUBMITTED"
    assert history2[1].to_status == "PENDING_VERIFICATION"
    assert history2[1].actor_id == env["officer"].id

    # 3. PENDING_VERIFICATION -> VERIFIED
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.VERIFIED,
        current_user=env["officer"],
        remarks="Lien verified and confirmed by bank",
    )
    history3 = FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id).order_by(
        FDRWorkflowHistory.id.asc()
    ).all()
    assert len(history3) == 3
    assert history3[2].from_status == "PENDING_VERIFICATION"
    assert history3[2].to_status == "VERIFIED"
    assert history3[2].remarks == "Lien verified and confirmed by bank"


def test_history_and_status_rollback_together_on_failure(seed_history_env, monkeypatch):
    """Verify that if commit fails, status change and workflow history roll back atomically."""
    env = seed_history_env
    fdr = env["fdr_a"]

    def mock_commit():
        raise RuntimeError("Simulated database failure during transaction commit")

    monkeypatch.setattr(db.session, "commit", mock_commit)

    with pytest.raises(RuntimeError):
        transition_fdr_scrutiny_status(
            fdr_id=fdr.id,
            target_status=ScrutinyStatus.SUBMITTED,
            current_user=env["user_a"],
        )

    # Roll back and verify
    db.session.rollback()
    refreshed = db.session.get(FDRRecord, fdr.id)
    assert refreshed.scrutiny_status == ScrutinyStatus.DRAFT.value
    # No history row must exist
    assert FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id).count() == 0


# =====================================================================
# 2. Deficiency Tracking & Resubmission Behavior
# =====================================================================


def test_officer_return_remarks_preserved_as_deficiency(seed_history_env):
    """Verify that officer return decision is recorded as an unresolved deficiency record."""
    env = seed_history_env
    fdr = env["fdr_a"]

    # Move to PENDING_VERIFICATION
    transition_fdr_scrutiny_status(fdr.id, ScrutinyStatus.SUBMITTED, env["user_a"])
    transition_fdr_scrutiny_status(fdr.id, ScrutinyStatus.PENDING_VERIFICATION, env["officer"])

    # Officer returns with explicit deficiency remarks
    deficiency_reason = "Branch seal is missing on page 1. Account name lacks AICTE joint clause."
    transition_fdr_scrutiny_status(
        fdr_id=fdr.id,
        target_status=ScrutinyStatus.RETURNED,
        current_user=env["officer"],
        remarks=deficiency_reason,
    )

    # Check workflow history
    deficiencies = FDRWorkflowHistory.query.filter_by(
        fdr_id=fdr.id, is_deficiency=True
    ).all()
    assert len(deficiencies) == 1
    deficiency = deficiencies[0]
    assert deficiency.to_status == "RETURNED"
    assert deficiency.remarks == deficiency_reason
    assert deficiency.resolution_status == "UNRESOLVED"


def test_resubmission_preserves_earlier_deficiencies_without_auto_resolution(seed_history_env):
    """Verify that institution resubmission creates a new history entry and does NOT auto-resolve earlier deficiencies."""
    env = seed_history_env
    fdr = env["fdr_a"]

    transition_fdr_scrutiny_status(fdr.id, ScrutinyStatus.SUBMITTED, env["user_a"])
    transition_fdr_scrutiny_status(fdr.id, ScrutinyStatus.PENDING_VERIFICATION, env["officer"])

    deficiency_reason = "Interest payout mode must be cumulative."
    transition_fdr_scrutiny_status(
        fdr.id, ScrutinyStatus.RETURNED, env["officer"], remarks=deficiency_reason
    )

    # Institution resubmits: RETURNED -> SUBMITTED
    transition_fdr_scrutiny_status(
        fdr.id,
        ScrutinyStatus.SUBMITTED,
        env["user_a"],
        remarks="Converted to cumulative interest mode with bank endorsement.",
    )

    # 1. Total history rows = 4
    all_history = FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id).order_by(
        FDRWorkflowHistory.id.asc()
    ).all()
    assert len(all_history) == 4

    # 2. Resubmission event is a distinct new entry
    resubmit_entry = all_history[3]
    assert resubmit_entry.from_status == "RETURNED"
    assert resubmit_entry.to_status == "SUBMITTED"
    assert resubmit_entry.is_deficiency is False

    # 3. Earlier return deficiency record remains UNTOUCHED and still UNRESOLVED
    return_entry = all_history[2]
    assert return_entry.to_status == "RETURNED"
    assert return_entry.is_deficiency is True
    assert return_entry.remarks == deficiency_reason
    assert return_entry.resolution_status == "UNRESOLVED"


# =====================================================================
# 3. Workflow API History, Deficiencies, & Pagination
# =====================================================================


def test_workflow_api_chronological_history_and_pagination(client, seed_history_env):
    """Test GET /api/fdr/<id>/workflow returns chronological history, deficiency list, and supports pagination."""
    env = seed_history_env
    fdr = env["fdr_a"]

    # Lifecycle: DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> RETURNED -> SUBMITTED (4 events)
    transition_fdr_scrutiny_status(fdr.id, ScrutinyStatus.SUBMITTED, env["user_a"])
    transition_fdr_scrutiny_status(fdr.id, ScrutinyStatus.PENDING_VERIFICATION, env["officer"])
    transition_fdr_scrutiny_status(
        fdr.id, ScrutinyStatus.RETURNED, env["officer"], remarks="Need clear stamp"
    )
    transition_fdr_scrutiny_status(
        fdr.id, ScrutinyStatus.SUBMITTED, env["user_a"], remarks="Uploaded clear stamp"
    )

    csrf = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    # 1. Full unpaginated retrieval
    res_full = client.get(f"/api/fdr/{fdr.id}/workflow")
    assert res_full.status_code == 200
    data_full = res_full.get_json()["data"]

    history = data_full["workflow_history"]
    assert len(history) == 4
    assert history[0]["to_status"] == "SUBMITTED"
    assert history[1]["to_status"] == "PENDING_VERIFICATION"
    assert history[2]["to_status"] == "RETURNED"
    assert history[3]["to_status"] == "SUBMITTED"

    # Deficiencies section must contain the return notice
    deficiencies = data_full["deficiencies"]
    assert len(deficiencies) == 1
    assert deficiencies[0]["remarks"] == "Need clear stamp"
    assert deficiencies[0]["resolution_status"] == "UNRESOLVED"

    # 2. Paginated retrieval: page 1 (per_page=2)
    res_p1 = client.get(f"/api/fdr/{fdr.id}/workflow?page=1&per_page=2")
    assert res_p1.status_code == 200
    data_p1 = res_p1.get_json()["data"]
    assert len(data_p1["workflow_history"]) == 2
    assert data_p1["pagination"]["total"] == 4
    assert data_p1["pagination"]["pages"] == 2
    assert data_p1["pagination"]["has_next"] is True
    assert data_p1["pagination"]["has_prev"] is False

    # 3. Paginated retrieval: page 2 (per_page=2)
    res_p2 = client.get(f"/api/fdr/{fdr.id}/workflow?page=2&per_page=2")
    assert res_p2.status_code == 200
    data_p2 = res_p2.get_json()["data"]
    assert len(data_p2["workflow_history"]) == 2
    assert data_p2["pagination"]["has_next"] is False
    assert data_p2["pagination"]["has_prev"] is True


def test_workflow_api_tenant_isolation(client, seed_history_env):
    """Verify that User B cannot access workflow history of User A's FDR (returns 404)."""
    env = seed_history_env
    fdr_a = env["fdr_a"]

    login_and_get_csrf(client, "registrar@zenith.edu", "ZenithPass123!")
    res = client.get(f"/api/fdr/{fdr_a.id}/workflow")
    assert res.status_code == 404


# =====================================================================
# 4. Safe Migration & AuditLog Backfill Tests
# =====================================================================


def test_safe_migration_and_audit_backfill(app, seed_history_env):
    """Verify that run_workflow_history_migration creates table, backfills AuditLog, and reruns idempotently."""
    env = seed_history_env
    fdr = env["fdr_a"]

    # Seed an AuditLog record simulating a pre-existing transition
    past_timestamp = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    audit = AuditLog(
        user_id=env["user_a"].id,
        action="SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED",
        entity_type="FDRRecord",
        entity_id=fdr.id,
        details=json.dumps(
            {
                "previous_status": "DRAFT",
                "new_status": "SUBMITTED",
                "actor_id": env["user_a"].id,
                "actor_email": env["user_a"].email,
                "actor_role": "INSTITUTION",
                "remarks": "Historical pre-migration submission",
                "timestamp": past_timestamp.isoformat(),
            }
        ),
        created_at=past_timestamp,
    )
    db.session.add(audit)
    db.session.commit()

    with app.app_context():
        # First migration run: creates table if not present and backfills historical audit
        result1 = run_workflow_history_migration(app=app, backfill=True)
        assert result1["success"] is True
        assert result1["backfilled_count"] >= 1

        # Verify backfilled row in FDRWorkflowHistory
        backfilled_row = FDRWorkflowHistory.query.filter_by(
            fdr_id=fdr.id, created_at=past_timestamp
        ).first()
        assert backfilled_row is not None
        assert backfilled_row.from_status == "DRAFT"
        assert backfilled_row.to_status == "SUBMITTED"
        assert backfilled_row.remarks == "Historical pre-migration submission"

        # Second migration run (idempotent rerun): must not duplicate rows
        result2 = run_workflow_history_migration(app=app, backfill=True)
        assert result2["success"] is True
        assert result2["table_already_existed"] is True
        assert result2["backfilled_count"] == 0  # No duplicate inserts!


def test_cli_migrate_workflow_history(runner, seed_history_env):
    """Test flask migrate-workflow-history CLI command execution."""
    result = runner.invoke(args=["migrate-workflow-history"])
    assert result.exit_code == 0
    assert "Migration completed" in result.output
