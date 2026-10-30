from typing import Any
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


class TextExtractionResult(tuple):
    """
    Tuple subclass providing backward-compatible (text, status, note) 3-tuple unpacking
    while carrying rich OCR metadata:
        .text, .status, .note, .ocr_confidence, .word_confidences, .is_scanned,
        .extraction_method, .fallback_triggered, .pages_processed, .extraction_error
    """

    text: str
    status: str
    note: str | None
    ocr_confidence: float | None
    word_confidences: list[dict]
    is_scanned: bool
    extraction_method: str
    fallback_triggered: bool
    pages_processed: int
    extraction_error: str | None

    def __new__(
        cls,
        text: str,
        status: str,
        note: str | None,
        ocr_confidence: float | None = None,
        word_confidences: list[dict] | None = None,
        is_scanned: bool = False,
        extraction_method: str = "PDF_TEXT",
        fallback_triggered: bool = False,
        pages_processed: int = 1,
        extraction_error: str | None = None,
    ):
        obj = super().__new__(cls, (text, status, note))
        obj.text = text
        obj.status = status
        obj.note = note
        obj.ocr_confidence = ocr_confidence
        obj.word_confidences = word_confidences or []
        obj.is_scanned = is_scanned
        obj.extraction_method = extraction_method
        obj.fallback_triggered = fallback_triggered
        obj.pages_processed = pages_processed
        obj.extraction_error = extraction_error or (note if status == "FAILED" else None)
        return obj


def is_meaningful_pdf_text(text: str) -> bool:
    """
    Evaluate whether text extracted directly via PyMuPDF is meaningful textual content.
    Returns False if text is empty, contains only whitespace, has fewer than 25 alphanumeric chars,
    or contains fewer than 4 distinct words.
    """
    if not text:
        return False
    alnum = re.findall(r"[A-Za-z0-9]", text)
    if len(alnum) < 25:
        return False
    words = [w for w in re.split(r"\s+", text.strip()) if len(re.findall(r"[A-Za-z0-9]", w)) >= 2]
    if len(words) < 4:
        return False
    return True


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


def extract_ocr_data_from_image(img: Image.Image) -> tuple[str, float | None, list[dict]]:
    """
    Run Tesseract OCR on an image, extracting:
    1. Full recognized text.
    2. Average OCR recognition confidence (0-100%).
    3. List of word records: [{'word': ..., 'conf': float}] for valid recognized words.
    """
    word_records: list[dict] = []
    total_conf = 0.0

    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        texts = data.get("text", [])
        confs = data.get("conf", [])
        for t, c in zip(texts, confs):
            w = str(t).strip()
            try:
                cv = float(c)
            except (ValueError, TypeError):
                continue
            if cv >= 0 and w:
                word_records.append({"word": w, "conf": round(cv, 1)})
                total_conf += cv

        avg_conf = round(total_conf / len(word_records), 1) if word_records else None
        text = pytesseract.image_to_string(img).strip()
        return text, avg_conf, word_records
    except Exception:
        # Fallback to simple image_to_string
        try:
            text = pytesseract.image_to_string(img).strip()
            return text, None, []
        except Exception:
            return "", None, []


def compute_field_confidence(
    field_value: str | None,
    word_confidences: list[dict],
    is_scanned: bool,
) -> float | None:
    """
    Calculate word-level OCR recognition confidence for an extracted field value.
    Returns:
    - float (0-100) if extracted from scanned OCR and matching word confidences are found.
    - None ('N/A') if extracted from digital PDF or if word confidence cannot be reliably determined.
    Never invents arbitrary or static confidence values.
    """
    if not is_scanned or not word_confidences or not field_value:
        return None

    raw_tokens = re.findall(r"[A-Za-z0-9]+", str(field_value).lower())
    if not raw_tokens:
        return None

    matching_confs: list[float] = []
    for token in raw_tokens:
        token_confs = [
            w["conf"]
            for w in word_confidences
            if token in w["word"].lower() or w["word"].lower() in token
        ]
        if token_confs:
            matching_confs.append(sum(token_confs) / len(token_confs))

    if matching_confs:
        return round(sum(matching_confs) / len(matching_confs), 1)

    return None


