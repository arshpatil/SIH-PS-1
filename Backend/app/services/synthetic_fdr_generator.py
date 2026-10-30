"""
Service for generating synthetic test FDR documents (digital PDF, scanned PDF, PNG image)
for demonstration, automated testing, and field-by-field verification audits.

SAFETY & COMPLIANCE REQUIREMENTS:
- Prominently marked: "SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK — FOR SOFTWARE TESTING ONLY"
- Fictional bank & reference details.
- Fictional test scenarios specifically designed to exercise:
  1. MATCHING_FDR
  2. MATURITY_DATE_MISMATCH
  3. AMOUNT_MISMATCH
  4. FDR_NUMBER_MISMATCH
  5. MISSING_FIELDS
  6. JOINT_LIEN_DETECTED
  7. JOINT_LIEN_AMBIGUOUS
  8. JOINT_LIEN_NOT_DETECTED
- Never copies private customer or institutional financial data.
- Never imitates a real bank's official security features, signatures, stamps, or seals.
- Strictly prohibited in production environments.
"""

from datetime import date, timedelta
from decimal import Decimal
import io
import os
from typing import Optional
from flask import current_app
import pymupdf
from PIL import Image

from app.models.fdr import FDRRecord
from app.services.synthetic_receipt_service import is_demo_environment


SYNTHETIC_WATERMARK = "SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK — FOR SOFTWARE TESTING ONLY"

SYNTHETIC_SCENARIOS = {
    "MATCHING_FDR": {
        "id": "MATCHING_FDR",
        "name": "Scenario 1: Perfect Match (All 6 Fields)",
        "description": "All 6 supported fields (FDR number, bank, branch, amount, issue date, maturity date) match registered FDR values with AICTE joint-lien endorsement.",
        "expected_result": "MATCH",
        "expected_lien": "DETECTED",
        "color": "emerald",
    },
    "MATURITY_DATE_MISMATCH": {
        "id": "MATURITY_DATE_MISMATCH",
        "name": "Scenario 2: Maturity Date Mismatch",
        "description": "Maturity date on receipt differs by +1 year from registered FDR maturity date. Tests date discrepancy detection.",
        "expected_result": "DISCREPANCY_FOUND",
        "expected_lien": "DETECTED",
        "color": "rose",
    },
    "AMOUNT_MISMATCH": {
        "id": "AMOUNT_MISMATCH",
        "name": "Scenario 3: Principal Amount Mismatch",
        "description": "Deposit amount on receipt is modified (e.g. registered INR 15,00,000 vs document INR 10,00,000). Tests decimal discrepancy detection.",
        "expected_result": "DISCREPANCY_FOUND",
        "expected_lien": "DETECTED",
        "color": "rose",
    },
    "FDR_NUMBER_MISMATCH": {
        "id": "FDR_NUMBER_MISMATCH",
        "name": "Scenario 4: FDR Number Mismatch",
        "description": "Receipt presents a different FDR reference number. Tests exact reference discrepancy detection.",
        "expected_result": "DISCREPANCY_FOUND",
        "expected_lien": "DETECTED",
        "color": "rose",
    },
    "MISSING_FIELDS": {
        "id": "MISSING_FIELDS",
        "name": "Scenario 5: Missing / Incomplete Fields",
        "description": "Receipt omits branch name, amount, and maturity date. Tests missing-field classification into MANUAL_REVIEW_REQUIRED.",
        "expected_result": "MANUAL_REVIEW_REQUIRED",
        "expected_lien": "NOT_DETECTED",
        "color": "amber",
    },
    "JOINT_LIEN_DETECTED": {
        "id": "JOINT_LIEN_DETECTED",
        "name": "Scenario 6: AICTE Joint Lien Clause Detected",
        "description": "Explicit joint lien endorsement clause naming AICTE Member Secretary with premature withdrawal restrictions.",
        "expected_result": "MATCH",
        "expected_lien": "DETECTED",
        "color": "emerald",
    },
    "JOINT_LIEN_AMBIGUOUS": {
        "id": "JOINT_LIEN_AMBIGUOUS",
        "name": "Scenario 7: Ambiguous Joint Lien Endorsement",
        "description": "Mentions AICTE New Delhi regulations, but lacks explicit joint holding or lien pledge clause.",
        "expected_result": "MATCH",
        "expected_lien": "AMBIGUOUS",
        "color": "amber",
    },
    "JOINT_LIEN_NOT_DETECTED": {
        "id": "JOINT_LIEN_NOT_DETECTED",
        "name": "Scenario 8: No Joint Lien Endorsement",
        "description": "Ordinary commercial deposit receipt lacking any AICTE or joint-lien endorsement wording.",
        "expected_result": "MATCH",
        "expected_lien": "NOT_DETECTED",
        "color": "slate",
    },
}


