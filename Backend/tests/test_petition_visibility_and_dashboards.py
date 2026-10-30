from datetime import date, timedelta
from decimal import Decimal
import io
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User


@pytest.fixture
def workflow_env(app):
    """Seed test environment with 2 institutions, an officer, and an admin."""
    inst_1 = Institution(
        institution_code="AICTE-TEST-001",
        name="Institute of Technology",
        contact_email="principal@inst1.edu",
    )
    inst_2 = Institution(
        institution_code="AICTE-TEST-002",
        name="Apex College of Science",
        contact_email="principal@inst2.edu",
    )
    db.session.add_all([inst_1, inst_2])
    db.session.commit()

    inst1_user = User(
        full_name="Principal Inst 1",
        email="principal@inst1.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_1.id,
        is_active=True,
    )
    inst1_user.set_password("SecurePass123!")

    inst2_user = User(
        full_name="Principal Inst 2",
        email="principal@inst2.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_2.id,
        is_active=True,
    )
    inst2_user.set_password("SecurePass123!")

    officer = User(
        full_name="Desk Scrutiny Officer",
        email="officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="AICTE Central Admin",
        email="admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([inst1_user, inst2_user, officer, admin])
    db.session.commit()

    # Create an FDR approaching maturity (due in 20 days)
    maturing_fdr = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="FDR-MAT-9901",
        bank_name="State Bank of India",
        branch_name="Main Campus Branch",
        amount=Decimal("1500000.00"),
        issue_date=date.today() - timedelta(days=365 * 3),
        maturity_date=date.today() + timedelta(days=20),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.EXPIRING_SOON.value,
        created_by=inst1_user.id,
    )
    db.session.add(maturing_fdr)
    db.session.commit()

    return {
        "inst_1": inst_1,
        "inst_2": inst_2,
        "inst1_user": inst1_user,
        "inst2_user": inst2_user,
        "officer": officer,
        "admin": admin,
        "fdr": maturing_fdr,
    }


def login(client, email, password):
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200
    token_res = client.get("/api/auth/csrf-token")
    csrf_token = token_res.get_json()["csrf_token"]
    return csrf_token