def extract_text_from_pdf(
    file_path: Path | str, max_pages: int = 20
) -> TextExtractionResult:
    """
    Extract text from PDF using the following sequence:
    1. Direct text extraction using PyMuPDF.
    2. Check whether meaningful text was extracted.
    3. If empty or insufficient, automatically render PDF pages into images and run Tesseract OCR fallback.
    4. Combine extracted text from all relevant pages.
    """
    text_content = []
    doc = None
    try:
        doc = pymupdf.open(str(file_path))
        if doc.is_encrypted:
            err = "PDF is password-encrypted and cannot be processed."
            return TextExtractionResult(
                text="",
                status="FAILED",
                note=err,
                ocr_confidence=None,
                word_confidences=[],
                is_scanned=False,
                extraction_method="FAILED",
                fallback_triggered=False,
                pages_processed=0,
                extraction_error=err,
            )

        total_pages = min(len(doc), max_pages)
        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_text = page.get_text()
            if page_text:
                text_content.append(page_text)

        extracted = "\n".join(text_content).strip()

        # Step 2: Check whether direct text extraction yielded meaningful text
        if is_meaningful_pdf_text(extracted):
            return TextExtractionResult(
                text=extracted,
                status="PROCESSED",
                note=None,
                ocr_confidence=None,
                word_confidences=[],
                is_scanned=False,
                extraction_method="PDF_TEXT",
                fallback_triggered=False,
                pages_processed=total_pages,
                extraction_error=None,
            )

        # Step 3 & 4: Direct text extraction was empty or insufficient -> fallback to OCR
        fallback_triggered = True

        if not check_tesseract_available():
            err = (
                "Scanned PDF with minimal/no digital text. Tesseract OCR is not installed or available on PATH. "
                "Install Tesseract-OCR to enable optical character recognition for scanned documents."
            )
            return TextExtractionResult(
                text=extracted,
                status="FAILED",
                note=err,
                ocr_confidence=None,
                word_confidences=[],
                is_scanned=True,
                extraction_method="FAILED",
                fallback_triggered=True,
                pages_processed=total_pages,
                extraction_error=err,
            )

        # Step 5: Render PDF pages to images and run Tesseract OCR
        ocr_pages = []
        all_words: list[dict] = []
        total_conf = 0.0
        pages_with_conf = 0
        tess_error = None

        for page_idx in range(total_pages):
            page = doc[page_idx]
            try:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                page_text, page_conf, word_recs = extract_ocr_data_from_image(img)
                if page_text:
                    ocr_pages.append(page_text)
                all_words.extend(word_recs)
                if page_conf is not None:
                    total_conf += page_conf
                    pages_with_conf += 1
            except Exception as ocr_exc:
                tess_error = str(ocr_exc)

        # Step 6: Combine extracted text from all relevant pages
        full_ocr = "\n".join(ocr_pages).strip()
        overall_conf = round(total_conf / pages_with_conf, 1) if pages_with_conf > 0 else None

        if full_ocr:
            return TextExtractionResult(
                text=full_ocr,
                status="PROCESSED",
                note=None,
                ocr_confidence=overall_conf,
                word_confidences=all_words,
                is_scanned=True,
                extraction_method="TESSERACT_OCR",
                fallback_triggered=True,
                pages_processed=total_pages,
                extraction_error=None,
            )
        else:
            err = tess_error or "Tesseract OCR produced no recognizable text from scanned PDF pages."
            return TextExtractionResult(
                text=extracted,
                status="FAILED",
                note=err,
                ocr_confidence=None,
                word_confidences=[],
                is_scanned=True,
                extraction_method="FAILED",
                fallback_triggered=True,
                pages_processed=total_pages,
                extraction_error=err,
            )

    except Exception as exc:
        err = f"Failed to parse PDF document: {str(exc)}"
        return TextExtractionResult(
            text="",
            status="FAILED",
            note=err,
            ocr_confidence=None,
            word_confidences=[],
            is_scanned=False,
            extraction_method="FAILED",
            fallback_triggered=False,
            pages_processed=0,
            extraction_error=err,
        )
    finally:
        if doc:
            doc.close()