def build_scenario_data(fdr: FDRRecord, scenario_id: str) -> dict:
    """Build field values and text blocks for a given scenario based on an FDR record."""
    inst_name = fdr.institution.name if fdr.institution else "Demo Technical College"
    reg_num = fdr.fdr_number or "FDR-DEMO-001"
    reg_bank = fdr.bank_name or "State Bank of India"
    reg_branch = fdr.branch_name or "Main Branch, Shivaji Nagar"
    reg_amt = fdr.amount if fdr.amount is not None else Decimal("1000000.00")
    reg_issue = fdr.issue_date if fdr.issue_date else date.today()
    reg_mat = fdr.maturity_date if fdr.maturity_date else (date.today() + timedelta(days=1095))

    data = {
        "scenario_id": scenario_id,
        "institution_name": inst_name,
        "fdr_number": reg_num,
        "bank_name": reg_bank,
        "branch_name": reg_branch,
        "amount": f"{Decimal(str(reg_amt)).quantize(Decimal('0.01')):.2f}",
        "issue_date": reg_issue.isoformat(),
        "maturity_date": reg_mat.isoformat(),
        "lien_clause": (
            f"Jointly held in the name of The Principal, {inst_name} and The Member Secretary, AICTE. "
            "Lien marked in favour of All India Council for Technical Education. "
            "No premature withdrawal or encashment permitted without prior written consent from AICTE."
        ),
        "show_branch": True,
        "show_amount": True,
        "show_maturity": True,
    }

    if scenario_id == "MATURITY_DATE_MISMATCH":
        try:
            mismatched_mat = reg_mat.replace(year=reg_mat.year + 1)
        except ValueError:
            mismatched_mat = reg_mat + timedelta(days=365)
        data["maturity_date"] = mismatched_mat.isoformat()

    elif scenario_id == "AMOUNT_MISMATCH":
        mismatched_amt = reg_amt + Decimal("500000.00")
        data["amount"] = f"{mismatched_amt:.2f}"

    elif scenario_id == "FDR_NUMBER_MISMATCH":
        data["fdr_number"] = f"{reg_num}-MISMATCH-99"

    elif scenario_id == "MISSING_FIELDS":
        data["show_branch"] = False
        data["show_amount"] = False
        data["show_maturity"] = False
        data["lien_clause"] = "General banking deposit. Terms as per bank schedule."

    elif scenario_id == "JOINT_LIEN_AMBIGUOUS":
        data["lien_clause"] = (
            f"Submitted towards AICTE Approval Process Handbook compliance for {inst_name}. "
            "Standard commercial term deposit rules and regulations apply."
        )

    elif scenario_id == "JOINT_LIEN_NOT_DETECTED":
        data["lien_clause"] = "Ordinary commercial fixed deposit. Repayable to depositor on maturity."

    return data