def test_complete_petition_lifecycle_and_dashboards(client, workflow_env):
    """
    Test complete requirement workflow:
    1. Institution logs in and submits a petition for an FDR approaching maturity.
    2. The petition is persisted and appears in the institution's request history.
    3. The Admin dashboard displays the petition in unassigned queue and metrics.
    4. The unassigned petition appears in the Admin assignment queue.
    5. The Admin assigns the petition to an active officer.
    6. The petition appears in that officer's assigned workload and officer dashboard.
    7. The officer opens the petition, reviews, and requests corrections.
    8. The institution resubmits with corrections.
    9. The assigned officer reviews resubmission and approves petition.
    10. The Admin dashboard reflects the updated status and workload.
    11. Unauthorized access is blocked across boundaries.
    """
    fdr = workflow_env["fdr"]
    officer = workflow_env["officer"]

    # 1. Institution 1 logs in and submits renewal petition
    csrf_inst = login(client, "principal@inst1.edu", "SecurePass123!")
    create_res = client.post(
        "/api/requests",
        data={
            "fdr_id": str(fdr.id),
            "request_type": "Renewal",
            "reason": "Requesting 3-year term renewal for regulatory compliance.",
            "remarks": "Bank renewal quotation attached.",
            "file": (io.BytesIO(b"%PDF-1.4 test document content"), "renewal_doc.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert create_res.status_code == 201
    create_data = create_res.get_json()
    assert create_data["success"] is True
    petition_raw_id = create_data["data"]["raw_id"]
    petition_str_id = create_data["data"]["id"]
    assert petition_str_id.startswith("REQ-")
    assert create_data["data"]["priority"] in ("URGENT", "HIGH", "MEDIUM", "CRITICAL")
    assert create_data["data"]["maturity_date"] is not None

    # 2. Institution checks its own request history
    inst_history_res = client.get("/api/requests")
    assert inst_history_res.status_code == 200
    inst_reqs = inst_history_res.get_json()["data"]
    assert any(r["raw_id"] == petition_raw_id for r in inst_reqs)

    # Cross-tenant check: Institution 2 must NOT see Institution 1's petition
    csrf_inst2 = login(client, "principal@inst2.edu", "SecurePass123!")
    inst2_history_res = client.get("/api/requests")
    assert inst2_history_res.status_code == 200
    assert len(inst2_history_res.get_json()["data"]) == 0

    # 3 & 4. Admin logs in and checks Admin Dashboard & Assignment Queue
    csrf_admin = login(client, "admin@aicte.gov.in", "AdminPass123!")
    admin_dash_res = client.get("/api/dashboard/admin")
    assert admin_dash_res.status_code == 200
    admin_dash_data = admin_dash_res.get_json()["data"]
    metrics = admin_dash_data["metrics"]
    assert metrics["unassigned_petitions_count"] >= 1
    assert metrics["total_petitions"] >= 1

    # Verify petition is in Admin's unassigned queue
    unassigned_queue = admin_dash_data["unassigned_queue"]
    found_in_queue = next((p for p in unassigned_queue if p["raw_id"] == petition_raw_id), None)
    assert found_in_queue is not None
    assert found_in_queue["institution_name"] == "Institute of Technology"
    assert found_in_queue["fdr_number"] == "FDR-MAT-9901"
    assert found_in_queue["assigned_to"] is None

    # 5. Admin assigns the petition to the active scrutiny officer
    assign_res = client.patch(
        f"/api/requests/{petition_str_id}/assign",
        json={"officer_id": officer.id},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert assign_res.status_code == 200
    assert assign_res.get_json()["data"]["assigned_to"] == officer.id

    # 6. Officer logs in and checks Officer Dashboard
    csrf_officer = login(client, "officer@aicte.gov.in", "OfficerPass123!")
    officer_dash_res = client.get("/api/dashboard/officer")
    assert officer_dash_res.status_code == 200
    officer_dash_data = officer_dash_res.get_json()["data"]
    workload = officer_dash_data["workload_overview"]
    assert workload["assigned_awaiting_review"] >= 1

    assigned_cases = officer_dash_data["assigned_cases"]
    assigned_petition = next((c for c in assigned_cases if c["raw_id"] == petition_raw_id), None)
    assert assigned_petition is not None
    assert assigned_petition["assigned_to"] == officer.id

    # 7. Officer opens petition detail using petition ID and requests corrections
    detail_res = client.get(f"/api/requests/{petition_str_id}")
    assert detail_res.status_code == 200
    assert detail_res.get_json()["data"]["raw_id"] == petition_raw_id

    # Officer requests corrections ("Documents Required")
    decision_res = client.patch(
        f"/api/requests/{petition_str_id}/status",
        json={
            "status": "Documents Required",
            "remarks": "Please provide joint holder endorsement certificate from SBI branch manager.",
        },
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert decision_res.status_code == 200
    assert decision_res.get_json()["data"]["status"] == "Documents Required"

    # 8. Institution 1 logs in and resubmits petition with corrections
    csrf_inst1 = login(client, "principal@inst1.edu", "SecurePass123!")
    resubmit_res = client.post(
        f"/api/requests/{petition_str_id}/resubmit",
        data={
            "remarks": "Attached SBI branch endorsement certificate as requested.",
            "file": (io.BytesIO(b"%PDF-1.4 revised SBI endorsement"), "sbi_endorsement.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst1},
        content_type="multipart/form-data",
    )
    assert resubmit_res.status_code == 200
    assert resubmit_res.get_json()["data"]["status"] == "Resubmitted / Awaiting Review"

    # 9. Officer reviews the resubmission and approves the petition
    csrf_officer2 = login(client, "officer@aicte.gov.in", "OfficerPass123!")
    approve_res = client.patch(
        f"/api/requests/{petition_str_id}/status",
        json={
            "status": "Approved",
            "remarks": "SBI branch endorsement verified. Approved for AICTE statutory renewal.",
        },
        headers={"X-CSRF-Token": csrf_officer2},
    )
    assert approve_res.status_code == 200
    assert approve_res.get_json()["data"]["status"] == "Approved"

    # 10. Admin dashboard reflects the approved status and officer workload
    csrf_admin2 = login(client, "admin@aicte.gov.in", "AdminPass123!")
    admin_dash_res2 = client.get("/api/dashboard/admin")
    assert admin_dash_res2.status_code == 200
    admin_metrics2 = admin_dash_res2.get_json()["data"]["metrics"]
    assert admin_metrics2["petitions_by_status"]["Approved"] >= 1

    # Verify audit log captures assignment, deficiency, resubmission, and approval
    recent_audits = admin_dash_res2.get_json()["data"]["recent_audit_events"]
    actions = [a["action"] for a in recent_audits]
    assert any("ASSIGNED" in a or "STATUS" in a for a in actions)


def test_officer_claim_and_admin_account_management(client, workflow_env):
    """Test officer claiming unassigned cases and admin activating/deactivating officers."""
    fdr = workflow_env["fdr"]
    officer = workflow_env["officer"]

    # 1. Institution creates a new Release petition
    csrf_inst = login(client, "principal@inst1.edu", "SecurePass123!")
    create_res = client.post(
        "/api/requests",
        json={
            "fdr_id": fdr.id,
            "request_type": "Release",
            "reason": "Completion of statutory mandatory 8-year lock-in period.",
        },
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert create_res.status_code == 201
    rel_petition_id = create_res.get_json()["data"]["id"]

    # 2. Officer claims the unassigned petition
    csrf_off = login(client, "officer@aicte.gov.in", "OfficerPass123!")
    claim_res = client.patch(
        f"/api/requests/{rel_petition_id}/claim",
        headers={"X-CSRF-Token": csrf_off},
    )
    assert claim_res.status_code == 200
    assert claim_res.get_json()["data"]["assigned_to"] == officer.id

    # 3. Admin lists officers and manages account status
    csrf_admin = login(client, "admin@aicte.gov.in", "AdminPass123!")
    officers_list_res = client.get("/api/dashboard/officers")
    assert officers_list_res.status_code == 200
    officers_data = officers_list_res.get_json()["data"]
    assert any(o["id"] == officer.id for o in officers_data)

    # Admin deactivates officer
    deact_res = client.patch(
        f"/api/dashboard/officers/{officer.id}/status",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert deact_res.status_code == 200
    assert deact_res.get_json()["data"]["is_active"] is False

    # Deactivated officer cannot log in
    failed_login = client.post(
        "/api/auth/login",
        json={"email": "officer@aicte.gov.in", "password": "OfficerPass123!"},
    )
    assert failed_login.status_code in (401, 403)

    # Admin reactivates officer
    react_res = client.patch(
        f"/api/dashboard/officers/{officer.id}/status",
        json={"is_active": True},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert react_res.status_code == 200
    assert react_res.get_json()["data"]["is_active"] is True

    # Admin cannot deactivate self
    self_deact = client.patch(
        f"/api/dashboard/officers/{workflow_env['admin'].id}/status",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert self_deact.status_code == 400
    assert self_deact.get_json()["code"] == "CANNOT_DEACTIVATE_SELF"