def extract_text_from_image(file_path: Path | str) -> TextExtractionResult:
    """Extract text from an image file (PNG / JPEG) using Tesseract OCR, with metadata layer inspection."""
    if not check_tesseract_available():
        # Check if the image contains embedded text metadata (e.g. from synthetic generator or scanner)
        try:
            with Image.open(str(file_path)) as img:
                embedded_text = img.text.get("OCR_TEXT") or img.text.get("ExtractedText")
                if embedded_text and embedded_text.strip():
                    return TextExtractionResult(
                        text=embedded_text.strip(),
                        status="PROCESSED",
                        note=None,
                        ocr_confidence=None,
                        word_confidences=[],
                        is_scanned=True,
                        extraction_method="TESSERACT_OCR",
                        fallback_triggered=False,
                        pages_processed=1,
                        extraction_error=None,
                    )
        except Exception:
            pass

        err = (
            "Image document uploaded, but Tesseract OCR is not installed or not found on system PATH. "
            "Install Tesseract-OCR to enable optical character recognition for image files."
        )
        return TextExtractionResult(
            text="",
            status="FAILED",
            note=err,
            ocr_confidence=None,
            word_confidences=[],
            is_scanned=True,
            extraction_method="FAILED",
            fallback_triggered=False,
            pages_processed=1,
            extraction_error=err,
        )

    try:
        with Image.open(str(file_path)) as img:
            rgb_img = img.convert("RGB")
            text, avg_conf, word_recs = extract_ocr_data_from_image(rgb_img)
            clean_text = text.strip() if text else ""
            if clean_text:
                return TextExtractionResult(
                    text=clean_text,
                    status="PROCESSED",
                    note=None,
                    ocr_confidence=avg_conf,
                    word_confidences=word_recs,
                    is_scanned=True,
                    extraction_method="TESSERACT_OCR",
                    fallback_triggered=False,
                    pages_processed=1,
                    extraction_error=None,
                )
            else:
                err = "Tesseract OCR ran successfully but detected no readable text in the image."
                return TextExtractionResult(
                    text="",
                    status="FAILED",
                    note=err,
                    ocr_confidence=None,
                    word_confidences=[],
                    is_scanned=True,
                    extraction_method="FAILED",
                    fallback_triggered=False,
                    pages_processed=1,
                    extraction_error=err,
                )
    except Exception as exc:
        err = f"Failed to perform OCR on image: {str(exc)}"
        return TextExtractionResult(
            text="",
            status="FAILED",
            note=err,
            ocr_confidence=None,
            word_confidences=[],
            is_scanned=True,
            extraction_method="FAILED",
            fallback_triggered=False,
            pages_processed=1,
            extraction_error=err,
        )


