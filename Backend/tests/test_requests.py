from datetime import date
from decimal import Decimal
import pytest
from app.models.enums import UserRole
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User


@pytest.fixture
def seed_request_env(app):
    """Seed test institutions, users, and FDRs for request tests."""
    with app.app_context():
        inst1 = Institution(
            institution_code="AICTE-TEST-REQ-1",
            name="Request Test College 1",
            contact_email="principal1@reqtest.edu",
        )
        inst2 = Institution(
            institution_code="AICTE-TEST-REQ-2",
            name="Request Test College 2",
            contact_email="principal2@reqtest.edu",
        )
        from app.extensions import db
        db.session.add_all([inst1, inst2])
        db.session.commit()

        u1 = User(
            full_name="College 1 Principal",
            email="principal1@reqtest.edu",
            role=UserRole.INSTITUTION,
            institution_id=inst1.id,
            is_active=True,
        )
        u1.set_password("Password123!")

        u2 = User(
            full_name="College 2 Principal",
            email="principal2@reqtest.edu",
            role=UserRole.INSTITUTION,
            institution_id=inst2.id,
            is_active=True,
        )
        u2.set_password("Password123!")

        officer = User(
            full_name="Review Officer",
            email="officer@reqtest.gov",
            role=UserRole.AICTE_OFFICER,
            institution_id=None,
            is_active=True,
        )
        officer.set_password("Password123!")

        db.session.add_all([u1, u2, officer])
        db.session.commit()

        fdr1 = FDRRecord(
            institution_id=inst1.id,
            fdr_number="FDR-REQ-001",
            bank_name="Test Bank",
            branch_name="Branch 1",
            amount=Decimal("500000.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            created_by=u1.id,
        )
        fdr2 = FDRRecord(
            institution_id=inst2.id,
            fdr_number="FDR-REQ-002",
            bank_name="Test Bank 2",
            branch_name="Branch 2",
            amount=Decimal("1000000.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            created_by=u2.id,
        )
        db.session.add_all([fdr1, fdr2])
        db.session.commit()

        return {
            "inst1_id": inst1.id,
            "inst2_id": inst2.id,
            "fdr1_id": fdr1.id,
            "fdr2_id": fdr2.id,
        }


def test_list_requests_unauthenticated(client):
    res = client.get("/api/requests")
    assert res.status_code == 401


def test_create_request_success(client, seed_request_env):
    fdr1_id = seed_request_env["fdr1_id"]

    # Login as institution user 1
    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal1@reqtest.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.get_json()["csrf_token"]

    # Create request
    create_res = client.post(
        "/api/requests",
        json={
            "fdr_id": fdr1_id,
            "request_type": "Renewal",
            "reason": "Requesting 3-year renewal due to course expansion.",
            "supporting_document": "letter.pdf",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 201
    data = create_res.get_json()["data"]
    assert data["fdrNumber"] == "FDR-REQ-001"
    assert data["requestType"] == "Renewal"
    assert data["status"] == "Submitted"

    # List requests for institution 1
    list_res = client.get("/api/requests")
    assert list_res.status_code == 200
    reqs = list_res.get_json()["data"]
    assert len(reqs) == 1
    assert reqs[0]["fdrId"] == fdr1_id


def test_create_request_data_isolation(client, seed_request_env):
    fdr2_id = seed_request_env["fdr2_id"]  # Belongs to institution 2

    # Login as institution 1
    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal1@reqtest.edu", "password": "Password123!"},
    )
    csrf_token = login_res.get_json()["csrf_token"]

    # Attempt to submit petition for institution 2's FDR -> must return 404
    create_res = client.post(
        "/api/requests",
        json={
            "fdr_id": fdr2_id,
            "request_type": "Release",
            "reason": "Unauthorized release attempt.",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 404


def test_update_profile(client, seed_request_env):
    # Login as institution 1
    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal1@reqtest.edu", "password": "Password123!"},
    )
    csrf_token = login_res.get_json()["csrf_token"]

    patch_res = client.patch(
        "/api/auth/profile",
        json={
            "full_name": "Dr. Updated Principal",
            "address": "New Campus Road, Knowledge Zone",
            "contact_phone": "+91 9988776655",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert patch_res.status_code == 200
    user_data = patch_res.get_json()["user"]
    assert user_data["full_name"] == "Dr. Updated Principal"
    assert user_data["institution_address"] == "New Campus Road, Knowledge Zone"
    assert user_data["institution_contact_phone"] == "+91 9988776655"


def test_download_attachment_unauthenticated(client):
    """Anonymous user must be rejected with 401."""
    res = client.get("/api/requests/1/download")
    assert res.status_code == 401


def test_download_attachment_success_institution(client, app, seed_request_env):
    """Institution user can download their own request's attachment."""
    fdr1_id = seed_request_env["fdr1_id"]
    inst1_id = seed_request_env["inst1_id"]

    # Seed an FDRRequest with a real physical file on disk in app's request upload folder
    with app.app_context():
        from app.extensions import db
        import os
        from pathlib import Path
        req_dir = Path(app.config["REQUEST_UPLOAD_FOLDER"])
        os.makedirs(req_dir, exist_ok=True)
        file_path = req_dir / "test_inst1_doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 test document content for request")

        fdr_req = FDRRequest(
            fdr_id=fdr1_id,
            institution_id=inst1_id,
            created_by=1,
            request_type="Renewal",
            status="Submitted",
            reason="Renewal justification test",
            supporting_document="test_inst1_doc.pdf",
        )
        db.session.add(fdr_req)
        db.session.commit()
        req_id = fdr_req.id

    # Login as Institution 1
    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal1@reqtest.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    # Download attachment
    res = client.get(f"/api/requests/{req_id}/download")
    assert res.status_code == 200
    assert "attachment" in res.headers["Content-Disposition"]
    assert "test_inst1_doc.pdf" in res.headers["Content-Disposition"]
    assert res.data == b"%PDF-1.4 test document content for request"


def test_download_attachment_success_officer_admin(client, app, seed_request_env):
    """AICTE Officer / Admin can download attachments across institutions."""
    fdr1_id = seed_request_env["fdr1_id"]
    inst1_id = seed_request_env["inst1_id"]

    with app.app_context():
        from app.extensions import db
        import os
        from pathlib import Path
        req_dir = Path(app.config["REQUEST_UPLOAD_FOLDER"])
        os.makedirs(req_dir, exist_ok=True)
        file_path = req_dir / "officer_view_doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 officer accessible content")

        fdr_req = FDRRequest(
            fdr_id=fdr1_id,
            institution_id=inst1_id,
            created_by=1,
            request_type="Renewal",
            status="Submitted",
            reason="Renewal justification test for officer review",
            supporting_document="officer_view_doc.pdf",
        )
        db.session.add(fdr_req)
        db.session.commit()
        req_id = fdr_req.id

    # Login as AICTE Officer
    login_res = client.post(
        "/api/auth/login",
        json={"email": "officer@reqtest.gov", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    # Download attachment as officer
    res = client.get(f"/api/requests/{req_id}/download")
    assert res.status_code == 200
    assert "attachment" in res.headers["Content-Disposition"]
    assert "officer_view_doc.pdf" in res.headers["Content-Disposition"]
    assert res.data == b"%PDF-1.4 officer accessible content"


def test_download_attachment_cross_institution_forbidden(client, app, seed_request_env):
    """Institution 2 cannot access or download Institution 1's attachments."""
    fdr1_id = seed_request_env["fdr1_id"]
    inst1_id = seed_request_env["inst1_id"]

    with app.app_context():
        from app.extensions import db
        import os
        from pathlib import Path
        req_dir = Path(app.config["REQUEST_UPLOAD_FOLDER"])
        os.makedirs(req_dir, exist_ok=True)
        file_path = req_dir / "inst1_confidential.pdf"
        file_path.write_bytes(b"%PDF-1.4 secret institution 1 data")

        fdr_req = FDRRequest(
            fdr_id=fdr1_id,
            institution_id=inst1_id,
            created_by=1,
            request_type="Release",
            status="Submitted",
            reason="Release justification",
            supporting_document="inst1_confidential.pdf",
        )
        db.session.add(fdr_req)
        db.session.commit()
        req_id = fdr_req.id

    # Login as Institution 2
    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal2@reqtest.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    # Attempt to download Institution 1's attachment -> 404 (data isolation)
    res = client.get(f"/api/requests/{req_id}/download")
    assert res.status_code == 404


def test_download_attachment_missing_file_on_disk(client, app, seed_request_env):
    """If database record points to a file that does not exist on disk, return 404 FILE_NOT_FOUND."""
    fdr1_id = seed_request_env["fdr1_id"]
    inst1_id = seed_request_env["inst1_id"]

    with app.app_context():
        from app.extensions import db
        fdr_req = FDRRequest(
            fdr_id=fdr1_id,
            institution_id=inst1_id,
            created_by=1,
            request_type="Renewal",
            status="Submitted",
            reason="Test missing file",
            supporting_document="missing_on_disk.pdf",
        )
        db.session.add(fdr_req)
        db.session.commit()
        req_id = fdr_req.id

    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal1@reqtest.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    res = client.get(f"/api/requests/{req_id}/download")
    assert res.status_code == 404
    data = res.get_json()
    assert data["code"] == "FILE_NOT_FOUND"


def test_download_attachment_no_attachment(client, app, seed_request_env):
    """If petition has no supporting document, return 404 ATTACHMENT_NOT_FOUND."""
    fdr1_id = seed_request_env["fdr1_id"]
    inst1_id = seed_request_env["inst1_id"]

    with app.app_context():
        from app.extensions import db
        fdr_req = FDRRequest(
            fdr_id=fdr1_id,
            institution_id=inst1_id,
            created_by=1,
            request_type="Renewal",
            status="Submitted",
            reason="No attachment petition",
            supporting_document=None,
        )
        db.session.add(fdr_req)
        db.session.commit()
        req_id = fdr_req.id

    login_res = client.post(
        "/api/auth/login",
        json={"email": "principal1@reqtest.edu", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    res = client.get(f"/api/requests/{req_id}/download")
    assert res.status_code == 404
    data = res.get_json()
    assert data["code"] == "ATTACHMENT_NOT_FOUND"


