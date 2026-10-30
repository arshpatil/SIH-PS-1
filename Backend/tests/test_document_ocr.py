from datetime import date
from decimal import Decimal
import io
from pathlib import Path
import pytest
from PIL import Image
import pymupdf

from app.extensions import db
from app.models.enums import DocumentProcessingStatus, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User
from app.services.ocr_service import detect_fdr_discrepancies, extract_fdr_fields


@pytest.fixture
def doc_test_env(app):
    """Seed test institutions, users, and FDRs for document and OCR tests."""
    inst_a = Institution(
        institution_code="AICTE-DOC-A",
        name="Alpha Engineering Institute",
        contact_email="director@alpha.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-DOC-B",
        name="Beta Technical College",
        contact_email="director@beta.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    user_a = User(
        full_name="Registrar Alpha",
        email="user_a@alpha.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a.set_password("AlphaPass123!")

    user_b = User(
        full_name="Registrar Beta",
        email="user_b@beta.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_b.id,
        is_active=True,
    )
    user_b.set_password("BetaPass123!")

    officer = User(
        full_name="AICTE Officer",
        email="officer_doc@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    db.session.add_all([user_a, user_b, officer])
    db.session.commit()

    fdr_a = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-DOC-101",
        bank_name="State Bank of India",
        branch_name="Connaught Place, New Delhi",
        amount=Decimal("500000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    fdr_b = FDRRecord(
        institution_id=inst_b.id,
        fdr_number="FDR-DOC-202",
        bank_name="HDFC Bank",
        branch_name="City Branch",
        amount=Decimal("1000000.00"),
        issue_date=date(2025, 2, 1),
        maturity_date=date(2030, 2, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_b.id,
    )
    db.session.add_all([fdr_a, fdr_b])
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "fdr_a": fdr_a,
        "fdr_b": fdr_b,
    }


def login_client(client, email, password):
    """Helper to log in and return session CSRF token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def make_synthetic_pdf(text: str) -> bytes:
    """Generate in-memory valid digital PDF containing the specified text."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_synthetic_png() -> bytes:
    """Generate in-memory valid PNG image."""
    img = Image.new("RGB", (120, 120), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_valid_pdf_and_discrepancy_match(client, doc_test_env):
    """Test uploading a valid digital PDF matching the FDR record produces MATCH status."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    matching_text = (
        "State Bank of India\n"
        "Fixed Deposit Receipt\n"
        "FDR No: FDR-DOC-101\n"
        "Branch: Connaught Place, New Delhi\n"
        "Amount: Rs. 500,000.00\n"
        "Issue Date: 2025-01-01\n"
        "Maturity Date: 2030-01-01\n"
    )
    pdf_bytes = make_synthetic_pdf(matching_text)

    response = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "sbi_receipt.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 201
    assert response.is_json
    data = response.get_json()["data"]

    # Document metadata verification
    doc_meta = data["document"]
    assert doc_meta["original_filename"] == "sbi_receipt.pdf"
    assert doc_meta["file_type"] == "application/pdf"
    assert doc_meta["processing_status"] == DocumentProcessingStatus.PROCESSED.value
    assert doc_meta["fdr_id"] == fdr_id
    assert "stored_filename" in doc_meta
    # Ensure raw server path is NOT exposed
    assert "uploads" not in doc_meta["stored_filename"]
    assert "/" not in doc_meta["stored_filename"]
    assert "\\" not in doc_meta["stored_filename"]

    # Discrepancy report verification
    report = data["discrepancy_report"]
    assert report["overall_result"] == "MATCH"
    assert len(report["mismatched_fields"]) == 0
    assert len(report["matched_fields"]) >= 4

    # Verify registered FDR record was NOT altered by OCR
    fdr = db.session.get(FDRRecord, fdr_id)
    assert fdr is not None
    assert fdr.amount == Decimal("500000.00")
    assert fdr.fdr_number == "FDR-DOC-101"


def test_upload_pdf_with_discrepancy_detected(client, doc_test_env):
    """Test uploading a PDF where amount and bank name differ triggers DISCREPANCY_FOUND."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    mismatched_text = (
        "Punjab National Bank\n"
        "FDR No: FDR-DOC-101\n"
        "Branch: Connaught Place, New Delhi\n"
        "Amount: Rs. 950,000.00\n"
        "Issue Date: 2025-01-01\n"
        "Maturity Date: 2030-01-01\n"
    )
    pdf_bytes = make_synthetic_pdf(mismatched_text)

    response = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "pnb_receipt.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 201
    report = response.get_json()["data"]["discrepancy_report"]
    assert report["overall_result"] == "DISCREPANCY_FOUND"
    mismatched_names = [m["field"] for m in report["mismatched_fields"]]
    assert "amount" in mismatched_names
    assert "bank_name" in mismatched_names


def test_upload_missing_fields_manual_review_required(client, doc_test_env):
    """Test uploading a document with sparse or missing fields flags MANUAL_REVIEW_REQUIRED."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    sparse_text = "FDR No: FDR-DOC-101\nThank you for banking with us.\n"
    pdf_bytes = make_synthetic_pdf(sparse_text)

    response = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "sparse.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 201
    report = response.get_json()["data"]["discrepancy_report"]
    assert report["overall_result"] == "MANUAL_REVIEW_REQUIRED"
    assert "amount" in report["missing_fields"]
    assert "maturity_date" in report["missing_fields"]


def test_upload_unsupported_extension_and_content_mismatch(client, doc_test_env):
    """Test rejection of unsupported file types and files with disguised extensions."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    # Unsupported extension (.exe)
    res_exe = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(b"binary"), "malware.exe")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_exe.status_code == 400
    assert "Unsupported file extension" in res_exe.get_json()["details"]["file"]

    # Disguised extension: .pdf extension with plain text content
    res_disguised = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(b"Hello plain text"), "fake.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_disguised.status_code == 400
    assert "does not match expected signature" in res_disguised.get_json()["details"]["file"]


def test_upload_empty_and_oversized_files(client, doc_test_env):
    """Test rejection of empty 0-byte files and files exceeding maximum allowed size."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    # Empty 0-byte file
    res_empty = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(b""), "empty.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.get_json()["details"]["file"]

    # Oversized file (> 10MB)
    oversized_bytes = b"%PDF-" + (b"0" * (10 * 1024 * 1024 + 100))
    res_over = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(oversized_bytes), "oversized.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_over.status_code in (400, 413)


def test_cross_institution_upload_denial(client, doc_test_env):
    """Test that institution user cannot upload documents to another institution's FDR (404)."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    other_fdr_id = doc_test_env["fdr_b"].id  # Belongs to Institution B

    pdf_bytes = make_synthetic_pdf("Some text")
    response = client.post(
        f"/api/fdr/{other_fdr_id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "cross.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 404


def test_list_and_get_document_metadata_and_report(client, doc_test_env):
    """Test listing attached documents and retrieving specific document discrepancy report."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    pdf_bytes = make_synthetic_pdf(
        "State Bank of India\nFDR No: FDR-DOC-101\nBranch: Connaught Place, New Delhi\nAmount: Rs. 500,000.00\nIssue Date: 2025-01-01\nMaturity Date: 2030-01-01"
    )
    upload_res = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "receipt_test.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    doc_id = upload_res.get_json()["data"]["document"]["id"]

    # 1. List documents for FDR
    list_res = client.get(f"/api/fdr/{fdr_id}/documents")
    assert list_res.status_code == 200
    docs = list_res.get_json()["data"]
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id
    assert docs[0]["original_filename"] == "receipt_test.pdf"

    # 2. Get specific document detail
    detail_res = client.get(f"/api/fdr/{fdr_id}/documents/{doc_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.get_json()["data"]
    assert detail_data["document"]["id"] == doc_id
    assert detail_data["discrepancy_report"]["overall_result"] == "MATCH"

    # 3. Document-to-FDR association check (document requested under wrong FDR ID -> 404)
    wrong_fdr_res = client.get(
        f"/api/fdr/{doc_test_env['fdr_b'].id}/documents/{doc_id}"
    )
    assert wrong_fdr_res.status_code == 404


def test_encrypted_and_corrupt_pdf_handling(client, doc_test_env):
    """Test safe handling of corrupt and encrypted PDFs without server crash."""
    csrf = login_client(client, "user_a@alpha.edu", "AlphaPass123!")
    fdr_id = doc_test_env["fdr_a"].id

    # 1. Corrupt PDF
    corrupt_pdf = b"%PDF-1.4\nCorrupt Header Trailer %%EOF"
    res_corrupt = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(corrupt_pdf), "corrupt.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_corrupt.status_code == 201
    doc_corrupt = res_corrupt.get_json()["data"]["document"]
    assert doc_corrupt["processing_status"] == DocumentProcessingStatus.FAILED.value

    # 2. Encrypted PDF
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 72), "Encrypted content")
    enc_bytes = doc.tobytes(
        encryption=getattr(pymupdf, "PDF_ENCRYPT_AES_256", 4), user_pw="testpassword"
    )
    doc.close()

    res_enc = client.post(
        f"/api/fdr/{fdr_id}/documents",
        data={"file": (io.BytesIO(enc_bytes), "encrypted.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_enc.status_code == 201
    doc_enc = res_enc.get_json()["data"]["document"]
    assert doc_enc["processing_status"] == DocumentProcessingStatus.FAILED.value


def test_officer_can_upload_and_view(client, doc_test_env):
    """Test AICTE officer can upload and view documents across institutions."""
    csrf = login_client(client, "officer_doc@aicte.gov.in", "OfficerPass123!")
    fdr_a_id = doc_test_env["fdr_a"].id

    pdf_bytes = make_synthetic_pdf("Verification note")
    res = client.post(
        f"/api/fdr/{fdr_a_id}/documents",
        data={"file": (io.BytesIO(pdf_bytes), "officer_check.pdf")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 201

    # Officer lists documents
    list_res = client.get(f"/api/fdr/{fdr_a_id}/documents")
    assert list_res.status_code == 200
    assert len(list_res.get_json()["data"]) >= 1