def generate_synthetic_fdr_pdf(fdr: FDRRecord, scenario_id: str = "MATCHING_FDR") -> bytes:
    """
    Generate a downloadable synthetic digital PDF for a specific scenario.
    Adheres strictly to synthetic document safety standards with prominent watermarks.
    """
    s_data = build_scenario_data(fdr, scenario_id)

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # Standard A4 size

    # Background canvas
    page.draw_rect(pymupdf.Rect(20, 20, 575, 822), color=(0.85, 0.88, 0.92), width=1)

    # Top Watermark Warning Banner
    page.draw_rect(pymupdf.Rect(25, 25, 570, 65), fill=(0.95, 0.90, 0.90), color=(0.85, 0.20, 0.20), width=1.5)
    page.insert_text((35, 42), SYNTHETIC_WATERMARK, fontsize=9, color=(0.75, 0.1, 0.1), fontname="helv")
    page.insert_text(
        (35, 56),
        "DEVELOPMENT & DEMO ENVIRONMENT ONLY — FICTIONAL FINANCIAL TEST DATA",
        fontsize=8,
        color=(0.6, 0.1, 0.1),
        fontname="helv",
    )

    # Bank Header (Clearly marked fictional)
    page.insert_text(
        (40, 100),
        f"[DEMO SIMULATION] {s_data['bank_name'].upper()}",
        fontsize=16,
        color=(0.1, 0.2, 0.4),
        fontname="helv",
    )
    if s_data["show_branch"]:
        page.insert_text(
            (40, 118),
            f"Branch: {s_data['branch_name']}",
            fontsize=10,
            color=(0.3, 0.3, 0.3),
            fontname="helv",
        )

    page.insert_text(
        (40, 145),
        "FIXED DEPOSIT RECEIPT / TERM DEPOSIT ADVICE",
        fontsize=12,
        color=(0.1, 0.1, 0.1),
        fontname="helv",
    )
    page.draw_line(pymupdf.Point(40, 155), pymupdf.Point(555, 155), color=(0.7, 0.7, 0.7), width=1)

    # Key Parameters Table / Block
    curr_y = 180
    line_h = 24

    params = [
        f"FDR Number: {s_data['fdr_number']}",
        f"Account / Depositor: The Principal, {s_data['institution_name']}",
    ]
    if s_data["show_amount"]:
        params.append(f"Deposit Amount: INR {float(s_data['amount']):,.2f} (Rs. {s_data['amount']})")
    params.append(f"Date of Issue: {s_data['issue_date']}")
    if s_data["show_maturity"]:
        params.append(f"Date of Maturity: {s_data['maturity_date']}")

    for line in params:
        page.insert_text((50, curr_y), line, fontsize=10, color=(0.1, 0.1, 0.1), fontname="helv")
        curr_y += line_h

    curr_y += 15

    # Statutory Joint-Lien Endorsement Box
    page.draw_rect(pymupdf.Rect(40, curr_y, 555, curr_y + 85), fill=(0.97, 0.98, 0.99), color=(0.75, 0.8, 0.85), width=1)
    page.insert_text(
        (50, curr_y + 20),
        "STATUTORY LIEN / ENDORSEMENT CLAUSE:",
        fontsize=9,
        color=(0.15, 0.25, 0.45),
        fontname="helv",
    )

    # Wrap lien clause text
    clause_text = s_data["lien_clause"]
    words = clause_text.split()
    line1 = " ".join(words[:14])
    line2 = " ".join(words[14:28])
    line3 = " ".join(words[28:])

    page.insert_text((50, curr_y + 38), line1, fontsize=9, color=(0.2, 0.2, 0.2), fontname="helv")
    if line2:
        page.insert_text((50, curr_y + 52), line2, fontsize=9, color=(0.2, 0.2, 0.2), fontname="helv")
    if line3:
        page.insert_text((50, curr_y + 66), line3, fontsize=9, color=(0.2, 0.2, 0.2), fontname="helv")

    curr_y += 115

    # Scenario explanation for tester
    scen_info = SYNTHETIC_SCENARIOS.get(scenario_id, {})
    page.draw_rect(pymupdf.Rect(40, curr_y, 555, curr_y + 90), fill=(0.95, 0.95, 0.95), color=(0.8, 0.8, 0.8), width=1)
    page.insert_text((50, curr_y + 20), f"TEST SCENARIO: {scen_info.get('name', scenario_id)}", fontsize=10, color=(0.1, 0.1, 0.1), fontname="helv")
    page.insert_text((50, curr_y + 38), f"Expected Overall Outcome: {scen_info.get('expected_result', 'N/A')}", fontsize=9, color=(0.2, 0.4, 0.2), fontname="helv")
    page.insert_text((50, curr_y + 54), f"Expected Joint Lien Status: {scen_info.get('expected_lien', 'N/A')}", fontsize=9, color=(0.2, 0.2, 0.5), fontname="helv")
    page.insert_text((50, curr_y + 70), "Purpose: Test AI-Powered Document Verification field audit & discrepancy detection.", fontsize=8, color=(0.4, 0.4, 0.4), fontname="helv")

    # Bottom Safety & Legal Disclaimer
    page.draw_line(pymupdf.Point(40, 750), pymupdf.Point(555, 750), color=(0.8, 0.2, 0.2), width=1)
    page.insert_text(
        (40, 765),
        "LEGAL NOTICE: SYNTHETIC SOFTWARE ARTIFACT — NOT ISSUED BY ANY COMMERCIAL BANK.",
        fontsize=8,
        color=(0.7, 0.1, 0.1),
        fontname="helv",
    )
    page.insert_text(
        (40, 778),
        "Generated solely for Portal Software automated testing. Does not confer financial or legal entitlement.",
        fontsize=7,
        color=(0.5, 0.5, 0.5),
        fontname="helv",
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_synthetic_fdr_scanned_pdf(fdr: FDRRecord, scenario_id: str = "MATCHING_FDR") -> bytes:
    """
    Generate a scanned-style PDF (single page containing rasterized image).
    Because bank scanners embed an invisible OCR text layer (PDF Searchable Scanned Document),
    we embed an invisible OCR text layer (render_mode=3) so the scanned document is fully readable
    both with Tesseract OCR fallback and via direct textpage extraction.
    """
    # 1. Generate digital PDF
    digital_pdf = generate_synthetic_fdr_pdf(fdr, scenario_id)

    # 2. Extract the digital text and render raster pixmap
    src_doc = pymupdf.open(stream=digital_pdf, filetype="pdf")
    page = src_doc[0]
    extracted_text = page.get_text()
    pix = page.get_pixmap(dpi=150)
    png_bytes = pix.tobytes("png")
    src_doc.close()

    # 3. Create new PDF containing the raster image + invisible OCR text layer
    out_doc = pymupdf.open()
    new_page = out_doc.new_page(width=pix.width * 72 / 150, height=pix.height * 72 / 150)
    new_page.insert_image(new_page.rect, stream=png_bytes)
    # Embed invisible text layer (render_mode=3) matching standard searchable scanned document practices
    if extracted_text:
        new_page.insert_text((40, 40), extracted_text, fontsize=8, render_mode=3)
    scanned_pdf_bytes = out_doc.tobytes()
    out_doc.close()

    return scanned_pdf_bytes


def generate_synthetic_fdr_image(fdr: FDRRecord, scenario_id: str = "MATCHING_FDR") -> bytes:
    """
    Generate a PNG image receipt suitable for testing image upload and Tesseract image OCR.
    Embeds the OCR text layer in PNG metadata (PngInfo) so image uploads can be tested
    both with external Tesseract binary and with embedded scanner text metadata.
    """
    from PIL import Image as PILImage, PngImagePlugin

    digital_pdf = generate_synthetic_fdr_pdf(fdr, scenario_id)
    src_doc = pymupdf.open(stream=digital_pdf, filetype="pdf")
    page = src_doc[0]
    extracted_text = page.get_text()
    pix = page.get_pixmap(dpi=150)
    png_bytes = pix.tobytes("png")
    src_doc.close()

    # Embed OCR text in PNG metadata chunk
    pil_img = PILImage.open(io.BytesIO(png_bytes))
    png_info = PngImagePlugin.PngInfo()
    if extracted_text:
        png_info.add_text("OCR_TEXT", extracted_text)
    out_buf = io.BytesIO()
    pil_img.save(out_buf, format="PNG", pnginfo=png_info)
    return out_buf.getvalue()


def generate_synthetic_fdr_document(
    fdr: FDRRecord,
    scenario_id: str = "MATCHING_FDR",
    doc_format: str = "pdf",
) -> tuple[bytes, str, str]:
    """
    Main entry point for generating synthetic FDR documents.
    Returns: (bytes, mime_type, filename)
    """
    clean_num = "".join(c for c in fdr.fdr_number if c.isalnum() or c in "-_") or "fdr"
    clean_scen = scenario_id.lower()

    if doc_format in ("scanned_pdf", "scanned"):
        raw_bytes = generate_synthetic_fdr_scanned_pdf(fdr, scenario_id)
        return raw_bytes, "application/pdf", f"DEMO_SCANNED_{clean_num}_{clean_scen}.pdf"

    elif doc_format in ("image", "png"):
        raw_bytes = generate_synthetic_fdr_image(fdr, scenario_id)
        return raw_bytes, "image/png", f"DEMO_IMAGE_{clean_num}_{clean_scen}.png"

    else:
        # Default digital PDF
        raw_bytes = generate_synthetic_fdr_pdf(fdr, scenario_id)
        return raw_bytes, "application/pdf", f"DEMO_RECEIPT_{clean_num}_{clean_scen}.pdf"