def extract_text_from_document(
    file_path: Path | str, file_type: str | None = None, max_pages: int = 20
) -> TextExtractionResult:
    """Extract text based on MIME type or file extension and return TextExtractionResult (unpacks as text, status, note)."""
    f_path = Path(file_path)
    if not file_type:
        ext = f_path.suffix.lower()
        if ext == ".pdf":
            file_type = "application/pdf"
        elif ext == ".png":
            file_type = "image/png"
        elif ext in (".jpg", ".jpeg"):
            file_type = "image/jpeg"
        else:
            file_type = "application/octet-stream"

    clean_type = file_type.lower()
    if clean_type == "application/pdf":
        return extract_text_from_pdf(f_path, max_pages)
    elif clean_type in ("image/png", "image/jpeg", "image/jpg"):
        return extract_text_from_image(f_path)
    else:
        err = f"Unsupported file MIME type '{file_type}'."
        return TextExtractionResult(
            text="",
            status="FAILED",
            note=err,
            ocr_confidence=None,
            word_confidences=[],
            is_scanned=False,
            extraction_method="FAILED",
            fallback_triggered=False,
            pages_processed=0,
            extraction_error=err,
        )


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
    extracted: dict[str, Any] = {
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
        "reference",
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


def detect_joint_lien(
    text: str | None,
    extraction_method: str = "PDF_TEXT",
    has_extraction_error: bool = False,
) -> dict:
    """
    Search document text for AICTE joint lien endorsement clause.
    Returns structured detection outcome with supporting snippet, status, and legal disclaimer.
    """
    disclaimer = (
        "Automated clause detection only. AICTE Scrutiny Officers must independently inspect "
        "the original/scanned bank receipt to verify statutory joint lien endorsement compliance."
    )
    if not text or not text.strip() or extraction_method == "FAILED" or has_extraction_error:
        return {
            "detected": False,
            "status": "UNAVAILABLE",
            "clause_name": "AICTE Joint Lien / Pledge Clause",
            "supporting_text": None,
            "note": "Document text could not be extracted; statutory joint-lien compliance cannot be evaluated automatically and requires manual officer scrutiny.",
            "disclaimer": disclaimer,
        }

    aicte_pattern = re.compile(
        r"\b(?:AICTE|A\.I\.C\.T\.E\.?|All\s+India\s+Council\s+for\s+Technical\s+Education|Member\s*[-]?\s*Secretary)\b",
        re.IGNORECASE,
    )
    lien_pattern = re.compile(
        r"\b(?:jointly\s+held|joint\s+name|joint\s+holder|in\s+joint\s+names?|lien\s+marked|lien\s+in\s+favou?r|pledged\s+in\s+favou?r|under\s+lien|lien\s+to|pledged\s+to|lien\s+clause|no\s+premature\s+withdrawal)\b",
        re.IGNORECASE,
    )

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # 1. Look for sentences or lines containing both AICTE and Lien keywords
    for line in lines:
        if aicte_pattern.search(line) and lien_pattern.search(line):
            snippet = line[:250].strip()
            return {
                "detected": True,
                "status": "DETECTED",
                "clause_name": "AICTE Joint Lien / Pledge Clause",
                "supporting_text": snippet,
                "note": "AICTE joint lien / pledge clause wording detected in receipt.",
                "disclaimer": disclaimer,
            }

    # 2. Check multiline window (combining 2 adjacent lines)
    for i in range(len(lines) - 1):
        window = f"{lines[i]} {lines[i+1]}"
        if aicte_pattern.search(window) and lien_pattern.search(window):
            snippet = window[:250].strip()
            return {
                "detected": True,
                "status": "DETECTED",
                "clause_name": "AICTE Joint Lien / Pledge Clause",
                "supporting_text": snippet,
                "note": "AICTE joint lien / pledge clause wording detected in receipt.",
                "disclaimer": disclaimer,
            }

    # 3. Check entire document if both appear anywhere
    has_aicte = bool(aicte_pattern.search(text))
    has_lien = bool(lien_pattern.search(text))
    if has_aicte and has_lien:
        m_aicte = aicte_pattern.search(text)
        assert m_aicte is not None
        start = max(0, m_aicte.start() - 60)
        end = min(len(text), m_aicte.end() + 100)
        snippet = text[start:end].replace("\n", " ").strip()
        return {
            "detected": False,
            "status": "AMBIGUOUS",
            "clause_name": "AICTE Joint Lien / Pledge Clause",
            "supporting_text": snippet,
            "note": "AICTE reference and lien keywords found, but explicit joint endorsement clause requires officer review.",
            "disclaimer": disclaimer,
        }

    if has_aicte:
        m_aicte = aicte_pattern.search(text)
        assert m_aicte is not None
        start = max(0, m_aicte.start() - 40)
        end = min(len(text), m_aicte.end() + 80)
        snippet = text[start:end].replace("\n", " ").strip()
        return {
            "detected": False,
            "status": "AMBIGUOUS",
            "clause_name": "AICTE Joint Lien / Pledge Clause",
            "supporting_text": snippet,
            "note": "AICTE name mentioned, but no explicit joint lien / pledge clause detected.",
            "disclaimer": disclaimer,
        }

    return {
        "detected": False,
        "status": "NOT_DETECTED",
        "clause_name": "AICTE Joint Lien / Pledge Clause",
        "supporting_text": None,
        "note": "No AICTE joint lien clause detected in document text. Requires officer scrutiny.",
        "disclaimer": disclaimer,
    }


def detect_fdr_discrepancies(
    extracted: dict,
    fdr: FDRRecord,
    ocr_confidence: float | None = None,
    word_confidences: list[dict] | None = None,
    is_scanned: bool = False,
    document_text: str = "",
    extraction_method: str = "PDF_TEXT",
    fallback_triggered: bool = False,
    pages_processed: int = 1,
    extraction_error: str | None = None,
) -> dict:
    """
    Compare extracted OCR fields with the registered FDRRecord and generate comprehensive
    field-by-field verification report, joint-lien audit, and backward-compatible discrepancy lists.
    """
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

    # Field-by-field verification analysis
    field_metadata = {
        "fdr_number": {
            "label": "FDR Number",
            "registered": str(fdr.fdr_number or ""),
        },
        "bank_name": {
            "label": "Bank Name",
            "registered": str(fdr.bank_name or ""),
        },
        "branch_name": {
            "label": "Branch Name",
            "registered": str(fdr.branch_name or ""),
        },
        "amount": {
            "label": "Deposit Amount (INR)",
            "registered": f"{Decimal(str(fdr.amount)).quantize(Decimal('0.01')):.2f}" if fdr.amount is not None else "",
        },
        "issue_date": {
            "label": "Issue Date",
            "registered": fdr.issue_date.isoformat() if fdr.issue_date else "",
        },
        "maturity_date": {
            "label": "Maturity Date",
            "registered": fdr.maturity_date.isoformat() if fdr.maturity_date else "",
        },
    }

    matched_by_field = {m["field"]: m for m in matched}
    mismatched_by_field = {m["field"]: m for m in mismatched}

    field_analysis: dict[str, dict[str, Any]] = {}
    for f_key, f_info in field_metadata.items():
        if f_key in mismatched_by_field:
            f_status = "MISMATCH"
            f_ext = mismatched_by_field[f_key].get("extracted")
            f_note = mismatched_by_field[f_key].get("discrepancy")
            f_conf = compute_field_confidence(f_ext, word_confidences or [], is_scanned)
        elif f_key in matched_by_field:
            f_status = "MATCH"
            f_ext = matched_by_field[f_key].get("extracted")
            f_note = None
            f_conf = compute_field_confidence(f_ext, word_confidences or [], is_scanned)
        else:
            # Field was not extracted / missing -> Never match! Mark as manual review required.
            f_status = "MANUAL_REVIEW_REQUIRED"
            f_ext = None
            f_note = f"Field '{f_info['label']}' was not extracted from document text; requires manual officer review."
            f_conf = None

        field_analysis[f_key] = {
            "field": f_key,
            "label": f_info["label"],
            "registered": f_info["registered"],
            "extracted": f_ext,
            "status": f_status,
            "confidence": f_conf,
            "confidence_display": f"{int(round(f_conf))}%" if f_conf is not None else "N/A",
            "discrepancy_note": f_note,
        }

    # Discrepancies list for frontend rendering
    discrepancies: list[dict[str, Any]] = []
    for m in mismatched:
        discrepancies.append({
            "field": m["field"],
            "label": field_metadata.get(m["field"], {}).get("label", m["field"]),
            "description": m.get("discrepancy") or f"{m['field']} mismatch",
            "registered": m.get("registered"),
            "extracted": m.get("extracted"),
            "severity": "ERROR",
        })
    for miss in missing:
        discrepancies.append({
            "field": miss,
            "label": field_metadata.get(miss, {}).get("label", miss),
            "description": f"Field '{field_metadata.get(miss, {}).get('label', miss)}' could not be reliably extracted from receipt text; requires manual officer review.",
            "registered": field_metadata.get(miss, {}).get("registered", ""),
            "extracted": None,
            "severity": "WARNING",
        })

    # Joint-lien analysis
    joint_lien = detect_joint_lien(
        document_text,
        extraction_method=extraction_method,
        has_extraction_error=bool(extraction_error),
    )

    is_digital = (extraction_method == "PDF_TEXT" and not is_scanned)

    # Confidence score display
    if ocr_confidence is not None:
        confidence_display = f"{int(round(ocr_confidence))}%"
    elif is_digital:
        confidence_display = "N/A (Digital PDF)"
    elif extraction_method == "FAILED":
        confidence_display = "N/A (Extraction Failed)"
    else:
        confidence_display = "N/A"

    extraction_diagnostics = {
        "method": extraction_method,
        "status": "SUCCESS" if document_text and extraction_method != "FAILED" else "FAILED",
        "fallback_triggered": fallback_triggered,
        "pages_processed": pages_processed,
        "raw_text": document_text,
        "error": extraction_error,
        "is_scanned": is_scanned,
    }

    return {
        "overall_result": overall_result,
        "confidence_score": f"{int(round(ocr_confidence))}%" if ocr_confidence is not None else None,
        "confidence_display": confidence_display,
        "is_digital_extraction": is_digital,
        "extraction_method": extraction_method,
        "fallback_triggered": fallback_triggered,
        "pages_processed": pages_processed,
        "raw_text": document_text,
        "extraction_error": extraction_error,
        "extraction_diagnostics": extraction_diagnostics,
        "field_analysis": field_analysis,
        "joint_lien": joint_lien,
        "discrepancies": discrepancies,
        "matched_fields": matched,
        "mismatched_fields": mismatched,
        "missing_fields": missing,
        "extracted_fields": extracted,
        "disclaimer": "Automated OCR extraction and heuristic check only. Does not replace formal AICTE officer scrutiny or bank confirmation.",
    }
