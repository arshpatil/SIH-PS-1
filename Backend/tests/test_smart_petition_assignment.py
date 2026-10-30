from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest, PetitionAssignmentHistory
from app.models.institution import Institution
from app.models.user import User
from app.services.assignment_service import (
    auto_assign_petition,
    calculate_admin_workload_metrics,
    get_eligible_officers,
    get_officer_active_workload,
    reassign_petition,
    scan_and_alert_critical_and_overdue_petitions,
    select_best_officer_for_assignment,
)


@pytest.fixture
def smart_assignment_env(app):
    """Seed test environment with 2 active officers, 1 inactive officer, an admin, and 2 institutions."""
    inst_1 = Institution(
        institution_code="AICTE-SMART-001",
        name="Smart Engineering Institute",
        contact_email="principal@smart1.edu",
    )
    inst_2 = Institution(
        institution_code="AICTE-SMART-002",
        name="Apex Polytechnic",
        contact_email="principal@smart2.edu",
    )
    db.session.add_all([inst_1, inst_2])
    db.session.commit()

    inst_user = User(
        full_name="Principal Smart",
        email="principal@smart1.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_1.id,
        is_active=True,
    )
    inst_user.set_password("SecurePass123!")

    officer_a = User(
        full_name="Officer Alpha",
        email="officer.a@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer_a.set_password("OfficerPass123!")

    officer_b = User(
        full_name="Officer Beta",
        email="officer.b@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer_b.set_password("OfficerPass123!")

    officer_inactive = User(
        full_name="Officer Gamma Inactive",
        email="officer.c@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=False,
    )
    officer_inactive.set_password("OfficerPass123!")

    admin = User(
        full_name="Admin Director",
        email="director@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([inst_user, officer_a, officer_b, officer_inactive, admin])
    db.session.commit()

    # Create FDR records with various maturity dates
    fdr_critical = FDRRecord(
        institution_id=inst_1.id,
        created_by=inst_user.id,
        fdr_number="FDR-CRIT-001",
        bank_name="State Bank of India",
        branch_name="Branch 1",
        amount=Decimal("1000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=4),  # <= 7 days -> CRITICAL
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.EXPIRING_SOON.value,
    )
    fdr_high = FDRRecord(
        institution_id=inst_1.id,
        created_by=inst_user.id,
        fdr_number="FDR-HIGH-002",
        bank_name="Punjab National Bank",
        branch_name="Branch 2",
        amount=Decimal("1500000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=12),  # <= 15 days -> HIGH
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.EXPIRING_SOON.value,
    )
    fdr_medium = FDRRecord(
        institution_id=inst_2.id,
        created_by=inst_user.id,
        fdr_number="FDR-MED-003",
        bank_name="Bank of Baroda",
        branch_name="Branch 3",
        amount=Decimal("2000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=35),  # 15 < days <= 60 -> MEDIUM
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
    )
    fdr_low = FDRRecord(
        institution_id=inst_2.id,
        created_by=inst_user.id,
        fdr_number="FDR-LOW-004",
        bank_name="Canara Bank",
        branch_name="Branch 4",
        amount=Decimal("500000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=120),  # > 60 days -> LOW
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
    )

    db.session.add_all([fdr_critical, fdr_high, fdr_medium, fdr_low])
    db.session.commit()

    return {
        "inst_1": inst_1,
        "inst_2": inst_2,
        "inst_user": inst_user,
        "officer_a": officer_a,
        "officer_b": officer_b,
        "officer_inactive": officer_inactive,
        "admin": admin,
        "fdr_critical": fdr_critical,
        "fdr_high": fdr_high,
        "fdr_medium": fdr_medium,
        "fdr_low": fdr_low,
    }


def login(client, email, password):
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200
    token_res = client.get("/api/auth/csrf-token")
    return token_res.get_json()["csrf_token"]


def test_dynamic_priority_calculation(smart_assignment_env):
    """Verify CRITICAL, HIGH, MEDIUM, and LOW priority calculation and reasons."""
    env = smart_assignment_env

    # 1. Critical petition: FDR maturing in 4 days
    req_crit = FDRRequest(
        fdr_id=env["fdr_critical"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Matures very soon",
        status="Submitted",
    )
    db.session.add(req_crit)
    db.session.commit()

    assert req_crit.priority == "CRITICAL"
    assert "7 days" in req_crit.priority_reason or "7-day" in req_crit.priority_reason or "Emergency" in req_crit.priority_reason or "matures" in req_crit.priority_reason.lower()

    # 2. High priority: FDR maturing in 12 days
    req_high = FDRRequest(
        fdr_id=env["fdr_high"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Matures in 12 days",
        status="Submitted",
    )
    db.session.add(req_high)
    db.session.commit()

    assert req_high.priority == "HIGH"
    assert "15-day" in req_high.priority_reason or "15 days" in req_high.priority_reason or "12 day" in req_high.priority_reason

    # 3. Medium priority: FDR maturing in 35 days, recently submitted
    req_med = FDRRequest(
        fdr_id=env["fdr_medium"].id,
        institution_id=env["inst_2"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Matures in 35 days",
        status="Submitted",
    )
    db.session.add(req_med)
    db.session.commit()

    assert req_med.priority == "MEDIUM"

    # 4. Low priority pending: FDR maturing in 120 days with plenty of buffer
    req_low = FDRRequest(
        fdr_id=env["fdr_low"].id,
        institution_id=env["inst_2"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Matures in 120 days",
        status="Submitted",
    )
    db.session.add(req_low)
    db.session.commit()

    assert req_low.priority == "LOW"

    # 5. Overdue petition: submitted > 14 days ago even if FDR maturity is far
    req_overdue = FDRRequest(
        fdr_id=env["fdr_medium"].id,
        institution_id=env["inst_2"].id,
        created_by=env["inst_user"].id,
        request_type="CLOSURE",
        reason="Overdue pending petition",
        status="Submitted",
        created_at=datetime.now(timezone.utc) - timedelta(days=20),
    )
    db.session.add(req_overdue)
    db.session.commit()

    assert req_overdue.is_overdue is True
    assert req_overdue.priority == "HIGH"
    assert "14-day" in req_overdue.priority_reason or "20 days" in req_overdue.priority_reason or "overdue" in req_overdue.priority_reason.lower()

    # 6. Completed petition (Approved / Rejected) -> LOW
    req_done = FDRRequest(
        fdr_id=env["fdr_critical"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Already processed",
        status="Approved",
    )
    db.session.add(req_done)
    db.session.commit()

    assert req_done.priority == "LOW"


def test_workload_balanced_auto_assignment(smart_assignment_env):
    """Verify that auto-assignment selects eligible active officers with lowest pending workload."""
    env = smart_assignment_env
    officer_a = env["officer_a"]
    officer_b = env["officer_b"]

    # Give officer A 2 pending petitions
    req1 = FDRRequest(
        fdr_id=env["fdr_medium"].id,
        institution_id=env["inst_2"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Case 1 for A",
        status="Under Review",
        assigned_to=officer_a.id,
    )
    req2 = FDRRequest(
        fdr_id=env["fdr_medium"].id,
        institution_id=env["inst_2"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Case 2 for A",
        status="Submitted",
        assigned_to=officer_a.id,
    )
    # Officer B has 0 pending petitions
    db.session.add_all([req1, req2])
    db.session.commit()

    assert get_officer_active_workload(officer_a.id) == 2
    assert get_officer_active_workload(officer_b.id) == 0

    # Best officer should be Officer B
    best = select_best_officer_for_assignment()
    assert best is not None
    assert best.id == officer_b.id

    # Create unassigned petition and auto-assign
    new_req = FDRRequest(
        fdr_id=env["fdr_critical"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Urgent auto-assignment test",
        status="Submitted",
    )
    db.session.add(new_req)
    db.session.commit()

    success, msg, assigned_officer = auto_assign_petition(new_req)
    assert success is True
    assert assigned_officer.id == officer_b.id
    assert new_req.assigned_to == officer_b.id

    # Check assignment history record
    history_entries = PetitionAssignmentHistory.query.filter_by(request_id=new_req.id).all()
    assert len(history_entries) == 1
    assert history_entries[0].new_officer_id == officer_b.id
    assert history_entries[0].assignment_type in ("AUTO_ASSIGNMENT", "AUTO_BALANCED")

    # Idempotence: Calling auto_assign_petition again returns existing officer and doesn't reassign
    second_success, _, second_run = auto_assign_petition(new_req)
    assert second_run.id == officer_b.id
    assert len(PetitionAssignmentHistory.query.filter_by(request_id=new_req.id).all()) == 1


def test_manual_reassignment_with_history(smart_assignment_env):
    """Verify admin can reassign a petition and create an immutable audit record."""
    env = smart_assignment_env
    officer_a = env["officer_a"]
    officer_b = env["officer_b"]
    admin = env["admin"]

    req = FDRRequest(
        fdr_id=env["fdr_medium"].id,
        institution_id=env["inst_2"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Reassignment test",
        status="Submitted",
        assigned_to=officer_a.id,
    )
    db.session.add(req)
    db.session.commit()

    # Admin reassigns to Officer B with explicit reason
    success, msg, reassigned = reassign_petition(
        req,
        new_officer_id=officer_b.id,
        assigned_by_user=admin,
        reason="Workload rebalancing due to urgent queue",
    )
    assert success is True
    assert reassigned.id == officer_b.id
    assert req.assigned_to == officer_b.id

    history_records = (
        PetitionAssignmentHistory.query.filter_by(request_id=req.id)
        .order_by(PetitionAssignmentHistory.id.desc())
        .all()
    )
    assert len(history_records) >= 1
    latest = history_records[0]
    assert latest.previous_officer_id == officer_a.id
    assert latest.new_officer_id == officer_b.id
    assert latest.assigned_by_id == admin.id
    assert latest.assignment_type in ("REASSIGNMENT", "MANUAL_REASSIGNMENT")
    assert "Workload rebalancing" in latest.reason


def test_permission_isolation_for_institution(client, smart_assignment_env):
    """Verify institutions cannot access internal assignment history or officer workload."""
    env = smart_assignment_env

    req = FDRRequest(
        fdr_id=env["fdr_critical"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Isolation test",
        status="Submitted",
        assigned_to=env["officer_a"].id,
    )
    db.session.add(req)
    db.session.commit()

    # Login as Institution
    csrf_inst = login(client, "principal@smart1.edu", "SecurePass123!")

    # 1. Institution detail fetch does NOT contain assignment_history
    detail_resp = client.get(f"/api/requests/{req.id}")
    assert detail_resp.status_code == 200
    req_data = detail_resp.get_json()["data"]
    assert "assignment_history" not in req_data or len(req_data.get("assignment_history", [])) == 0

    # 2. Dedicated assignment-history endpoint forbids institution
    hist_resp = client.get(f"/api/requests/{req.id}/assignment-history")
    assert hist_resp.status_code == 403

    # 3. Dedicated auto-assign-unassigned batch endpoint forbids institution
    auto_resp = client.post("/api/requests/auto-assign-unassigned", headers={"X-CSRF-Token": csrf_inst})
    assert auto_resp.status_code == 403


def test_admin_workload_metrics_and_batch_assignment(client, smart_assignment_env):
    """Verify batch auto-assignment and admin workload calculation."""
    env = smart_assignment_env
    admin = env["admin"]

    # Create 2 unassigned petitions
    req_u1 = FDRRequest(
        fdr_id=env["fdr_critical"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Unassigned 1",
        status="Submitted",
        assigned_to=None,
    )
    req_u2 = FDRRequest(
        fdr_id=env["fdr_high"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="CLOSURE",
        reason="Unassigned 2",
        status="Submitted",
        assigned_to=None,
    )
    db.session.add_all([req_u1, req_u2])
    db.session.commit()

    # Login as Admin
    csrf_admin = login(client, "director@aicte.gov.in", "AdminPass123!")

    # Run batch auto-assignment
    batch_resp = client.post(
        "/api/requests/auto-assign-unassigned",
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert batch_resp.status_code == 200
    b_data = batch_resp.get_json()
    assert b_data["successfully_assigned"] >= 2

    # Check admin dashboard returns workload metrics
    dash_resp = client.get("/api/dashboard/admin")
    assert dash_resp.status_code == 200
    resp_data = dash_resp.get_json()["data"]
    workload = resp_data["workload_metrics"]
    assert workload["total_active_officers"] >= 2  # active officers and admins, excluding inactive
    assert "officers_workload" in workload
    assert len(workload["officers_workload"]) >= 2
    assert "workload_share_pct" in workload["officers_workload"][0]


def test_watchdog_scanner_deduplication(smart_assignment_env):
    """Verify the alert scanner detects critical/overdue cases without duplicate notifications."""
    env = smart_assignment_env

    # Critical request assigned to officer A
    req_alert = FDRRequest(
        fdr_id=env["fdr_critical"].id,
        institution_id=env["inst_1"].id,
        created_by=env["inst_user"].id,
        request_type="RENEWAL",
        reason="Escalation test",
        status="Submitted",
        assigned_to=env["officer_a"].id,
    )
    db.session.add(req_alert)
    db.session.commit()

    # First run of scanner
    res1 = scan_and_alert_critical_and_overdue_petitions()
    assert res1["critical_alerts_sent"] >= 1

    # Second run should deduplicate and send 0 duplicates
    res2 = scan_and_alert_critical_and_overdue_petitions()
    assert res2["critical_alerts_sent"] == 0
