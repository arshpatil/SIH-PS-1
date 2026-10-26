from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import shutil

import pymupdf
from PIL import Image
import pytesseract

from app.models.fdr import FDRRecord


KNOWN_BANKS = [
    "State Bank of India",
    "Punjab National Bank",
    "HDFC Bank",
    "ICICI Bank",
    "Axis Bank",
    "Bank of Baroda",
    "Canara Bank",
    "Union Bank of India",
    "Bank of India",
    "Indian Bank",
    "Central Bank of India",
    "Kotak Mahindra Bank",
    "IndusInd Bank",
    "Federal Bank",
    "IDBI Bank",
    "Yes Bank",
]


def check_tesseract_available(tesseract_cmd: str | None = None) -> bool:
    """Check whether Tesseract OCR binary is installed and reachable."""
    cmd = tesseract_cmd or os.getenv("TESSERACT_CMD", "tesseract")
    if shutil.which(cmd):
        return True
    if os.path.exists(cmd):
        return True
    # Common Windows default installation paths
    windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for p in windows_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def extract_text_from_pdf(file_path: Path | str, max_pages: int = 20) -> tuple[str, bool, str | None]:
    """Extract text from PDF using PyMuPDF, falling back to Tesseract OCR for scanned pages."""
    text_content = []
    doc = None
    try:
        doc = pymupdf.open(str(file_path))
        if doc.is_encrypted:
            return "", False, "PDF is password-encrypted and cannot be processed."

        total_pages = min(len(doc), max_pages)
        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_text = page.get_text()
            text_content.append(page_text)

        extracted = "\n".join(text_content).strip()

        # If extractable digital text is sufficient, return it
        if len(extracted) >= 30:
            return extracted, True, None

        # Digital text is minimal; attempt OCR if Tesseract is available
        if not check_tesseract_available():
            return (
                extracted,
                False,
                "Scanned PDF with minimal digital text. Tesseract OCR is not installed or available on PATH.",
            )

        ocr_pages = []
        for page_idx in range(total_pages):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img)
            ocr_pages.append(ocr_text)

        full_ocr = "\n".join(ocr_pages).strip()
        return full_ocr, True, None

    except Exception as exc:
        return "", False, f"Failed to parse PDF document: {str(exc)}"
    finally:
        if doc:
            doc.close()


def extract_text_from_image(file_path: Path | str) -> tuple[str, bool, str | None]:
    """Extract text from an image file using Tesseract OCR."""
    if not check_tesseract_available():
        return (
            "",
            False,
            "Tesseract OCR is not installed or not found on system PATH. Install Tesseract to enable image OCR.",
        )

    try:
        with Image.open(str(file_path)) as img:
            text = pytesseract.image_to_string(img)
            return text.strip(), True, None
    except Exception as exc:
        return "", False, f"Failed to perform OCR on image: {str(exc)}"


def extract_text_from_document(
    file_path: Path | str, file_type: str, max_pages: int = 20
) -> tuple[str, str, str | None]:
    """Extract text based on MIME type and return (text, status, note)."""
    clean_type = file_type.lower()
    if clean_type == "application/pdf":
        text, success, note = extract_text_from_pdf(file_path, max_pages)
    elif clean_type in ("image/png", "image/jpeg", "image/jpg"):
        text, success, note = extract_text_from_image(file_path)
    else:
        return "", "FAILED", f"Unsupported file MIME type '{file_type}'."

    if success:
        return text, "PROCESSED", note
    return text, "FAILED", note


