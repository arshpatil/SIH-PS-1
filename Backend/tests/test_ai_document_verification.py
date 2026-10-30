import io
from datetime import date
from decimal import Decimal
import json
import pytest
import pymupdf

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import DocumentProcessingStatus, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User
from app.services.ocr_service import (
    compute_field_confidence,
    detect_fdr_discrepancies,
    detect_joint_lien,
    extract_fdr_fields,
)


@pytest.fixture
def ai_test_env(app):
    """Seed test fixtures for AI document verification testing."""
    inst = Institution(
        institution_code="AICTE-AI-TEST-1",
        name="Apex Institute of Technology",
        contact_email="director@apex.edu",
    )
    db.session.add(inst)
    db.session.commit()

    inst_user = User(
        full_name="College Registrar",
        email="registrar@apex.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst.id,
        is_active=True,
    )
    inst_user.set_password("ApexPass123!")

    officer = User(
        full_name="AICTE Verification Officer",
        email="scrutiny_officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="AICTE Super Admin",
        email="super_admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([inst_user, officer, admin])
    db.session.commit()

    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number="FDR-AI-9999",
        bank_name="Canara Bank",
        branch_name="Shivaji Nagar, Pune",
        amount=Decimal("1500000.00"),
        issue_date=date(2025, 6, 1),
        maturity_date=date(2030, 6, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=inst_user.id,
    )
    db.session.add(fdr)
    db.session.commit()

    return {
        "inst": inst,
        "inst_user": inst_user,
        "officer": officer,
        "admin": admin,
        "fdr": fdr,
    }


def login_helper(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=12)
    b = doc.tobytes()
    doc.close()
    return b


def test_field_by_field_matching_and_contract(ai_test_env):
    """Verify that when all 6 fields match, each field is marked MATCH with correct registered and extracted data."""
    fdr = ai_test_env["fdr"]
    matching_extracted = {
        "fdr_number": "FDR-AI-9999",
        "bank_name": "Canara Bank",
        "branch_name": "Shivaji Nagar, Pune",
        "amount": "1500000.00",
        "issue_date": "2025-06-01",
        "maturity_date": "2030-06-01",
    }
    report = detect_fdr_discrepancies(matching_extracted, fdr, is_scanned=False)

    assert report["overall_result"] == "MATCH"
    assert "field_analysis" in report
    fields = report["field_analysis"]

    for k in ["fdr_number", "bank_name", "branch_name", "amount", "issue_date", "maturity_date"]:
        assert k in fields
        assert fields[k]["status"] == "MATCH"
        assert fields[k]["extracted"] is not None
        assert fields[k]["discrepancy_note"] is None
        # Digital PDF without word OCR data must report confidence as None and display 'N/A'
        assert fields[k]["confidence"] is None
        assert fields[k]["confidence_display"] == "N/A"

    # Contract checks: both mismatched_fields and discrepancies arrays must exist
    assert "mismatched_fields" in report
    assert "discrepancies" in report
    assert len(report["mismatched_fields"]) == 0
    assert len(report["discrepancies"]) == 0


def test_field_by_field_mismatches_detected(ai_test_env):
    """Verify that mismatches in amount, bank, fdr number, and dates are caught with MISMATCH status."""
    fdr = ai_test_env["fdr"]
    mismatched_extracted = {
        "fdr_number": "FDR-WRONG-0001",
        "bank_name": "Punjab National Bank",
        "branch_name": "Different Branch",
        "amount": "750000.00",
        "issue_date": "2024-01-01",
        "maturity_date": "2028-01-01",
    }
    report = detect_fdr_discrepancies(mismatched_extracted, fdr, is_scanned=False)

    assert report["overall_result"] == "DISCREPANCY_FOUND"
    fields = report["field_analysis"]

    assert fields["fdr_number"]["status"] == "MISMATCH"
    assert fields["bank_name"]["status"] == "MISMATCH"
    assert fields["branch_name"]["status"] == "MISMATCH"
    assert fields["amount"]["status"] == "MISMATCH"
    assert fields["issue_date"]["status"] == "MISMATCH"
    assert fields["maturity_date"]["status"] == "MISMATCH"

    # Frontend discrepancies array must contain all 6 mismatches
    assert len(report["discrepancies"]) == 6
    fields_in_disc = [d["field"] for d in report["discrepancies"]]
    assert "amount" in fields_in_disc
    assert "fdr_number" in fields_in_disc
    assert "bank_name" in fields_in_disc


def test_missing_or_unreadable_fields_never_match(ai_test_env):
    """Verify missing/unreadable fields are classified as MANUAL_REVIEW_REQUIRED and NEVER as MATCH."""
    fdr = ai_test_env["fdr"]
    sparse_extracted = {
        "fdr_number": "FDR-AI-9999",
        "bank_name": "Canara Bank",
        # amount, branch, issue_date, maturity_date missing
    }
    report = detect_fdr_discrepancies(sparse_extracted, fdr, is_scanned=False)

    assert report["overall_result"] == "MANUAL_REVIEW_REQUIRED"
    fields = report["field_analysis"]

    assert fields["fdr_number"]["status"] == "MATCH"
    assert fields["bank_name"]["status"] == "MATCH"
    assert fields["amount"]["status"] == "MANUAL_REVIEW_REQUIRED"
    assert fields["branch_name"]["status"] == "MANUAL_REVIEW_REQUIRED"
    assert fields["issue_date"]["status"] == "MANUAL_REVIEW_REQUIRED"
    assert fields["maturity_date"]["status"] == "MANUAL_REVIEW_REQUIRED"

    # Missing fields must be included in discrepancies array for officer attention
    disc_fields = [d["field"] for d in report["discrepancies"]]
    assert "amount" in disc_fields
    assert "maturity_date" in disc_fields


def test_confidence_calculation_meaningful_and_honest():
    """Verify confidence indicators: honest word-level confidence for scanned OCR vs N/A for digital."""
    # 1. Digital PDF extraction -> confidence must be None
    conf_digital = compute_field_confidence("1500000.00", word_confidences=[], is_scanned=False)
    assert conf_digital is None

    # 2. Scanned OCR with matching word confidences
    mock_word_confs = [
        {"word": "FDR-AI-9999", "conf": 96.0},
        {"word": "Canara", "conf": 94.0},
        {"word": "Bank", "conf": 98.0},
        {"word": "1500000.00", "conf": 88.5},
    ]
    conf_scanned_bank = compute_field_confidence("Canara Bank", mock_word_confs, is_scanned=True)
    assert conf_scanned_bank is not None
    assert conf_scanned_bank == 96.0  # (94.0 + 98.0) / 2

    # 3. Scanned OCR where token cannot be found -> must return None (N/A) rather than a fake score
    conf_unfound = compute_field_confidence("NonexistentToken", mock_word_confs, is_scanned=True)
    assert conf_unfound is None

    # 4. None / empty field value -> must return None
    assert compute_field_confidence(None, mock_word_confs, is_scanned=True) is None


def test_joint_lien_detection_scenarios():
    """Verify AICTE joint lien clause detection: DETECTED, AMBIGUOUS, and NOT_DETECTED."""
    # 1. Clear joint lien endorsement
    text_detected = (
        "Canara Bank Term Deposit Receipt.\n"
        "Deposit FDR-AI-9999 in joint names of Principal Apex Institute and Member Secretary AICTE.\n"
        "Lien marked in favour of AICTE. No premature encashment without prior NOC."
    )
    res_det = detect_joint_lien(text_detected)
    assert res_det["detected"] is True
    assert res_det["status"] == "DETECTED"
    assert "Member Secretary AICTE" in res_det["supporting_text"]
    assert "Automated clause detection only" in res_det["disclaimer"]

    # 2. Ambiguous wording (AICTE mentioned, but no explicit lien/pledge keywords)
    text_ambiguous = (
        "Canara Bank Term Deposit Receipt.\n"
        "Approved by AICTE New Delhi for institutional operations.\n"
        "Ordinary commercial fixed deposit."
    )
    res_amb = detect_joint_lien(text_ambiguous)
    assert res_amb["detected"] is False
    assert res_amb["status"] == "AMBIGUOUS"
    assert "AICTE" in (res_amb["supporting_text"] or "")

    # 3. Not detected
    text_none = "Standard Personal Fixed Deposit. Repayable to depositor on maturity."
    res_none = detect_joint_lien(text_none)
    assert res_none["detected"] is False
    assert res_none["status"] == "NOT_DETECTED"
    assert res_none["supporting_text"] is None


def test_officer_field_level_decision_recording_and_persistence(client, ai_test_env):
    """
    Verify officer can review individual fields, decisions are stored in .analysis.json,
    and audit logs are generated for each field decision.
    """
    fdr = ai_test_env["fdr"]
    inst_user = ai_test_env["inst_user"]
    officer = ai_test_env["officer"]

    # 1. Institution uploads document
    csrf_inst = login_helper(client, inst_user.email, "ApexPass123!")
    pdf_bytes = make_pdf(
        "Canara Bank\nFDR No: FDR-AI-9999\nBranch: Shivaji Nagar, Pune\nAmount: Rs. 1,500,000.00\nIssue Date: 2025-06-01\nMaturity Date: 2030-06-01\nLien marked to Member Secretary AICTE"
    )
    up_res = client.post(
        f"/api/fdr/{fdr.id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "fdr_doc.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert up_res.status_code == 201
    doc_id = up_res.get_json()["data"]["document"]["id"]

    # 2. Officer records field-level review decisions
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    field_payload = {
        "field_reviews": {
            "amount": {"decision": "VERIFIED", "remarks": "Confirmed with bank receipt seal"},
            "bank_name": {"decision": "VERIFIED", "remarks": "Canara Bank authorized"},
            "joint_lien": {"decision": "VERIFIED", "remarks": "AICTE joint lien clause endorsed"},
        },
        "decision": "VERIFIED",
        "remarks": "All essential parameters verified against bank certificate.",
    }
    rev_res = client.post(
        f"/api/fdr/{fdr.id}/documents/{doc_id}/verify",
        json=field_payload,
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.get_json()
    assert rev_data["success"] is True
    assert "field_reviews" in rev_data
    assert rev_data["field_reviews"]["amount"]["decision"] == "VERIFIED"
    assert rev_data["field_reviews"]["joint_lien"]["decision"] == "VERIFIED"

    # 3. Verify persistence: reload document detail via GET endpoint
    get_res = client.get(f"/api/fdr/{fdr.id}/documents/{doc_id}")
    assert get_res.status_code == 200
    report = get_res.get_json()["data"]["discrepancy_report"]
    assert "field_reviews" in report
    assert report["field_reviews"]["amount"]["decision"] == "VERIFIED"
    assert report["field_reviews"]["amount"]["reviewed_by_email"] == officer.email
    assert "document_review" in report
    assert report["document_review"]["decision"] == "VERIFIED"

    # 4. Verify AuditLog entries were generated
    logs = AuditLog.query.filter_by(entity_type="Document", entity_id=doc_id).all()
    actions = [l.action for l in logs]
    assert "DOCUMENT_FIELD_REVIEW_AMOUNT" in actions
    assert "DOCUMENT_FIELD_REVIEW_BANK_NAME" in actions
    assert "DOCUMENT_FIELD_REVIEW_JOINT_LIEN" in actions
    assert "DOCUMENT_DECISION_VERIFIED" in actions

    # 5. Verify official FDR record was NOT altered
    fdr_db = db.session.get(FDRRecord, fdr.id)
    assert fdr_db.amount == Decimal("1500000.00")
    assert fdr_db.fdr_number == "FDR-AI-9999"


def test_unauthorized_institution_cannot_record_field_review(client, ai_test_env):
    """Verify that institution users cannot record officer verification decisions (403)."""
    fdr = ai_test_env["fdr"]
    inst_user = ai_test_env["inst_user"]

    csrf_inst = login_helper(client, inst_user.email, "ApexPass123!")
    pdf_bytes = make_pdf("Canara Bank FDR No: FDR-AI-9999")
    up_res = client.post(
        f"/api/fdr/{fdr.id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "fdr_doc2.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_inst},
    )
    doc_id = up_res.get_json()["data"]["document"]["id"]

    # Institution user attempts to verify field
    inst_attempt = client.post(
        f"/api/fdr/{fdr.id}/documents/{doc_id}/verify",
        json={"field_reviews": {"amount": {"decision": "VERIFIED"}}},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert inst_attempt.status_code == 403


def test_invalid_field_names_and_decisions_rejected(client, ai_test_env):
    """Verify that invalid field names or decisions are rejected with HTTP 400."""
    fdr = ai_test_env["fdr"]
    officer = ai_test_env["officer"]
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")

    pdf_bytes = make_pdf("Canara Bank FDR No: FDR-AI-9999")
    up_res = client.post(
        f"/api/fdr/{fdr.id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "fdr_doc3.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf_officer},
    )
    doc_id = up_res.get_json()["data"]["document"]["id"]

    # 1. Invalid field name
    bad_field = client.post(
        f"/api/fdr/{fdr.id}/documents/{doc_id}/verify",
        json={"field_reviews": {"arbitrary_hacked_field": {"decision": "VERIFIED"}}},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert bad_field.status_code == 400
    assert "Invalid field name" in bad_field.get_json()["error"]

    # 2. Invalid field decision
    bad_dec = client.post(
        f"/api/fdr/{fdr.id}/documents/{doc_id}/verify",
        json={"field_reviews": {"amount": {"decision": "ILLEGAL_DECISION"}}},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert bad_dec.status_code == 400
    assert "Invalid decision" in bad_dec.get_json()["error"]


def test_synthetic_scenarios_generation_and_formats(ai_test_env):
    """Test generating all 8 synthetic scenarios across digital PDF, scanned PDF, and PNG formats."""
    from app.services.synthetic_fdr_generator import (
        SYNTHETIC_SCENARIOS,
        SYNTHETIC_WATERMARK,
        generate_synthetic_fdr_document,
    )
    from app.services.ocr_service import extract_text_from_document
    fdr = ai_test_env["fdr"]

    # 1. Test each scenario in digital vector PDF format
    for scen_id in SYNTHETIC_SCENARIOS:
        raw_bytes, mime, filename = generate_synthetic_fdr_document(fdr, scen_id, "pdf")
        assert mime == "application/pdf"
        assert filename.startswith("DEMO_RECEIPT_")
        assert raw_bytes.startswith(b"%PDF-")

        # Open and verify safety watermark text
        doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
        text = doc[0].get_text()
        doc.close()
        assert "SYNTHETIC DEMO DOCUMENT" in text
        assert "NOT ISSUED BY A BANK" in text
        assert "LEGAL NOTICE" in text

    # 2. Test scanned raster PDF format
    scanned_bytes, mime, filename = generate_synthetic_fdr_document(fdr, "MATCHING_FDR", "scanned_pdf")
    assert mime == "application/pdf"
    assert filename.startswith("DEMO_SCANNED_")
    assert scanned_bytes.startswith(b"%PDF-")

    # 3. Test PNG image format
    img_bytes, mime, filename = generate_synthetic_fdr_document(fdr, "MATCHING_FDR", "image")
    assert mime == "image/png"
    assert filename.startswith("DEMO_IMAGE_")
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_synthetic_scenarios_ocr_analysis_outcomes(ai_test_env):
    """Verify that extracted text for each scenario produces the exact expected discrepancy results."""
    from app.services.synthetic_fdr_generator import generate_synthetic_fdr_pdf
    from app.services.ocr_service import extract_fdr_fields, detect_fdr_discrepancies
    fdr = ai_test_env["fdr"]

    scenarios_to_check = {
        "MATCHING_FDR": ("MATCH", "DETECTED"),
        "MATURITY_DATE_MISMATCH": ("DISCREPANCY_FOUND", "DETECTED"),
        "AMOUNT_MISMATCH": ("DISCREPANCY_FOUND", "DETECTED"),
        "FDR_NUMBER_MISMATCH": ("DISCREPANCY_FOUND", "DETECTED"),
        "MISSING_FIELDS": ("MANUAL_REVIEW_REQUIRED", "NOT_DETECTED"),
        "JOINT_LIEN_DETECTED": ("MATCH", "DETECTED"),
        "JOINT_LIEN_AMBIGUOUS": ("MATCH", "AMBIGUOUS"),
        "JOINT_LIEN_NOT_DETECTED": ("MATCH", "NOT_DETECTED"),
    }

    for scen_id, (expected_res, expected_lien) in scenarios_to_check.items():
        pdf_bytes = generate_synthetic_fdr_pdf(fdr, scen_id)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = doc[0].get_text()
        doc.close()

        extracted_fields = extract_fdr_fields(extracted_text)
        analysis = detect_fdr_discrepancies(extracted_fields, fdr, document_text=extracted_text)

        assert analysis["overall_result"] == expected_res, f"Scenario {scen_id} expected {expected_res}, got {analysis['overall_result']}"
        assert analysis["joint_lien"]["status"] == expected_lien, f"Scenario {scen_id} expected lien {expected_lien}, got {analysis['joint_lien']['status']}"


def test_synthetic_document_api_endpoints(client, ai_test_env):
    """Test the dev-only endpoints: scenarios catalog, file download, and direct scenario loading."""
    fdr = ai_test_env["fdr"]
    officer = ai_test_env["officer"]
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")

    # 1. GET /scenarios
    scen_res = client.get(
        f"/api/fdr/{fdr.id}/synthetic-documents/scenarios",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert scen_res.status_code == 200
    scen_data = scen_res.get_json()
    assert scen_data["success"] is True
    assert len(scen_data["scenarios"]) == 8

    # 2. GET /download
    dl_res = client.get(
        f"/api/fdr/{fdr.id}/synthetic-documents/download?scenario=AMOUNT_MISMATCH&format=pdf",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert dl_res.status_code == 200
    assert dl_res.mimetype == "application/pdf"
    assert "DEMO_RECEIPT_" in dl_res.headers.get("Content-Disposition", "")
    assert dl_res.data.startswith(b"%PDF-")

    # 3. POST /load (Amount Mismatch scenario)
    load_res = client.post(
        f"/api/fdr/{fdr.id}/synthetic-documents/load",
        json={"scenario": "AMOUNT_MISMATCH", "format": "pdf"},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert load_res.status_code == 201
    load_json = load_res.get_json()
    assert load_json["success"] is True
    assert load_json["document"]["id"] is not None
    assert load_json["discrepancy_report"]["overall_result"] == "DISCREPANCY_FOUND"
    assert "amount" in [m["field"] for m in load_json["discrepancy_report"]["mismatched_fields"]]

    # 4. Verify document appears in list and detail route
    doc_id = load_json["document"]["id"]
    det_res = client.get(
        f"/api/fdr/{fdr.id}/documents/{doc_id}",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert det_res.status_code == 200
    det_data = det_res.get_json()["data"]
    assert "field_analysis" in det_data["discrepancy_report"]
    assert det_data["discrepancy_report"]["field_analysis"]["amount"]["status"] == "MISMATCH"


def test_synthetic_endpoints_forbidden_in_production(client, ai_test_env, monkeypatch):
    """Verify that all synthetic document endpoints return HTTP 403 in production mode."""
    fdr = ai_test_env["fdr"]
    officer = ai_test_env["officer"]
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")

    # Mock is_demo_environment to False (production)
    import app.services.synthetic_receipt_service
    monkeypatch.setattr(app.services.synthetic_receipt_service, "is_demo_environment", lambda: False)

    # Scenarios endpoint
    res1 = client.get(
        f"/api/fdr/{fdr.id}/synthetic-documents/scenarios",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res1.status_code == 403
    assert res1.get_json()["code"] == "DEMO_DISABLED"

    # Download endpoint
    res2 = client.get(
        f"/api/fdr/{fdr.id}/synthetic-documents/download",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res2.status_code == 403
    assert res2.get_json()["code"] == "DEMO_DISABLED"

    # Load endpoint
    res3 = client.post(
        f"/api/fdr/{fdr.id}/synthetic-documents/load",
        json={"scenario": "MATCHING_FDR"},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert res3.status_code == 403
    assert res3.get_json()["code"] == "DEMO_DISABLED"


def test_ocr_meaningful_text_and_fallback_pipeline(tmp_path):
    """Test is_meaningful_pdf_text and fallback triggering on scanned/empty PDFs."""
    from app.services.ocr_service import (
        is_meaningful_pdf_text,
        extract_text_from_pdf,
        extract_text_from_document,
    )

    # 1. Meaningful text tests
    assert is_meaningful_pdf_text("") is False
    assert is_meaningful_pdf_text("   \n\t  ") is False
    assert is_meaningful_pdf_text("Page 1") is False
    assert is_meaningful_pdf_text("Fixed Deposit Receipt Canara Bank Branch Amount 1500000") is True

    # 2. Pure scanned PDF with 0 vector text
    blank_pdf = tmp_path / "blank_scanned.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    # Draw pure vector shape without text
    page.draw_rect(pymupdf.Rect(10, 10, 390, 390), fill=(0.9, 0.9, 0.9))
    doc.save(str(blank_pdf))
    doc.close()

    result = extract_text_from_document(blank_pdf)
    assert result.fallback_triggered is True
    assert result.is_scanned is True
    assert result.extraction_method in ("TESSERACT_OCR", "FAILED")
    assert result.pages_processed == 1


def test_joint_lien_status_unavailable_on_empty_text():
    """Verify that unavailable/failed text extraction yields UNAVAILABLE rather than false NOT_DETECTED."""
    # 1. Empty text / failed extraction
    r1 = detect_joint_lien("", extraction_method="FAILED")
    assert r1["status"] == "UNAVAILABLE"
    assert r1["detected"] is False
    assert "could not be extracted" in r1["note"]

    # 2. Non-empty text genuinely lacking AICTE lien clause
    r2 = detect_joint_lien("Ordinary commercial term deposit repayable to depositor on maturity.")
    assert r2["status"] == "NOT_DETECTED"
    assert r2["detected"] is False

    # 3. Explicit joint lien clause
    r3 = detect_joint_lien("Jointly held under lien in favour of AICTE Member Secretary.")
    assert r3["status"] == "DETECTED"
    assert r3["detected"] is True


def test_extraction_diagnostics_structure(ai_test_env):
    """Test that discrepancy report contains all required diagnostics fields."""
    fdr = ai_test_env["fdr"]
    report = detect_fdr_discrepancies(
        extracted={"fdr_number": "FDR-AI-9999"},
        fdr=fdr,
        ocr_confidence=88.5,
        word_confidences=[{"word": "FDR-AI-9999", "conf": 92.0}],
        is_scanned=True,
        document_text="FDR-AI-9999 Canara Bank",
        extraction_method="TESSERACT_OCR",
        fallback_triggered=True,
        pages_processed=2,
        extraction_error=None,
    )
    assert report["extraction_method"] == "TESSERACT_OCR"
    assert report["fallback_triggered"] is True
    assert report["pages_processed"] == 2
    assert report["raw_text"] == "FDR-AI-9999 Canara Bank"
    assert report["is_digital_extraction"] is False
    assert report["confidence_display"] == "88%"
    assert report["extraction_diagnostics"]["method"] == "TESSERACT_OCR"
    assert report["extraction_diagnostics"]["status"] == "SUCCESS"


def test_scanned_pdf_and_image_synthetic_pipeline(client, ai_test_env):
    """Test loading and verifying scanned PDF and PNG image synthetic scenarios."""
    fdr = ai_test_env["fdr"]
    officer = ai_test_env["officer"]
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")

    # 1. Load scanned PDF scenario
    scanned_res = client.post(
        f"/api/fdr/{fdr.id}/synthetic-documents/load",
        json={"scenario": "MATCHING_FDR", "format": "scanned_pdf"},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert scanned_res.status_code == 201
    scanned_data = scanned_res.get_json()
    assert scanned_data["success"] is True
    assert scanned_data["discrepancy_report"]["overall_result"] == "MATCH"
    assert scanned_data["discrepancy_report"]["pages_processed"] >= 1

    # 2. Load PNG image scenario
    img_res = client.post(
        f"/api/fdr/{fdr.id}/synthetic-documents/load",
        json={"scenario": "MATCHING_FDR", "format": "image"},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert img_res.status_code == 201
    img_data = img_res.get_json()
    assert img_data["success"] is True
    assert img_data["discrepancy_report"]["overall_result"] == "MATCH"
    assert img_data["discrepancy_report"]["pages_processed"] == 1



