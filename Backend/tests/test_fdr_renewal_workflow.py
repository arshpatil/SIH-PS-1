from datetime import date, timedelta
from decimal import Decimal
import io
import pytest

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.renewal_history import FDRRenewalHistory
from app.models.user import User


@pytest.fixture
def renewal_env(app):
    """Seed test environment with 2 institutions, an officer, and an admin."""
    inst_1 = Institution(
        institution_code="AICTE-REN-001",
        name="Apex Institute of Technology",
        contact_email="principal@apex.edu",
    )
    inst_2 = Institution(
        institution_code="AICTE-REN-002",
        name="Global Engineering College",
        contact_email="director@global.edu",
    )
    db.session.add_all([inst_1, inst_2])
    db.session.commit()

    inst1_user = User(
        full_name="Principal Apex",
        email="principal@apex.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_1.id,
        is_active=True,
    )
    inst1_user.set_password("ApexPass123!")

    inst2_user = User(
        full_name="Director Global",
        email="director@global.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_2.id,
        is_active=True,
    )
    inst2_user.set_password("GlobalPass123!")

    officer = User(
        full_name="Scrutiny Officer Sharma",
        email="sharma.officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="Regional Admin Verma",
        email="verma.admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([inst1_user, inst2_user, officer, admin])
    db.session.commit()

    # Create an initial FDR that is maturing soon (15 days remaining)
    old_issue_date = date.today() - timedelta(days=365 * 3)
    old_maturity_date = date.today() + timedelta(days=15)
    fdr = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="FDR-SBI-100200",
        bank_name="State Bank of India",
        branch_name="University Campus",
        amount=Decimal("2500000.00"),
        issue_date=old_issue_date,
        maturity_date=old_maturity_date,
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.EXPIRING_SOON.value,
        created_by=inst1_user.id,
    )
    db.session.add(fdr)
    db.session.commit()

    return {
        "inst_1": inst_1,
        "inst_2": inst_2,
        "inst1_user": inst1_user,
        "inst2_user": inst2_user,
        "officer": officer,
        "admin": admin,
        "fdr": fdr,
        "old_issue_date": old_issue_date,
        "old_maturity_date": old_maturity_date,
    }


def login(client, email, password):
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, f"Login failed for {email}: {res.get_data(as_text=True)}"
    csrf_res = client.get("/api/auth/csrf-token")
    assert csrf_res.status_code == 200
    return csrf_res.get_json()["csrf_token"]


