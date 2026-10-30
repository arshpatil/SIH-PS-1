from datetime import date
from decimal import Decimal
import io
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.user import User


@pytest.fixture
def req_env(app):
    """Seed testing environment for petition lifecycle tests."""
    inst_a = Institution(
        institution_code="AICTE-REQ-A",
        name="Aryabhatta Engineering College",
        contact_email="principal@aryabhatta.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-REQ-B",
        name="Bhaskara Institute",
        contact_email="principal@bhaskara.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    user_a = User(
        full_name="Registrar Aryabhatta",
        email="user_a@aryabhatta.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a.set_password("AryaPass123!")

    user_b = User(
        full_name="Registrar Bhaskara",
        email="user_b@bhaskara.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_b.id,
        is_active=True,
    )
    user_b.set_password("BhaskaraPass123!")

    officer = User(
        full_name="AICTE Verification Officer",
        email="officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="AICTE Portal Administrator",
        email="admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([user_a, user_b, officer, admin])
    db.session.commit()

    # Create verified FDR for institution A
    fdr_verified = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-REQ-TEST-101",
        bank_name="State Bank of India",
        branch_name="Main University Branch",
        amount=Decimal("2500000.00"),
        issue_date=date(2023, 1, 1),
        maturity_date=date(2028, 1, 1),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    db.session.add(fdr_verified)
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
        "fdr_verified": fdr_verified,
    }


def login_client(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def test_full_request_lifecycle(client, req_env):
    """Test complete lifecycle: Submitted -> Under Review -> Documents Required -> Resubmitted -> Approved -> Closed."""
    env = req_env
    csrf_inst = login_client(client, "user_a@aryabhatta.edu", "AryaPass123!")

    # 1. Institution creates Renewal petition
    payload = {
        "fdr_id": env["fdr_verified"].id,
        "request_type": "Renewal",
        "reason": "Requesting 5-year term extension with State Bank of India.",
        "supporting_document": "renewal_application.pdf",
    }
    res_create = client.post("/api/requests", json=payload, headers={"X-CSRF-Token": csrf_inst})
    assert res_create.status_code == 201
    req_id = res_create.get_json()["data"]["raw_id"]

    # 2. Prevent duplicate active request of same type
    res_dup = client.post("/api/requests", json=payload, headers={"X-CSRF-Token": csrf_inst})
    assert res_dup.status_code == 409
    assert res_dup.get_json()["code"] == "DUPLICATE_ACTIVE_REQUEST"

    # 3. Officer logs in and transitions to 'Under Review'
    csrf_officer = login_client(client, "officer@aicte.gov.in", "OfficerPass123!")
    res_review = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Under Review", "remarks": "Review started at scrutiny desk."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_review.status_code == 200
    assert res_review.get_json()["data"]["status"] == "Under Review"

    # 4. Officer requests additional documents (Mandatory remarks check)
    res_fail_remarks = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Documents Required", "remarks": ""},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_fail_remarks.status_code == 400
    assert res_fail_remarks.get_json()["code"] == "REMARKS_REQUIRED"

    res_doc_req = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Documents Required", "remarks": "Please provide latest bank ledger statement and lien certificate."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_doc_req.status_code == 200
    assert res_doc_req.get_json()["data"]["status"] == "Documents Required"

    # 5. Institution resubmits petition with requested file
    csrf_inst = login_client(client, "user_a@aryabhatta.edu", "AryaPass123!")
    fake_pdf = io.BytesIO(b"%PDF-1.4 Fake bank statement")
    res_resubmit = client.post(
        f"/api/requests/{req_id}/resubmit",
        data={
            "file": (fake_pdf, "bank_statement_signed.pdf"),
            "remarks": "Attached certified bank ledger statement as requested.",
        },
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert res_resubmit.status_code == 200
    assert res_resubmit.get_json()["data"]["status"] == "Resubmitted / Awaiting Review"

    # 6. Officer approves request
    csrf_officer = login_client(client, "officer@aicte.gov.in", "OfficerPass123!")
    res_approve = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "All documents verified. Term extension approved."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_approve.status_code == 200
    assert res_approve.get_json()["data"]["status"] == "Approved"

    # 7. Close petition
    res_close = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Closed", "remarks": "Formal certificate issued. Case closed."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_close.status_code == 200
    assert res_close.get_json()["data"]["status"] == "Closed"

    # Verify audit trail
    history_res = client.get(f"/api/requests/{req_id}")
    assert history_res.status_code == 200
    audit_history = history_res.get_json()["data"]["history"]
    assert len(audit_history) >= 4


def test_admin_case_assignment(client, req_env):
    """Test admin assigning a petition to an officer with audit trail."""
    env = req_env
    csrf_inst = login_client(client, "user_a@aryabhatta.edu", "AryaPass123!")

    # Create request
    payload = {
        "fdr_id": env["fdr_verified"].id,
        "request_type": "Release",
        "reason": "Course discontinuation approved; requesting security deposit lien release.",
    }
    res_create = client.post("/api/requests", json=payload, headers={"X-CSRF-Token": csrf_inst})
    assert res_create.status_code == 201
    req_id = res_create.get_json()["data"]["raw_id"]

    # Institution cannot assign
    res_unauth = client.patch(
        f"/api/requests/{req_id}/assign",
        json={"officer_id": env["officer"].id},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert res_unauth.status_code == 403

    # Admin assigns to officer
    csrf_admin = login_client(client, "admin@aicte.gov.in", "AdminPass123!")
    res_assign = client.patch(
        f"/api/requests/{req_id}/assign",
        json={"officer_id": env["officer"].id},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res_assign.status_code == 200
    data = res_assign.get_json()["data"]
    assert data["assignedTo"] == env["officer"].id
    assert data["assignedOfficerName"] == env["officer"].full_name

    # Verify notification sent to assigned officer
    notif = Notification.query.filter_by(user_id=env["officer"].id).first()
    assert notif is not None
    assert f"REQ-{req_id:04d}" in notif.title or f"REQ-{req_id:04d}" in notif.message


def test_request_stats_endpoint(client, req_env):
    """Verify /api/requests/stats aggregation and overdue detection."""
    csrf_admin = login_client(client, "admin@aicte.gov.in", "AdminPass123!")
    res = client.get("/api/requests/stats", headers={"X-CSRF-Token": csrf_admin})
    assert res.status_code == 200
    stats = res.get_json()["stats"]
    assert "total" in stats
    assert "submitted" in stats
    assert "under_review" in stats
    assert "overdue" in stats


def test_request_formatted_id_resolution(client, req_env):
    """Verify that petition endpoints accept both integer and formatted 'REQ-0001' string IDs."""
    env = req_env
    csrf_inst = login_client(client, "user_a@aryabhatta.edu", "AryaPass123!")

    # Create petition
    payload = {
        "fdr_id": env["fdr_verified"].id,
        "request_type": "Renewal",
        "reason": "Test renewal with formatted string ID resolution.",
    }
    res_create = client.post("/api/requests", json=payload, headers={"X-CSRF-Token": csrf_inst})
    assert res_create.status_code == 201
    formatted_id = res_create.get_json()["data"]["id"]  # e.g. "REQ-0001"
    raw_id = res_create.get_json()["data"]["raw_id"]

    # 1. GET with formatted ID
    res_get_fmt = client.get(f"/api/requests/{formatted_id}")
    assert res_get_fmt.status_code == 200
    assert res_get_fmt.get_json()["data"]["raw_id"] == raw_id

    # 2. PATCH status with formatted ID
    csrf_officer = login_client(client, "officer@aicte.gov.in", "OfficerPass123!")
    res_status_fmt = client.patch(
        f"/api/requests/{formatted_id}/status",
        json={"status": "Under Review", "remarks": "Review started using formatted ID."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_status_fmt.status_code == 200
    assert res_status_fmt.get_json()["data"]["status"] == "Under Review"

    # 3. PATCH assign with formatted ID
    csrf_admin = login_client(client, "admin@aicte.gov.in", "AdminPass123!")
    res_assign_fmt = client.patch(
        f"/api/requests/{formatted_id}/assign",
        json={"officer_id": env["officer"].id},
        headers={"X-CSRF-Token": csrf_admin},
    )
    assert res_assign_fmt.status_code == 200
    assert res_assign_fmt.get_json()["data"]["assignedTo"] == env["officer"].id


def test_maturity_bracket_aliases(client, req_env):
    """Verify maturity bracket filters '90D', '60D', '30D', '7D', 'ACTIVE' work in list_authorized_fdrs."""
    from datetime import timedelta
    from app.services.fdr_service import list_authorized_fdrs
    from app.services.maturity_service import get_business_date
    ref_d = get_business_date()
    env = req_env
    user = env["admin"]

    # Create FDRs across different maturity horizons
    fdr_30d = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-30D-TEST",
        bank_name="Test Bank",
        branch_name="Branch",
        amount=Decimal("100000.00"),
        issue_date=ref_d - timedelta(days=365),
        maturity_date=ref_d + timedelta(days=20),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a"].id,
    )
    fdr_active = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-ACTIVE-TEST",
        bank_name="Test Bank",
        branch_name="Branch",
        amount=Decimal("100000.00"),
        issue_date=ref_d - timedelta(days=365),
        maturity_date=ref_d + timedelta(days=120),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a"].id,
    )
    db.session.add_all([fdr_30d, fdr_active])
    db.session.commit()

    # Query with 30D bracket
    res_30d, _ = list_authorized_fdrs(user, {"maturity_bracket": "30D"})
    fdr_numbers_30d = [f.fdr_number for f in res_30d]
    assert "FDR-30D-TEST" in fdr_numbers_30d
    assert "FDR-ACTIVE-TEST" not in fdr_numbers_30d

    # Query with ACTIVE bracket
    res_active, _ = list_authorized_fdrs(user, {"maturity_bracket": "ACTIVE"})
    fdr_numbers_active = [f.fdr_number for f in res_active]
    assert "FDR-ACTIVE-TEST" in fdr_numbers_active
    assert "FDR-30D-TEST" not in fdr_numbers_active