def parse_date_heuristic(raw: str) -> date | None:
    """Parse flexible date strings (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, etc.) into date object."""
    if not raw:
        return None
    cleaned = raw.strip()
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %b %Y",
        "%d %B %Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def extract_fdr_fields(text: str) -> dict:
    """Extract FDR fields from text using pattern matching heuristics."""
    extracted = {
        "fdr_number": None,
        "bank_name": None,
        "branch_name": None,
        "amount": None,
        "issue_date": None,
        "maturity_date": None,
    }

    if not text:
        return extracted

    # 1. FDR Number heuristics
    num_patterns = [
        r"\b(?:FDR|F\.D\.R\.?)\s*(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Za-z0-9\/-]{4,30})",
        r"(?:Fixed\s*Deposit|Deposit\s*Receipt|Deposit|Account)\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Za-z0-9\/-]{4,30})",
        r"\b(?:FDR|FD)-[A-Za-z0-9\/-]{4,25}\b",
    ]
    disallowed_fdr_words = {
        "receipt",
        "certificate",
        "account",
        "scheme",
        "deposit",
        "fixed",
        "general",
        "branch",
    }
    for pat in num_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            cand = (
                match.group(1).strip()
                if match.groups()
                else match.group(0).strip()
            )
            if cand.lower() not in disallowed_fdr_words and len(cand) >= 4:
                extracted["fdr_number"] = cand
                break

    # 2. Bank Name heuristics
    for bank in KNOWN_BANKS:
        if re.search(r"\b" + re.escape(bank) + r"\b", text, re.IGNORECASE):
            extracted["bank_name"] = bank
            break
    if not extracted["bank_name"]:
        match_bank = re.search(
            r"\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\s+Bank(?:\s+of\s+[A-Z][a-zA-Z]+)?)\b",
            text,
        )
        if match_bank:
            cleaned_b = match_bank.group(1).strip()
            if len(cleaned_b) <= 50 and not re.search(
                r"\b(?:thank|welcome|banking)\b", cleaned_b, re.IGNORECASE
            ):
                extracted["bank_name"] = cleaned_b

    # 3. Branch Name heuristics
    branch_match = re.search(
        r"Branch(?:\s*Name)?\s*[:\-\s]\s*([A-Za-z0-9\s,.-]{3,40})", text, re.IGNORECASE
    )
    if branch_match:
        # Strip trailing newline or extra symbols
        cand = branch_match.group(1).split("\n")[0].strip()
        extracted["branch_name"] = cand

    # 4. Amount heuristics
    amt_patterns = [
        r"(?:Rs\.?|INR|Amount|Principal|Deposit\s*Amount)\s*[:\-\s]*(?:Rs\.?|INR)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{2})?)",
        r"\b([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{2})?)\b",
    ]
    for pat in amt_patterns:
        match_amt = re.search(pat, text, re.IGNORECASE)
        if match_amt:
            clean_amt = match_amt.group(1).replace(",", "").strip()
            try:
                dec = Decimal(clean_amt)
                if dec > Decimal("0"):
                    extracted["amount"] = f"{dec:.2f}"
                    break
            except (InvalidOperation, ValueError):
                pass

    # 5. Issue Date heuristics
    issue_match = re.search(
        r"(?:Issue\s*Date|Date\s*of\s*Issue|Deposit\s*Date|Effective\s*Date|Value\s*Date)\s*[:\-\s]\s*([0-9A-Za-z\s\/-]{6,20})",
        text,
        re.IGNORECASE,
    )
    if issue_match:
        cand_d = issue_match.group(1).split("\n")[0].strip()
        parsed_d = parse_date_heuristic(cand_d)
        if parsed_d:
            extracted["issue_date"] = parsed_d.isoformat()

    # 6. Maturity Date heuristics
    mat_match = re.search(
        r"(?:Maturity\s*Date|Date\s*of\s*Maturity|Due\s*Date)\s*[:\-\s]\s*([0-9A-Za-z\s\/-]{6,20})",
        text,
        re.IGNORECASE,
    )
    if mat_match:
        cand_m = mat_match.group(1).split("\n")[0].strip()
        parsed_m = parse_date_heuristic(cand_m)
        if parsed_m:
            extracted["maturity_date"] = parsed_m.isoformat()

    return extracted