def test_renewal_workflow_end_to_end(client, renewal_env):
    """
    Test complete renewal lifecycle:
    1. Institution submits renewal petition.
    2. Officer approves petition without silently changing maturity date.
    3. Institution sees approved status with prompt for receipt upload immediately & on re-login.
    4. Old maturity date remains completely unchanged.
    5. Institution uploads renewed FDR details and receipt file.
    6. Officer verifies renewed details and endorsed new maturity date.
    7. FDR maturity, amount, fdr number update to verified new values; validity status recalculates.
    8. Old FDR details preserved in FDRRenewalHistory.
    """
    fdr = renewal_env["fdr"]
    old_mat_str = fdr.maturity_date.isoformat()
    old_num = fdr.fdr_number
    old_amt = fdr.amount

    # 1. Institution submits a renewal petition
    csrf_inst = login(client, "principal@apex.edu", "ApexPass123!")

    doc_bytes = io.BytesIO(b"%PDF-1.4 Mock FDR renewal application letter")
    submit_res = client.post(
        "/api/requests",
        data={
            "fdr_id": str(fdr.id),
            "request_type": "Renewal",
            "reason": "Institution requests approval to renew maturing security deposit with State Bank of India.",
            "file": (doc_bytes, "Renewal_Petition.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert submit_res.status_code == 201, submit_res.get_data(as_text=True)
    res_json = submit_res.get_json()
    req_data = res_json.get("data") or res_json.get("request")
    req_id = req_data.get("raw_id") or req_data.get("id")
    assert req_data["status"] == "Submitted"

    # Verify FDR maturity has NOT changed
    db.session.refresh(fdr)
    assert fdr.maturity_date.isoformat() == old_mat_str

    # 2. Officer logs in and reviews petition
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")

    # Officer moves petition to Under Review
    review_res = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Under Review", "remarks": "Scrutinizing banking covenants."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert review_res.status_code == 200
    rev_json = review_res.get_json()
    rev_data = rev_json.get("data") or rev_json.get("request")
    assert rev_data["status"] == "Under Review"

    # Officer approves renewal petition
    approve_res = client.patch(
        f"/api/requests/{req_id}/status",
        json={
            "status": "Approved",
            "remarks": "Renewal petition approved under APH Section 4. Deposit renewal receipt required.",
        },
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert approve_res.status_code == 200
    appr_json = approve_res.get_json()
    appr_data = appr_json.get("data") or appr_json.get("request")
    assert appr_data["status"] == "Approved"
    assert "Deposit Receipt" in appr_data["stage"]

    # 3. Check that FDR maturity date was NOT silently changed upon petition approval
    db.session.refresh(fdr)
    assert fdr.maturity_date.isoformat() == old_mat_str
    assert fdr.fdr_number == old_num
    assert fdr.amount == old_amt

    # 4. Institution logs in again and verifies status and dashboard prompt
    csrf_inst = login(client, "principal@apex.edu", "ApexPass123!")

    inst_req_res = client.get(f"/api/requests/{req_id}")
    assert inst_req_res.status_code == 200
    inst_req_json = inst_req_res.get_json()
    inst_req = inst_req_json.get("data") or inst_req_json.get("request")
    assert inst_req["status"] == "Approved"
    assert "Renewal petition approved" in (inst_req.get("remarks") or inst_req.get("rejection_reason") or "")

    # Institution checks FDR detail API
    fdr_res = client.get(f"/api/fdr/{fdr.id}")
    assert fdr_res.status_code == 200
    fdr_payload = fdr_res.get_json()["data"]
    assert (fdr_payload.get("maturityDate") or fdr_payload.get("maturity_date")) == old_mat_str
    assert fdr_payload["latest_request"]["status"] == "Approved"

    # 5. Institution uploads renewed FDR details and receipt
    new_issue = (date.today()).isoformat()
    new_mat = (date.today() + timedelta(days=365 * 3)).isoformat()
    new_num = "FDR-SBI-998877"
    new_amount = "2750000.00"

    receipt_bytes = io.BytesIO(b"%PDF-1.4 Official Bank Renewed FDR Term Deposit Receipt")
    upload_res = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": new_num,
            "new_issue_date": new_issue,
            "new_maturity_date": new_mat,
            "new_amount": new_amount,
            "remarks": "Bank renewed FDR with interest capitalisation. New FDR copy attached.",
            "renewal_document": (receipt_bytes, "Bank_Renewed_FDR_Receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 200, upload_res.get_data(as_text=True)
    up_json = upload_res.get_json()
    up_data = up_json.get("data") or up_json.get("request")
    assert up_data["status"] == "Pending Verification"
    assert up_data["renewal_fdr_number"] == new_num
    assert up_data["renewal_maturity_date"] == new_mat

    # FDR is now in RENEWAL_PENDING_VERIFICATION but maturity date is STILL the old date
    db.session.refresh(fdr)
    assert fdr.validity_status == ValidityStatus.RENEWAL_PENDING_VERIFICATION.value
    assert fdr.maturity_date.isoformat() == old_mat_str

    # 6. Officer verifies renewed FDR receipt
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")

    verify_res = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={
            "decision": "VERIFIED",
            "remarks": "Renewed FDR receipt verified with SBI branch. New 3-year term endorsed.",
        },
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert verify_res.status_code == 200, verify_res.get_data(as_text=True)
    ver_data = verify_res.get_json()
    assert ver_data["fdr"]["fdrNumber"] == new_num
    assert ver_data["fdr"]["maturityDate"] == new_mat
    assert ver_data["request"]["status"] == "Closed"

    # 7. FDR record has updated to the verified new values
    db.session.refresh(fdr)
    assert fdr.fdr_number == new_num
    assert fdr.maturity_date.isoformat() == new_mat
    assert fdr.amount == Decimal("2750000.00")
    assert fdr.validity_status == ValidityStatus.ACTIVE.value

    # 8. Check FDR renewal history preserves previous details
    hist_entries = FDRRenewalHistory.query.filter_by(fdr_id=fdr.id).all()
    assert len(hist_entries) == 1
    h = hist_entries[0]
    assert h.previous_fdr_number == old_num
    assert h.previous_maturity_date.isoformat() == old_mat_str
    assert h.new_fdr_number == new_num
    assert h.new_maturity_date.isoformat() == new_mat
    assert h.new_amount == Decimal("2750000.00")
    assert h.verifier.email == "sharma.officer@aicte.gov.in"
    assert "New 3-year term endorsed" in h.remarks


def test_unauthorized_users_cannot_approve_or_verify(client, renewal_env):
    """
    Ensure RBAC and access controls:
    - Institution users cannot approve or verify petitions.
    - Unauthenticated callers are rejected.
    - Other institutions cannot view or submit renewals for someone else's petition.
    """
    fdr = renewal_env["fdr"]

    # Submit renewal petition
    csrf_inst1 = login(client, "principal@apex.edu", "ApexPass123!")
    doc = io.BytesIO(b"%PDF-1.4 Mock Application")
    sub_res = client.post(
        "/api/requests",
        data={
            "fdr_id": str(fdr.id),
            "request_type": "Renewal",
            "reason": "Requesting renewal clearance",
            "file": (doc, "app.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst1},
        content_type="multipart/form-data",
    )
    assert sub_res.status_code == 201
    res_json = sub_res.get_json()
    req_data = res_json.get("data") or res_json.get("request")
    req_id = req_data.get("raw_id") or req_data.get("id")

    # Institution tries to approve their own petition -> 403 Forbidden
    hack_res = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Self approval attempt"},
        headers={"X-CSRF-Token": csrf_inst1},
    )
    assert hack_res.status_code == 403

    # Other institution tries to access or submit renewal -> 403 or 404 (isolation)
    csrf_inst2 = login(client, "director@global.edu", "GlobalPass123!")
    other_sub = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "HACK-999",
            "new_issue_date": date.today().isoformat(),
            "new_maturity_date": (date.today() + timedelta(days=365)).isoformat(),
            "new_amount": "1000000",
        },
        headers={"X-CSRF-Token": csrf_inst2},
    )
    assert other_sub.status_code in (403, 404)

    other_verify = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={"decision": "VERIFIED", "remarks": "Illegal verification"},
        headers={"X-CSRF-Token": csrf_inst2},
    )
    assert other_verify.status_code in (403, 404)

    # Officer approves petition legitimately
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")
    client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Approved"},
        headers={"X-CSRF-Token": csrf_officer},
    )

    # Institution tries to call verify-renewal endpoint directly -> 403 Forbidden
    login(client, "principal@apex.edu", "ApexPass123!")
    inst_verify_attempt = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={"decision": "VERIFIED", "remarks": "Self verification attempt"},
        headers={"X-CSRF-Token": csrf_inst1},
    )
    assert inst_verify_attempt.status_code == 403


def test_invalid_dates_and_duplicate_handling(client, renewal_env):
    """
    Test validation edge cases:
    - Invalid maturity dates (new maturity <= new issue date) are rejected with 400.
    - Duplicate active petitions for the same FDR are prevented.
    - Returning/rejecting renewed deposit documents.
    """
    fdr = renewal_env["fdr"]

    # 1. Duplicate active petition prevention
    csrf_inst = login(client, "principal@apex.edu", "ApexPass123!")
    doc1 = io.BytesIO(b"%PDF-1.4 First Application")
    res1 = client.post(
        "/api/requests",
        data={
            "fdr_id": str(fdr.id),
            "request_type": "Renewal",
            "reason": "First renewal petition",
            "file": (doc1, "petition1.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert res1.status_code == 201
    res1_json = res1.get_json()
    req_data = res1_json.get("data") or res1_json.get("request")
    req_id = req_data.get("raw_id") or req_data.get("id")

    # Attempt to submit a duplicate renewal petition for the same FDR while one is active
    doc2 = io.BytesIO(b"%PDF-1.4 Duplicate Application")
    res2 = client.post(
        "/api/requests",
        data={
            "fdr_id": str(fdr.id),
            "request_type": "Renewal",
            "reason": "Second renewal petition attempt",
            "file": (doc2, "petition2.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert res2.status_code == 409
    assert "already in progress" in res2.get_json()["error"]

    # Officer approves the first petition
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")
    client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Approved"},
        headers={"X-CSRF-Token": csrf_officer},
    )

    # 2. Institution submits invalid renewal dates (new maturity <= new issue date)
    csrf_inst = login(client, "principal@apex.edu", "ApexPass123!")
    bad_doc = io.BytesIO(b"%PDF-1.4 Receipt")
    bad_date_res = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "BAD-FDR-001",
            "new_issue_date": "2026-05-01",
            "new_maturity_date": "2025-05-01",  # Maturity BEFORE issue date
            "new_amount": "2000000",
            "renewal_document": (bad_doc, "receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert bad_date_res.status_code == 400
    assert "must be later than the issue date" in bad_date_res.get_json()["error"].lower()

    # Negative / zero amount validation
    bad_amt_doc = io.BytesIO(b"%PDF-1.4 Receipt")
    bad_amt_res = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "BAD-FDR-002",
            "new_issue_date": "2026-05-01",
            "new_maturity_date": "2029-05-01",
            "new_amount": "-500",
            "renewal_document": (bad_amt_doc, "receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert bad_amt_res.status_code == 400

    # 3. Officer RETURNED / DEFICIENT decision on renewal receipt
    # Submit valid parameters first
    good_doc = io.BytesIO(b"%PDF-1.4 Good Receipt")
    good_res = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "FDR-RECHECK-100",
            "new_issue_date": "2026-05-01",
            "new_maturity_date": "2029-05-01",
            "new_amount": "2500000",
            "renewal_document": (good_doc, "receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert good_res.status_code == 200

    # Officer returns for deficiency / missing seal
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")
    return_res = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={
            "decision": "RETURNED",
            "remarks": "Bank officer stamp and branch IFSC code missing from receipt.",
        },
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert return_res.status_code == 200
    ret_req = return_res.get_json()["request"]
    assert ret_req["status"] == "Documents Required"
    assert "Bank officer stamp" in ret_req["remarks"]


def test_synthetic_receipt_generation_and_download(client, renewal_env):
    """
    Test downloadable synthetic PDF renewal receipt:
    - Prominently marked 'SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK'.
    - Uses clearly fictional bank/reference information.
    - Includes institution name and FDR identifier from the demo record.
    - Includes principal amount and proposed new maturity date.
    - Disclaims all official bank confirmation.
    - Restricted to authorized users.
    """
    fdr = renewal_env["fdr"]
    inst_user = renewal_env["inst1_user"]
    inst2_user = renewal_env["inst2_user"]

    # Institution 1 logs in
    csrf_inst1 = login(client, inst_user.email, "ApexPass123!")

    # Download synthetic PDF from FDR endpoint
    res = client.get(f"/api/fdr/{fdr.id}/demo-renewal-receipt", headers={"X-CSRF-Token": csrf_inst1})
    assert res.status_code == 200, res.get_data(as_text=True)
    assert res.headers.get("Content-Type") == "application/pdf"
    assert "attachment" in res.headers.get("Content-Disposition", "")
    pdf_bytes = res.get_data()
    assert pdf_bytes.startswith(b"%PDF-")

    # Extract text using PyMuPDF to verify content and disclaimers
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    extracted_text = doc[0].get_text()

    # Assertions on content
    assert "SYNTHETIC DEMO DOCUMENT - NOT ISSUED BY A BANK" in extracted_text
    assert "Fictional Sandbox Test Bank Ltd." in extracted_text
    assert "Apex Institute of Technology" in extracted_text
    assert fdr.fdr_number in extracted_text
    assert "2,500,000.00" in extracted_text
    assert "NOT CONSTITUTE BANK CONFIRMATION" in extracted_text.upper() or "NOT AN OFFICIAL BANK RECORD" in extracted_text.upper()

    # Multi-tenant scoping: Institution 2 CANNOT download Institution 1's demo receipt
    csrf_inst2 = login(client, inst2_user.email, "GlobalPass123!")
    res_forbidden = client.get(f"/api/fdr/{fdr.id}/demo-renewal-receipt", headers={"X-CSRF-Token": csrf_inst2})
    assert res_forbidden.status_code in (403, 404)


def test_synthetic_receipt_upload_honest_detection_and_simulated_verification(client, renewal_env, monkeypatch):
    """
    Test complete synthetic receipt cycle:
    1. Petition approved by officer.
    2. Synthetic PDF downloaded and uploaded through standard interface.
    3. Document validation runs without bypass.
    4. Text extraction honestly detects synthetic demo watermark.
    5. Receipt is NOT automatically verified; status is 'Pending Verification'.
    6. Original maturity date remains unchanged.
    7. Officer performs simulated demo verification.
    8. Official maturity date and renewal history update correctly.
    9. Audit logs and notifications record simulated demo verification without false bank claims.
    """
    fdr = renewal_env["fdr"]
    old_mat_date = fdr.maturity_date
    csrf_inst = login(client, "principal@apex.edu", "ApexPass123!")

    # 1. Submit renewal petition
    doc_bytes = io.BytesIO(b"%PDF-1.4 Renewal petition letter")
    sub_res = client.post(
        "/api/requests",
        data={
            "fdr_id": str(fdr.id),
            "request_type": "Renewal",
            "reason": "Request 3-year extension for FDR",
            "file": (doc_bytes, "Petition.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    req_id = sub_res.get_json()["data"]["raw_id"]

    # Officer approves petition
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")
    client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Approved by Scrutiny Desk"},
        headers={"X-CSRF-Token": csrf_officer},
    )

    # 2. Download synthetic PDF
    csrf_inst = login(client, "principal@apex.edu", "ApexPass123!")
    dl_res = client.get(f"/api/requests/{req_id}/demo-renewal-receipt", headers={"X-CSRF-Token": csrf_inst})
    assert dl_res.status_code == 200
    pdf_content = dl_res.get_data()
    assert pdf_content.startswith(b"%PDF-")

    # 3. Upload synthetic PDF via existing submit-renewal interface
    new_issue = date.today().isoformat()
    new_maturity = (date.today() + timedelta(days=365 * 3)).isoformat()
    upload_res = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": f"{fdr.fdr_number}-REN",
            "new_issue_date": new_issue,
            "new_maturity_date": new_maturity,
            "new_amount": "2500000.00",
            "remarks": "Submitting synthetic renewed receipt for testing.",
            "file": (io.BytesIO(pdf_content), f"DEMO_Renewal_{fdr.fdr_number}.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 200, upload_res.get_data(as_text=True)
    req_data = upload_res.get_json()["data"]

    # 4. Status is Pending Verification (NOT automatically marked verified!)
    assert req_data["status"] == "Pending Verification"
    assert req_data["stage"] == "Pending Renewal Receipt Verification"
    assert req_data["renewalIsSynthetic"] is True or req_data["renewal_is_synthetic"] is True

    # 5. Check FDR maturity date in DB has NOT been altered yet
    db.session.refresh(fdr)
    assert fdr.maturity_date == old_mat_date
    assert fdr.validity_status == ValidityStatus.RENEWAL_PENDING_VERIFICATION.value

    # 6. Institution CANNOT verify the receipt
    inst_verify_res = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={"decision": "VERIFIED", "is_simulated": True},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert inst_verify_res.status_code == 403

    # 7. Authorized officer performs simulated demo verification
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")
    verify_res = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={
            "decision": "VERIFIED",
            "remarks": "Reviewed in demo mode with synthetic test receipt.",
            "is_simulated": True,
        },
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert verify_res.status_code == 200, verify_res.get_data(as_text=True)
    ver_json = verify_res.get_json()
    assert ver_json["success"] is True

    # 8. Check that official maturity date is now updated
    db.session.refresh(fdr)
    assert fdr.maturity_date.isoformat() == new_maturity
    assert fdr.fdr_number.endswith("-REN")

    # 9. Verify renewal history preserves old maturity date
    history_entries = FDRRenewalHistory.query.filter_by(fdr_id=fdr.id).all()
    assert len(history_entries) >= 1
    latest_hist = history_entries[-1]
    assert latest_hist.previous_maturity_date == old_mat_date
    assert latest_hist.new_maturity_date.isoformat() == new_maturity
    assert "SIMULATED DEMO VERIFICATION" in latest_hist.remarks

    # 10. Verify calendar events reflect the new maturity date
    cal_res = client.get(f"/api/calendar/events?end={new_maturity}", headers={"X-CSRF-Token": csrf_officer})
    assert cal_res.status_code == 200
    events = cal_res.get_json()["events"]
    # At least one event has new maturity date
    mat_events = [e for e in events if e.get("fdr_id") == fdr.id and e.get("type") == "FDR_MATURITY"]
    assert any(e["date"] == new_maturity for e in mat_events)


def test_production_environment_prevents_simulated_verification(client, renewal_env, monkeypatch):
    """
    Test that in production mode:
    - Synthetic demo receipts cannot be downloaded.
    - Simulated demo verification cannot be performed.
    """
    from app.services import synthetic_receipt_service

    # Mock environment to simulate production
    monkeypatch.setattr(synthetic_receipt_service, "is_demo_environment", lambda: False)

    fdr = renewal_env["fdr"]
    csrf_officer = login(client, "sharma.officer@aicte.gov.in", "OfficerPass123!")

    # 1. Download attempt blocked in production
    res_dl = client.get(f"/api/fdr/{fdr.id}/demo-renewal-receipt", headers={"X-CSRF-Token": csrf_officer})
    assert res_dl.status_code == 403
    assert "disabled in production" in res_dl.get_json()["error"]

    # 2. Simulated verification attempt blocked in production
    # Create request in Approved state
    fdr_req = FDRRequest(
        fdr_id=fdr.id,
        institution_id=renewal_env["inst_1"].id,
        created_by=renewal_env["inst1_user"].id,
        request_type="Renewal",
        status="Pending Verification",
        stage="Pending Renewal Receipt Verification",
        reason="Test petition",
        renewal_fdr_number=f"{fdr.fdr_number}-REN",
        renewal_issue_date=date.today(),
        renewal_maturity_date=date.today() + timedelta(days=365 * 3),
        renewal_amount=fdr.amount,
        renewal_is_synthetic=True,
    )
    db.session.add(fdr_req)
    db.session.commit()

    ver_res = client.post(
        f"/api/requests/{fdr_req.id}/verify-renewal",
        json={"decision": "VERIFIED", "is_simulated": True},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert ver_res.status_code == 403
    assert "strictly prohibited in production" in ver_res.get_json()["error"]

