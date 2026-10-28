from datetime import date
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.enums import NotificationType, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.user import User


@pytest.fixture
def seed_api_env(app):
    """Seed institutions, users across roles, baseline FDRs, and supporting documents."""
    inst_a = Institution(
        institution_code="AICTE-API-A",
        name="Apex College of Technology",
        contact_email="contact@apex.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-API-B",
        name="Zenith Institute of Engineering",
        contact_email="contact@zenith.edu",
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
    fdr_draft = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-API-DRAFT-01",
        bank_name="State Bank of India",
        branch_name="Main Campus Branch",
        amount=Decimal("1000000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    # Submitted FDR for Institution A
    fdr_submitted = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-API-SUB-01",
        bank_name="Punjab National Bank",
        branch_name="Tech Zone",
        amount=Decimal("1500000.00"),
        issue_date=date(2025, 2, 1),
        maturity_date=date(2030, 2, 1),
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    # Under Review FDR for Institution A
    fdr_review = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-API-REVIEW-01",
        bank_name="Canara Bank",
        branch_name="Metro City",
        amount=Decimal("800000.00"),
        issue_date=date(2025, 3, 1),
        maturity_date=date(2030, 3, 1),
        scrutiny_status=ScrutinyStatus.PENDING_VERIFICATION.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    # Returned FDR for Institution A
    fdr_returned = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-API-RET-01",
        bank_name="Union Bank",
        branch_name="Civil Lines",
        amount=Decimal("500000.00"),
        issue_date=date(2025, 4, 1),
        maturity_date=date(2030, 4, 1),
        scrutiny_status=ScrutinyStatus.RETURNED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    # Institution B FDR (for cross-tenant tests)
    fdr_b = FDRRecord(
        institution_id=inst_b.id,
        fdr_number="FDR-API-INST-B-01",
        bank_name="HDFC Bank",
        branch_name="Sector 18",
        amount=Decimal("2000000.00"),
        issue_date=date(2025, 5, 1),
        maturity_date=date(2032, 5, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_b.id,
    )

    db.session.add_all([fdr_draft, fdr_submitted, fdr_review, fdr_returned, fdr_b])
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
        "fdr_draft": fdr_draft,
        "fdr_submitted": fdr_submitted,
        "fdr_review": fdr_review,
        "fdr_returned": fdr_returned,
        "fdr_b": fdr_b,
    }


def login_and_get_csrf(client, email, password):
    """Helper to authenticate and extract session CSRF token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def attach_document(fdr_id, uploaded_by):
    """Helper to seed a supporting document for an FDR record."""
    doc = Document(
        fdr_id=fdr_id,
        original_filename="fdr_scan.pdf",
        stored_filename=fdr_id.__str__() + "_stored_scan.pdf",
        file_type="application/pdf",
        file_size=125000,
        processing_status="PROCESSED",
        uploaded_by=uploaded_by,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


# =====================================================================
# 1. Institution Submission & Resubmission Endpoints
# =====================================================================


def test_submit_fdr_missing_document_validation(client, seed_api_env):
    """Test that submitting an FDR without any supporting document uploaded returns 400."""
    env = seed_api_env
    csrf = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    # Attempt submission without attaching document
    res = client.post(
        f"/api/fdr/{env['fdr_draft'].id}/submit",
        json={"remarks": "Initial submission"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["code"] == "VALIDATION_ERROR"
    assert "documents" in data["details"]


def test_submit_fdr_draft_success(client, seed_api_env):
    """Test successful submission of DRAFT FDR by institution user when document is attached."""
    env = seed_api_env
    fdr = env["fdr_draft"]
    attach_document(fdr.id, env["user_a"].id)

    csrf = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    res = client.post(
        f"/api/fdr/{fdr.id}/submit",
        json={"remarks": "Ready for verification"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["scrutiny_status"] == "SUBMITTED"

    # Verify audit log and notification
    audit = AuditLog.query.filter_by(
        entity_id=fdr.id, action="SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED"
    ).first()
    assert audit is not None


def test_resubmit_returned_fdr_success(client, seed_api_env):
    """Test successful resubmission of RETURNED FDR by institution user."""
    env = seed_api_env
    fdr = env["fdr_returned"]
    attach_document(fdr.id, env["user_a"].id)

    csrf = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    res = client.post(
        f"/api/fdr/{fdr.id}/submit",
        json={"remarks": "Attached attested bank seal"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["scrutiny_status"] == "SUBMITTED"


# =====================================================================
# 2. Officer Review & Decision Endpoints
# =====================================================================


def test_officer_start_review_success(client, seed_api_env):
    """Test AICTE officer transitions SUBMITTED FDR into PENDING_VERIFICATION."""
    env = seed_api_env
    fdr = env["fdr_submitted"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    res = client.post(
        f"/api/fdr/{fdr.id}/start-review",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["scrutiny_status"] == "PENDING_VERIFICATION"


def test_officer_verify_success(client, seed_api_env):
    """Test AICTE officer approves and verifies an FDR in PENDING_VERIFICATION."""
    env = seed_api_env
    fdr = env["fdr_review"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    res = client.post(
        f"/api/fdr/{fdr.id}/verify",
        json={"remarks": "Joint lien verified with bank manager."},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["scrutiny_status"] == "VERIFIED"


def test_officer_return_with_mandatory_reason(client, seed_api_env):
    """Test AICTE officer returns an FDR with mandatory remarks."""
    env = seed_api_env
    fdr = env["fdr_review"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    reason = "Official bank seal is blurred. Please upload clear scan."
    res = client.post(
        f"/api/fdr/{fdr.id}/return",
        json={"reason": reason},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["scrutiny_status"] == "RETURNED"
    assert data["reason"] == reason


def test_officer_reject_with_mandatory_reason(client, seed_api_env):
    """Test AICTE officer rejects an FDR with mandatory remarks."""
    env = seed_api_env
    fdr = env["fdr_review"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    reason = "FDR already matured and encashed prior to submission."
    res = client.post(
        f"/api/fdr/{fdr.id}/reject",
        json={"reason": reason},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["scrutiny_status"] == "REJECTED"
    assert data["reason"] == reason


# =====================================================================
# 3. Decision Remarks Validation Errors
# =====================================================================


def test_officer_return_missing_and_whitespace_remarks(client, seed_api_env):
    """Test that returning an FDR without reason or with whitespace-only returns 400."""
    env = seed_api_env
    fdr = env["fdr_review"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    # 1. Missing body/reason
    res1 = client.post(
        f"/api/fdr/{fdr.id}/return",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    assert res1.status_code == 400
    assert "remarks" in res1.get_json()["details"]

    # 2. Whitespace-only reason
    res2 = client.post(
        f"/api/fdr/{fdr.id}/return",
        json={"reason": "   \n\t  "},
        headers={"X-CSRF-Token": csrf},
    )
    assert res2.status_code == 400
    assert "remarks" in res2.get_json()["details"]


def test_officer_return_oversized_remarks(client, seed_api_env):
    """Test that remarks exceeding 2000 characters return 400 validation error."""
    env = seed_api_env
    fdr = env["fdr_review"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    too_long = "X" * 2001
    res = client.post(
        f"/api/fdr/{fdr.id}/return",
        json={"reason": too_long},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 400
    assert "2000" in res.get_json()["details"]["remarks"]


# =====================================================================
# 4. Role Permissions & Workflow Integrity
# =====================================================================


def test_institution_user_cannot_perform_officer_actions(client, seed_api_env):
    """Verify that institution users receive 403 when attempting officer actions."""
    env = seed_api_env
    fdr_sub = env["fdr_submitted"]
    fdr_rev = env["fdr_review"]

    csrf = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    # Cannot start review
    res_start = client.post(
        f"/api/fdr/{fdr_sub.id}/start-review",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_start.status_code == 403

    # Cannot verify
    res_verify = client.post(
        f"/api/fdr/{fdr_rev.id}/verify",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_verify.status_code == 403

    # Cannot return
    res_return = client.post(
        f"/api/fdr/{fdr_rev.id}/return",
        json={"reason": "Self-return"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res_return.status_code == 403

    # Cannot reject
    res_reject = client.post(
        f"/api/fdr/{fdr_rev.id}/reject",
        json={"reason": "Self-reject"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res_reject.status_code == 403


def test_officer_cannot_submit_on_behalf_of_institution(client, seed_api_env):
    """Verify that officers cannot submit draft FDRs on behalf of institutions."""
    env = seed_api_env
    fdr = env["fdr_draft"]
    attach_document(fdr.id, env["user_a"].id)

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    res = client.post(
        f"/api/fdr/{fdr.id}/submit",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 403


def test_invalid_transition_matrix_bypasses(client, seed_api_env):
    """Verify that jumping statuses (e.g. DRAFT -> VERIFIED) returns 400 INVALID_TRANSITION."""
    env = seed_api_env
    fdr_draft = env["fdr_draft"]

    csrf = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")

    # Officer tries to verify a DRAFT directly without SUBMITTED and PENDING_VERIFICATION
    res = client.post(
        f"/api/fdr/{fdr_draft.id}/verify",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 400
    assert res.get_json()["code"] == "INVALID_TRANSITION"


# =====================================================================
# 5. Cross-Tenant Isolation & Authentication / CSRF Security
# =====================================================================


def test_cross_tenant_isolation(client, seed_api_env):
    """Verify that an institution user receives 404 when attempting actions on another institution's FDR."""
    env = seed_api_env
    fdr_b = env["fdr_b"]  # Belongs to Zenith Institute

    csrf_a = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    # User A tries to submit User B's FDR
    res = client.post(
        f"/api/fdr/{fdr_b.id}/submit",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert res.status_code == 404

    # User A tries to get workflow status of User B's FDR
    res_wf = client.get(
        f"/api/fdr/{fdr_b.id}/workflow",
    )
    assert res_wf.status_code == 404


def test_unauthenticated_and_csrf_enforcement(client, seed_api_env):
    """Verify unauthenticated access returns 401 and POST without CSRF returns 403."""
    fdr_id = seed_api_env["fdr_draft"].id

    # 1. Unauthenticated requests
    assert client.post(f"/api/fdr/{fdr_id}/submit").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/start-review").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/verify").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/return").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/reject").status_code == 401
    assert client.get(f"/api/fdr/{fdr_id}/workflow").status_code == 401

    # 2. Authenticated but missing CSRF token
    login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")
    res_no_csrf = client.post(f"/api/fdr/{fdr_id}/submit")
    assert res_no_csrf.status_code == 403
    assert res_no_csrf.get_json()["code"] == "CSRF_ERROR"


# =====================================================================
# 6. Workflow Status & Available Actions Endpoint
# =====================================================================


def test_workflow_endpoint_available_actions_and_history(client, seed_api_env):
    """Test GET /api/fdr/<id>/workflow returns accurate available actions and audit history."""
    env = seed_api_env
    fdr = env["fdr_draft"]
    attach_document(fdr.id, env["user_a"].id)

    # 1. As Institution User for DRAFT FDR:
    login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")
    res1 = client.get(f"/api/fdr/{fdr.id}/workflow")
    assert res1.status_code == 200
    data1 = res1.get_json()["data"]
    assert data1["scrutiny_status"] == "DRAFT"
    assert data1["validity_status"] == "ACTIVE"
    assert data1["is_authorized"] is True
    assert "submit" in data1["available_actions"]

    # 2. Submit the FDR:
    csrf_inst = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")
    client.post(f"/api/fdr/{fdr.id}/submit", headers={"X-CSRF-Token": csrf_inst})

    # 3. As Officer for SUBMITTED FDR:
    login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")
    res2 = client.get(f"/api/fdr/{fdr.id}/workflow")
    assert res2.status_code == 200
    data2 = res2.get_json()["data"]
    assert data2["scrutiny_status"] == "SUBMITTED"
    assert data2["available_actions"] == ["start-review"]
    assert len(data2["workflow_history"]) == 1
    assert data2["workflow_history"][0]["action"] == "SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED"

    # 4. Officer starts review:
    csrf_officer = login_and_get_csrf(client, "officer.scrutiny@aicte.gov.in", "OfficerPass123!")
    client.post(f"/api/fdr/{fdr.id}/start-review", headers={"X-CSRF-Token": csrf_officer})

    # 5. As Officer for PENDING_VERIFICATION FDR:
    res3 = client.get(f"/api/fdr/{fdr.id}/workflow")
    data3 = res3.get_json()["data"]
    assert data3["scrutiny_status"] == "PENDING_VERIFICATION"
    assert set(data3["available_actions"]) == {"verify", "return", "reject"}
    assert len(data3["workflow_history"]) == 2