def normalize_text(text: str | None) -> str:
    """Normalize text for discrepancy comparison (alphanumeric, lowercase)."""
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def detect_fdr_discrepancies(extracted: dict, fdr: FDRRecord) -> dict:
    """Compare extracted OCR fields with the registered FDRRecord and generate discrepancy report."""
    matched = []
    mismatched = []
    missing = []

    # 1. FDR Number comparison
    reg_num = fdr.fdr_number
    ext_num = extracted.get("fdr_number")
    if not ext_num:
        missing.append("fdr_number")
    else:
        if normalize_text(reg_num) == normalize_text(ext_num):
            matched.append(
                {"field": "fdr_number", "registered": reg_num, "extracted": ext_num}
            )
        else:
            mismatched.append(
                {
                    "field": "fdr_number",
                    "registered": reg_num,
                    "extracted": ext_num,
                    "discrepancy": f"FDR number mismatch: registered '{reg_num}' vs extracted '{ext_num}'",
                }
            )

    # 2. Bank Name comparison
    reg_bank = fdr.bank_name
    ext_bank = extracted.get("bank_name")
    if not ext_bank:
        missing.append("bank_name")
    else:
        norm_reg = normalize_text(reg_bank)
        norm_ext = normalize_text(ext_bank)
        if norm_reg == norm_ext or norm_reg in norm_ext or norm_ext in norm_reg:
            matched.append(
                {"field": "bank_name", "registered": reg_bank, "extracted": ext_bank}
            )
        else:
            mismatched.append(
                {
                    "field": "bank_name",
                    "registered": reg_bank,
                    "extracted": ext_bank,
                    "discrepancy": f"Bank name mismatch: registered '{reg_bank}' vs extracted '{ext_bank}'",
                }
            )

    # 3. Branch Name comparison
    reg_branch = fdr.branch_name
    ext_branch = extracted.get("branch_name")
    if not ext_branch:
        missing.append("branch_name")
    else:
        norm_b_reg = normalize_text(reg_branch)
        norm_b_ext = normalize_text(ext_branch)
        if norm_b_reg == norm_b_ext or norm_b_reg in norm_b_ext or norm_b_ext in norm_b_reg:
            matched.append(
                {"field": "branch_name", "registered": reg_branch, "extracted": ext_branch}
            )
        else:
            mismatched.append(
                {
                    "field": "branch_name",
                    "registered": reg_branch,
                    "extracted": ext_branch,
                    "discrepancy": f"Branch mismatch: registered '{reg_branch}' vs extracted '{ext_branch}'",
                }
            )

    # 4. Amount comparison (Numeric / Decimal comparison)
    reg_amt = fdr.amount
    ext_amt_str = extracted.get("amount")
    if not ext_amt_str:
        missing.append("amount")
    else:
        try:
            ext_amt_dec = Decimal(ext_amt_str).quantize(Decimal("0.01"))
            reg_amt_dec = Decimal(str(reg_amt)).quantize(Decimal("0.01"))
            if ext_amt_dec == reg_amt_dec:
                matched.append(
                    {
                        "field": "amount",
                        "registered": f"{reg_amt_dec:.2f}",
                        "extracted": f"{ext_amt_dec:.2f}",
                    }
                )
            else:
                mismatched.append(
                    {
                        "field": "amount",
                        "registered": f"{reg_amt_dec:.2f}",
                        "extracted": f"{ext_amt_dec:.2f}",
                        "discrepancy": f"Amount mismatch: registered INR {reg_amt_dec:.2f} vs extracted INR {ext_amt_dec:.2f}",
                    }
                )
        except (InvalidOperation, ValueError):
            missing.append("amount")

    # 5. Issue Date comparison
    reg_issue = fdr.issue_date.isoformat() if fdr.issue_date else None
    ext_issue = extracted.get("issue_date")
    if not ext_issue:
        missing.append("issue_date")
    else:
        if reg_issue == ext_issue:
            matched.append(
                {"field": "issue_date", "registered": reg_issue, "extracted": ext_issue}
            )
        else:
            mismatched.append(
                {
                    "field": "issue_date",
                    "registered": reg_issue,
                    "extracted": ext_issue,
                    "discrepancy": f"Issue date mismatch: registered {reg_issue} vs extracted {ext_issue}",
                }
            )

    # 6. Maturity Date comparison
    reg_mat = fdr.maturity_date.isoformat() if fdr.maturity_date else None
    ext_mat = extracted.get("maturity_date")
    if not ext_mat:
        missing.append("maturity_date")
    else:
        if reg_mat == ext_mat:
            matched.append(
                {"field": "maturity_date", "registered": reg_mat, "extracted": ext_mat}
            )
        else:
            mismatched.append(
                {
                    "field": "maturity_date",
                    "registered": reg_mat,
                    "extracted": ext_mat,
                    "discrepancy": f"Maturity date mismatch: registered {reg_mat} vs extracted {ext_mat}",
                }
            )

    # Compute overall outcome
    if mismatched:
        overall_result = "DISCREPANCY_FOUND"
    elif not missing and len(matched) >= 4:
        overall_result = "MATCH"
    else:
        overall_result = "MANUAL_REVIEW_REQUIRED"

    return {
        "overall_result": overall_result,
        "matched_fields": matched,
        "mismatched_fields": mismatched,
        "missing_fields": missing,
        "extracted_fields": extracted,
        "disclaimer": "Automated OCR extraction and heuristic check only. Does not replace formal AICTE officer scrutiny or bank confirmation.",
    }
