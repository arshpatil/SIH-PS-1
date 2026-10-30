"""
Service for generating and validating synthetic dummy FDR renewal receipts
for local development, automated testing, and demonstration workflows.

SAFETY & COMPLIANCE REQUIREMENTS:
- Prominently marked "SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK".
- Uses clearly fictional bank/reference information.
- Includes institution name and FDR identifier from the selected demo record.
- Includes principal amount and proposed new maturity date without inventing official bank confirmation.
- Includes clear notes that all details are fictional and require AICTE scrutiny officer verification.
- Never imitates a real bank's official receipt, signature, stamp, or security design.
- Strictly prohibited in production environments.
"""

from datetime import date, timedelta
from decimal import Decimal
import io
import os
from typing import Optional
from flask import current_app
import pymupdf

from app.models.fdr import FDRRecord


SYNTHETIC_MARKERS = [
    "SYNTHETIC DEMO DOCUMENT",
    "NOT ISSUED BY A BANK",
    "FICTIONAL SANDBOX TEST BANK",
    "SIMULATED TEST RECEIPT",
    "LOCAL ENVIRONMENT TEST ARTIFACT",
    "DEMO / SIMULATION ONLY",
    "PROTOTYPE DEMONSTRATION ONLY",
]


def is_demo_environment() -> bool:
    """
    Check if the application is running in local development or testing demo environment.
    Strictly returns False if FLASK_ENV == 'production' or if ProductionConfig is active.
    """
    env = os.getenv("FLASK_ENV", "").lower()
    if env == "production":
        return False
    if current_app:
        if current_app.config.get("ENV") == "production":
            return False
        if current_app.config.get("TESTING"):
            return True
        if current_app.config.get("DEBUG"):
            return True
        if current_app.config.get("DEMO_MODE") is False:
            return False
    if os.getenv("DEMO_MODE", "").lower() in ("false", "0", "no"):
        return False
    return env in ("development", "testing", "")


def detect_synthetic_markers(text: str | None) -> tuple[bool, Optional[str]]:
    """
    Detect whether extracted document text contains synthetic demo markers or watermarks.
    Returns (is_synthetic, matched_marker_or_none).
    """
    if not text:
        return False, None
    upper_text = text.upper()
    for marker in SYNTHETIC_MARKERS:
        if marker.upper() in upper_text:
            return True, marker
    return False, None


