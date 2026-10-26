from datetime import date
from decimal import Decimal
import io
import json
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.enums import NotificationType, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.user import User
from app.models.workflow_history import FDRWorkflowHistory
from app.services.scheduler import init_scheduler


@pytest.fixture
def seed_e2e_env(app):
    """Seed multi-institution environment with separate actors for comprehensive lifecycle and security testing."""
    # 1. Institutions
    inst_a = Institution(
        institution_code="AICTE-E2E-A",
        name="Apex College of Engineering",
        contact_email="contact@apex.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-E2E-B",
        name="Zenith Polytechnic Institute",
        contact_email="contact@zenith.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    # 2. Users
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
        full_name="AICTE Portal Administrator",
        email="admin.portal@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([user_a, user_b, officer, admin])
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
    }


def login_and_get_csrf(client, email, password):
    """Helper to authenticate a test client and retrieve session CSRF token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def create_fdr_and_upload_document(client, email, password, fdr_number="FDR-E2E-001"):
    """Helper for institution user to create a draft FDR and upload a valid PDF document."""
    csrf = login_and_get_csrf(client, email, password)

    # 1. Create FDR
    fdr_payload = {
        "fdr_number": fdr_number,
        "bank_name": "State Bank of India",
        "branch_name": "Connaught Place, New Delhi",
        "amount": "1200000.00",
        "issue_date": "2025-01-15",
        "maturity_date": "2030-01-15",
    }
    res_create = client.post(
        "/api/fdr",
        json=fdr_payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert res_create.status_code == 201
    fdr_id = res_create.get_json()["data"]["id"]

    # 2. Upload PDF document
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
    data = {
        "file": (io.BytesIO(pdf_bytes), "deposit_receipt.pdf", "application/pdf")
    }
    res_upload = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data=data,
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_upload.status_code == 201

    return fdr_id, csrf


# =====================================================================
# 1. End-to-End Scrutiny Lifecycle Scenarios
# =====================================================================


def test_e2e_scenario_a_successful_verification(client, seed_e2e_env):
    """
    Scenario A: Full happy-path lifecycle:
    DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> VERIFIED.
    Verifies state transitions, history rows, audit logs, and notifications.
    """
    env = seed_e2e_env

    # 1. Institution user creates draft and uploads document
    fdr_id, csrf_inst = create_fdr_and_upload_document(
        client, "registrar@apex.edu", "ApexPass123!", "FDR-E2E-A-01"
    )

    # 2. Check workflow status before submission
    res_wf1 = client.get(f"/api/fdr/{fdr_id}/workflow")
    assert res_wf1.status_code == 200
    wf1_data = res_wf1.get_json()["data"]
    assert wf1_data["scrutiny_status"] == "DRAFT"
    assert "submit" in wf1_data["available_actions"]
    assert len(wf1_data["workflow_history"]) == 0

    # 3. Institution user submits FDR
    res_sub = client.post(
        f"/api/fdr/{fdr_id}/submit",
        json={"remarks": "Initial submission for approval"},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert res_sub.status_code == 200
    assert res_sub.get_json()["data"]["scrutiny_status"] == "SUBMITTED"

    # 4. Officer reviews available actions
    csrf_officer = login_and_get_csrf(client, "officer.verif@aicte.gov.in", "OfficerPass123!")
    res_wf2 = client.get(f"/api/fdr/{fdr_id}/workflow")
    wf2_data = res_wf2.get_json()["data"]
    assert wf2_data["scrutiny_status"] == "SUBMITTED"
    assert wf2_data["available_actions"] == ["start-review"]

    # 5. Officer starts review (SUBMITTED -> PENDING_VERIFICATION)
    res_start = client.post(
        f"/api/fdr/{fdr_id}/start-review",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_start.status_code == 200
    assert res_start.get_json()["data"]["scrutiny_status"] == "PENDING_VERIFICATION"

    # 6. Officer checks available actions
    res_wf3 = client.get(f"/api/fdr/{fdr_id}/workflow")
    assert set(res_wf3.get_json()["data"]["available_actions"]) == {"verify", "return", "reject"}

    # 7. Officer approves and verifies FDR (PENDING_VERIFICATION -> VERIFIED)
    res_verify = client.post(
        f"/api/fdr/{fdr_id}/verify",
        json={"remarks": "Confirmed joint lien with SBI CP branch manager. All clauses verified."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_verify.status_code == 200
    assert res_verify.get_json()["data"]["scrutiny_status"] == "VERIFIED"

    # 8. Check final workflow state
    res_wf_final = client.get(f"/api/fdr/{fdr_id}/workflow")
    final_data = res_wf_final.get_json()["data"]
    assert final_data["scrutiny_status"] == "VERIFIED"
    assert final_data["validity_status"] == "ACTIVE"
    assert final_data["available_actions"] == []  # Terminal state: no further actions

    # Verify structured history: exactly 3 rows
    history = final_data["workflow_history"]
    assert len(history) == 3
    assert history[0]["from_status"] == "DRAFT" and history[0]["to_status"] == "SUBMITTED"
    assert history[1]["from_status"] == "SUBMITTED" and history[1]["to_status"] == "PENDING_VERIFICATION"
    assert history[2]["from_status"] == "PENDING_VERIFICATION" and history[2]["to_status"] == "VERIFIED"
    assert history[2]["remarks"] == "Confirmed joint lien with SBI CP branch manager. All clauses verified."

    # Verify AuditLog entries
    audit_count = AuditLog.query.filter_by(entity_id=fdr_id).filter(
        AuditLog.action.like("SCRUTINY_TRANSITION_%")
    ).count()
    assert audit_count == 3

    # Verify notifications
    inst_notifs = Notification.query.filter_by(user_id=env["user_a"].id).all()
    assert len(inst_notifs) >= 3  # Intake confirmation, under scrutiny notice, verified notice


def test_e2e_scenario_b_returned_and_resubmitted_fdr(client, seed_e2e_env):
    """
    Scenario B: Return, deficiency preservation, resubmission, and subsequent verification:
    DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> RETURNED -> SUBMITTED -> PENDING_VERIFICATION -> VERIFIED.
    Verifies that return remarks are preserved as a deficiency and NOT marked resolved on resubmission.
    """
    env = seed_e2e_env

    # 1. Create and submit
    fdr_id, csrf_inst = create_fdr_and_upload_document(
        client, "registrar@apex.edu", "ApexPass123!", "FDR-E2E-B-01"
    )
    client.post(f"/api/fdr/{fdr_id}/submit", headers={"X-CSRF-Token": csrf_inst})

    # 2. Officer starts review
    csrf_officer = login_and_get_csrf(client, "officer.verif@aicte.gov.in", "OfficerPass123!")
    client.post(f"/api/fdr/{fdr_id}/start-review", headers={"X-CSRF-Token": csrf_officer})

    # 3. Officer returns for correction with explicit reason
    return_reason = "Branch seal is missing on page 1. Account name lacks AICTE joint clause."
    res_return = client.post(
        f"/api/fdr/{fdr_id}/return",
        json={"reason": return_reason},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_return.status_code == 200
    assert res_return.get_json()["scrutiny_status"] == "RETURNED"

    # 4. Institution user checks workflow state:
    # Must see RETURNED status, available action ["submit"], and active deficiency record
    csrf_inst = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")
    res_wf_ret = client.get(f"/api/fdr/{fdr_id}/workflow")
    data_ret = res_wf_ret.get_json()["data"]
    assert data_ret["scrutiny_status"] == "RETURNED"
    assert "submit" in data_ret["available_actions"]
    assert len(data_ret["deficiencies"]) == 1
    assert data_ret["deficiencies"][0]["remarks"] == return_reason
    assert data_ret["deficiencies"][0]["resolution_status"] == "UNRESOLVED"

    # 5. Institution user resubmits: RETURNED -> SUBMITTED
    res_resubmit = client.post(
        f"/api/fdr/{fdr_id}/submit",
        json={"remarks": "Uploaded fresh scan with branch seal and joint clause."},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert res_resubmit.status_code == 200
    assert res_resubmit.get_json()["data"]["scrutiny_status"] == "SUBMITTED"

    # 6. Verify that earlier deficiency is STILL preserved and NOT automatically marked resolved
    res_wf_resub = client.get(f"/api/fdr/{fdr_id}/workflow")
    data_resub = res_wf_resub.get_json()["data"]
    assert len(data_resub["deficiencies"]) == 1
    assert data_resub["deficiencies"][0]["resolution_status"] == "UNRESOLVED"
    assert data_resub["deficiencies"][0]["remarks"] == return_reason

    # 7. Officer starts review again and approves
    csrf_officer = login_and_get_csrf(client, "officer.verif@aicte.gov.in", "OfficerPass123!")
    client.post(f"/api/fdr/{fdr_id}/start-review", headers={"X-CSRF-Token": csrf_officer})
    res_final_verify = client.post(
        f"/api/fdr/{fdr_id}/verify",
        json={"remarks": "Re-uploaded receipt has clear bank seal and valid joint lien. Approved."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_final_verify.status_code == 200
    assert res_final_verify.get_json()["data"]["scrutiny_status"] == "VERIFIED"

    # 8. Verify total history count = exactly 6 events in strict chronological order
    res_final = client.get(f"/api/fdr/{fdr_id}/workflow")
    history = res_final.get_json()["data"]["workflow_history"]
    assert len(history) == 6
    transitions = [(h["from_status"], h["to_status"]) for h in history]
    assert transitions == [
        ("DRAFT", "SUBMITTED"),
        ("SUBMITTED", "PENDING_VERIFICATION"),
        ("PENDING_VERIFICATION", "RETURNED"),
        ("RETURNED", "SUBMITTED"),
        ("SUBMITTED", "PENDING_VERIFICATION"),
        ("PENDING_VERIFICATION", "VERIFIED"),
    ]


def test_e2e_scenario_c_rejection(client, seed_e2e_env):
    """
    Scenario C: Submission, review, and rejection:
    DRAFT -> SUBMITTED -> PENDING_VERIFICATION -> REJECTED.
    Verifies terminal rejection state, alert notifications, and locking of record.
    """
    env = seed_e2e_env

    # 1. Create and submit
    fdr_id, csrf_inst = create_fdr_and_upload_document(
        client, "registrar@apex.edu", "ApexPass123!", "FDR-E2E-C-01"
    )
    client.post(f"/api/fdr/{fdr_id}/submit", headers={"X-CSRF-Token": csrf_inst})

    # 2. Officer starts review
    csrf_officer = login_and_get_csrf(client, "officer.verif@aicte.gov.in", "OfficerPass123!")
    client.post(f"/api/fdr/{fdr_id}/start-review", headers={"X-CSRF-Token": csrf_officer})

    # 3. Officer rejects deposit
    rejection_reason = "FDR prematurely encashed by institution prior to verification without AICTE NOC."
    res_reject = client.post(
        f"/api/fdr/{fdr_id}/reject",
        json={"reason": rejection_reason},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_reject.status_code == 200
    assert res_reject.get_json()["scrutiny_status"] == "REJECTED"

    # 4. Check terminal state in workflow endpoint
    res_wf = client.get(f"/api/fdr/{fdr_id}/workflow")
    wf_data = res_wf.get_json()["data"]
    assert wf_data["scrutiny_status"] == "REJECTED"
    assert wf_data["available_actions"] == []  # No actions permitted

    # 5. Attempting any further transition must be rejected with TERMINAL_STATUS_LOCKED
    res_bad = client.post(
        f"/api/fdr/{fdr_id}/verify",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res_bad.status_code == 400
    assert res_bad.get_json()["code"] == "TERMINAL_STATUS_LOCKED"

    # 6. Institution user must have received an ALERT notification
    alert_notif = Notification.query.filter_by(
        user_id=env["user_a"].id, notification_type=NotificationType.ALERT.value
    ).first()
    assert alert_notif is not None
    assert rejection_reason in alert_notif.message


# =====================================================================
# 2. Comprehensive Security & Regression Tests
# =====================================================================


def test_security_unauthenticated_access_blocked(client, seed_e2e_env):
    """Verify unauthenticated users cannot access any FDR, document, workflow, or notification endpoints."""
    fdr_id = 1
    # FDR endpoints
    assert client.get("/api/fdr").status_code == 401
    assert client.get(f"/api/fdr/{fdr_id}").status_code == 401
    assert client.post("/api/fdr", json={}).status_code == 401
    assert client.patch(f"/api/fdr/{fdr_id}", json={}).status_code == 401

    # Document endpoints
    assert client.get(f"/api/fdr/{fdr_id}/documents").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/documents").status_code == 401
    assert client.get(f"/api/fdr/{fdr_id}/documents/1").status_code == 401

    # Workflow endpoints
    assert client.get(f"/api/fdr/{fdr_id}/workflow").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/submit").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/start-review").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/verify").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/return").status_code == 401
    assert client.post(f"/api/fdr/{fdr_id}/reject").status_code == 401

    # Notification endpoints
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.patch("/api/notifications/1/read").status_code == 401
    assert client.patch("/api/notifications/read-all").status_code == 401


def test_security_csrf_enforcement_on_mutating_endpoints(client, seed_e2e_env):
    """Verify that all state-changing endpoints reject requests missing or containing invalid CSRF tokens."""
    fdr_id, _ = create_fdr_and_upload_document(
        client, "registrar@apex.edu", "ApexPass123!", "FDR-CSRF-TEST"
    )

    # 1. Missing CSRF token
    res1 = client.post(f"/api/fdr/{fdr_id}/submit")
    assert res1.status_code == 403
    assert res1.get_json()["code"] == "CSRF_ERROR"

    # 2. Invalid / forged CSRF token
    res2 = client.post(
        f"/api/fdr/{fdr_id}/submit",
        headers={"X-CSRF-Token": "forged-invalid-token-12345"},
    )
    assert res2.status_code == 403
    assert res2.get_json()["code"] == "CSRF_ERROR"


def test_security_cross_institution_isolation(client, seed_e2e_env):
    """
    Verify complete tenant isolation: Institution B user cannot read, mutate,
    submit, view documents, or view workflow history of Institution A's FDR (returns 404).
    """
    fdr_a_id, _ = create_fdr_and_upload_document(
        client, "registrar@apex.edu", "ApexPass123!", "FDR-ISOLATION-A"
    )

    # Log in as User B (Zenith Polytechnic)
    csrf_b = login_and_get_csrf(client, "registrar@zenith.edu", "ZenithPass123!")

    # Attempt to read FDR A
    assert client.get(f"/api/fdr/{fdr_a_id}").status_code == 404

    # Attempt to update FDR A
    assert (
        client.patch(
            f"/api/fdr/{fdr_a_id}",
            json={"bank_name": "Hacked Bank"},
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )

    # Attempt to submit FDR A
    assert (
        client.post(
            f"/api/fdr/{fdr_a_id}/submit",
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )

    # Attempt to view documents of FDR A
    assert client.get(f"/api/fdr/{fdr_a_id}/documents").status_code == 404

    # Attempt to view workflow history of FDR A
    assert client.get(f"/api/fdr/{fdr_a_id}/workflow").status_code == 404


def test_security_client_payload_cannot_override_server_authorization(client, seed_e2e_env):
    """
    Verify that client-supplied institution_id, user_id, or role values inside JSON payloads
    are completely ignored in favor of server-side session identity.
    """
    env = seed_e2e_env
    csrf = login_and_get_csrf(client, "registrar@apex.edu", "ApexPass123!")

    # Institution A user attempts to create an FDR for Institution B by spoofing institution_id
    payload = {
        "institution_id": env["inst_b"].id,  # Spoofed!
        "fdr_number": "FDR-SPOOF-001",
        "bank_name": "State Bank of India",
        "branch_name": "Main",
        "amount": "500000.00",
        "issue_date": "2025-01-01",
        "maturity_date": "2030-01-01",
    }
    res = client.post("/api/fdr", json=payload, headers={"X-CSRF-Token": csrf})
    assert res.status_code == 201

    # Record must be bound to Institution A, NOT the spoofed Institution B
    created_fdr = db.session.get(FDRRecord, res.get_json()["data"]["id"])
    assert created_fdr.institution_id == env["inst_a"].id
    assert created_fdr.created_by == env["user_a"].id


def test_security_uploads_directory_not_publicly_accessible(client):
    """Verify that uploaded documents and analysis files cannot be accessed directly via static paths."""
    assert client.get("/uploads/fdr_documents/some_file.pdf").status_code == 404
    assert client.get("/uploads/fdr_documents/some_file.pdf.analysis.json").status_code == 404
    assert client.get("/instance/aicte_fdr.db").status_code == 404


def test_security_scheduler_disabled_in_testing(app):
    """Verify background scheduler is strictly disabled during testing and cannot start background threads."""
    scheduler = init_scheduler(app)
    assert scheduler is None