def generate_synthetic_renewal_receipt(
    fdr: FDRRecord,
    new_maturity_date: Optional[date] = None,
    proposed_amount: Optional[Decimal] = None,
    new_fdr_number: Optional[str] = None,
) -> bytes:
    """
    Generate a downloadable synthetic PDF renewal receipt for demonstration & testing.

    The PDF adheres strictly to compliance guidelines:
    - Prominently marked 'SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK'.
    - Uses clearly fictional bank/reference information.
    - Captures institution name and FDR identifier from the demo record.
    - Sets principal amount and proposed new maturity date consistent with the record.
    - Disclaims all legal/official banking validity.
    - Simple geometric layout; never imitates official bank seals, stamps, or signatures.
    """
    # Calculate proposed maturity date if not specified (default: 3-year extension from current maturity)
    if not new_maturity_date:
        base_date = fdr.maturity_date if fdr.maturity_date else date.today()
        # Add approximately 3 years
        try:
            new_maturity_date = base_date.replace(year=base_date.year + 3)
        except ValueError:
            # Leap day fallback
            new_maturity_date = base_date + timedelta(days=365 * 3)

    amt = proposed_amount if proposed_amount is not None else (fdr.amount or Decimal("0.00"))
    renewed_num = new_fdr_number or f"{fdr.fdr_number}-REN2026"
    inst_name = fdr.institution.name if fdr.institution else "Demo Educational Institution"
    inst_code = fdr.institution.institution_code if fdr.institution else "AICTE-DEMO-INST"

    doc = pymupdf.open()
    # A4 standard dimensions: 595.28 x 841.89 points
    page = doc.new_page(width=595, height=842)

    # Color definitions (RGB in 0.0 - 1.0)
    C_RED = (0.78, 0.12, 0.12)
    C_BG_RED = (0.99, 0.94, 0.94)
    C_DARK = (0.12, 0.16, 0.22)
    C_MUTED = (0.35, 0.40, 0.48)
    C_BORDER = (0.78, 0.82, 0.88)
    C_BG_BOX = (0.97, 0.98, 0.99)
    C_AMBER = (0.75, 0.45, 0.05)
    C_BG_AMBER = (1.0, 0.98, 0.92)

    # 1. Top Primary Warning Banner (Mandatory Synthetic Notice)
    banner_rect = pymupdf.Rect(36, 36, 559, 105)
    page.draw_rect(banner_rect, color=C_RED, fill=C_BG_RED, width=1.5)
    page.insert_text(
        (48, 62),
        "SYNTHETIC DEMO DOCUMENT - NOT ISSUED BY A BANK",
        fontsize=13,
        fontname="helv",
        color=C_RED,
    )
    page.insert_text(
        (48, 80),
        "LOCAL ENVIRONMENT TEST ARTIFACT - FOR SOFTWARE TESTING & VERIFICATION FLOW ONLY",
        fontsize=8.5,
        fontname="helv",
        color=C_RED,
    )
    page.insert_text(
        (48, 95),
        "ALL DATA IS FICTIONAL - REQUIRES FORMAL ENDORSEMENT BY AUTHORIZED AICTE SCRUTINY OFFICER",
        fontsize=8,
        fontname="helv",
        color=C_RED,
    )

    # 2. Watermark / Secondary Demarcation Bar
    wm_rect = pymupdf.Rect(36, 115, 559, 142)
    page.draw_rect(wm_rect, color=C_BORDER, fill=C_BG_BOX, width=1)
    page.insert_text(
        (48, 132),
        "DEMO WATERMARK: SYNTHETIC DEMO DOCUMENT - NOT ISSUED BY A BANK",
        fontsize=9,
        fontname="helv",
        color=C_MUTED,
    )

    # 3. Fictional Bank Information Box (Clearly non-existent test bank)
    bank_rect = pymupdf.Rect(36, 152, 559, 235)
    page.draw_rect(bank_rect, color=C_BORDER, fill=(1, 1, 1), width=1)
    page.insert_text(
        (48, 172),
        "FICTIONAL ISSUING BANK INFORMATION (SIMULATED TEST ENTITY)",
        fontsize=9.5,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 192),
        "Bank Name: Fictional Sandbox Test Bank Ltd. (DEMO / SIMULATION ONLY)",
        fontsize=9,
        fontname="helv",
        color=C_MUTED,
    )
    page.insert_text(
        (48, 208),
        "Branch: Prototype Virtual Branch #000, Local Development Sandbox",
        fontsize=9,
        fontname="helv",
        color=C_MUTED,
    )
    page.insert_text(
        (48, 224),
        "Fictional Reference: SIM-CBS-REN-TEST-89102 (Generated for REQ workflow test)",
        fontsize=9,
        fontname="helv",
        color=C_MUTED,
    )

    # 4. Deposit Record Parameters (Derived from actual demo record)
    data_rect = pymupdf.Rect(36, 245, 559, 395)
    page.draw_rect(data_rect, color=C_BORDER, fill=(1, 1, 1), width=1)
    page.insert_text(
        (48, 265),
        "DEPOSIT RECORD PARAMETERS (DERIVED FROM LOCAL DEMO RECORD)",
        fontsize=9.5,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 285),
        f"Institution: {inst_name} ({inst_code})",
        fontsize=9,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 302),
        f"Original FDR Number: {fdr.fdr_number}",
        fontsize=9,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 319),
        f"Proposed Renewed FDR Number: {renewed_num}",
        fontsize=9,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 336),
        f"Deposit Principal Amount: INR {amt:,.2f}",
        fontsize=9,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 353),
        f"Original Deposit Maturity Date: {fdr.maturity_date.isoformat() if fdr.maturity_date else 'N/A'}",
        fontsize=9,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 370),
        f"Proposed Extended Maturity Date: {new_maturity_date.isoformat()} (3-Year Proposed Extension)",
        fontsize=9,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 387),
        "Joint Lien Endorsement: In favour of Member Secretary, AICTE (SIMULATED)",
        fontsize=9,
        fontname="helv",
        color=C_MUTED,
    )

    # 5. Mandatory Verification Requirement & Disclaimer Callout
    callout_rect = pymupdf.Rect(36, 405, 559, 535)
    page.draw_rect(callout_rect, color=C_AMBER, fill=C_BG_AMBER, width=1)
    page.insert_text(
        (48, 425),
        "MANDATORY SCRUTINY & VERIFICATION NOTICE:",
        fontsize=9,
        fontname="helv",
        color=C_AMBER,
    )
    page.insert_text(
        (48, 443),
        "1. This document is a synthetic test receipt created solely for demonstrating the renewal workflow.",
        fontsize=8,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 458),
        "2. It does NOT constitute bank confirmation, legal tender, or an official certificate of deposit.",
        fontsize=8,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 473),
        "3. Uploading this synthetic receipt does NOT automatically verify or extend the official FDR maturity date.",
        fontsize=8,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 488),
        "4. An authorized AICTE scrutiny officer must review the document and complete the verification workflow.",
        fontsize=8,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 503),
        "5. In production environments, synthetic demonstration receipts are strictly rejected.",
        fontsize=8,
        fontname="helv",
        color=C_DARK,
    )
    page.insert_text(
        (48, 518),
        "6. In local demo mode, officers may use the simulated verification path to complete this test flow.",
        fontsize=8,
        fontname="helv",
        color=C_DARK,
    )

    # 6. Geometric Demo Footer (NO fake signature, NO bank stamp, NO counterfeit styling)
    footer_rect = pymupdf.Rect(36, 755, 559, 795)
    page.draw_rect(footer_rect, color=C_BORDER, fill=C_BG_BOX, width=1)
    page.insert_text(
        (48, 772),
        "AICTE SECURITY DEPOSIT PORTAL • LOCAL DEMO HARNESS • SYNTHETIC RECEIPT GENERATOR",
        fontsize=8,
        fontname="helv",
        color=C_MUTED,
    )
    page.insert_text(
        (48, 785),
        "SECURITY NOTICE: PROTOTYPE TEST ARTIFACT — DO NOT USE FOR FINANCIAL OR LEGAL PURPOSES",
        fontsize=7.5,
        fontname="helv",
        color=C_RED,
    )

    return doc.tobytes()

