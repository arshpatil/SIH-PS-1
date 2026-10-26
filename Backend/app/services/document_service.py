import json
import os
from pathlib import Path
import re
import secrets
from typing import Any
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.config import Config
from app.extensions import db
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.enums import DocumentProcessingStatus, UserRole
from app.models.fdr import FDRRecord
from app.models.user import User
from app.services.fdr_service import FDRNotFoundError, FDRPermissionError, FDRValidationError
from app.services.ocr_service import detect_fdr_discrepancies, extract_fdr_fields, extract_text_from_document


ALLOWED_EXTENSIONS = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}


def sanitize_filename(filename: str | None) -> str:
    """Sanitize client-provided original filename."""
    if not filename:
        return "unnamed_document"
    # Extract basename only to prevent path traversal in original_filename string
    base = os.path.basename(filename.replace("\\", "/"))
    clean = secure_filename(base)
    return clean if clean else "sanitized_document"


def validate_uploaded_file(file: FileStorage, max_bytes: int = 10 * 1024 * 1024) -> tuple[str, str, bytes]:
    """Validate file presence, extension, actual file size, and magic bytes signature."""
    if not file or not file.filename:
        raise FDRValidationError({"file": "No file was selected or uploaded."})

    sanitized_name = sanitize_filename(file.filename)
    ext = Path(sanitized_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        allowed_list = sorted(list(ALLOWED_EXTENSIONS.keys()))
        raise FDRValidationError(
            {
                "file": f"Unsupported file extension '{ext}'. Allowed extensions: {allowed_list}."
            }
        )

    expected_mime, magic_bytes = ALLOWED_EXTENSIONS[ext]

    # Read content into memory to check size and magic bytes
    content = file.read()
    file_size = len(content)

    if file_size == 0:
        raise FDRValidationError({"file": "Uploaded file is empty (0 bytes)."})

    if file_size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise FDRValidationError(
            {
                "file": f"File size exceeds maximum permitted limit of {max_mb} MB ({file_size} bytes)."
            }
        )

    # Magic byte signature validation
    if not content.startswith(magic_bytes):
        raise FDRValidationError(
            {
                "file": f"File content does not match expected signature for extension '{ext}'."
            }
        )

    return sanitized_name, expected_mime, content


def get_analysis_file_path(upload_dir: Path, stored_filename: str) -> Path:
    """Return path for the companion analysis JSON file."""
    return upload_dir / f"{stored_filename}.analysis.json"


def save_analysis_result(upload_dir: Path, stored_filename: str, result: dict) -> None:
    """Persist structured discrepancy analysis result alongside the stored document."""
    analysis_path = get_analysis_file_path(upload_dir, stored_filename)
    try:
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
    except OSError:
        pass


def load_analysis_result(upload_dir: Path, stored_filename: str) -> dict | None:
    """Load persistent structured analysis report if available."""
    analysis_path = get_analysis_file_path(upload_dir, stored_filename)
    if not analysis_path.exists():
        return None
    try:
        with open(analysis_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def get_authorized_fdr_for_upload(fdr_id: int, current_user: User) -> FDRRecord:
    """Ensure user is authorized to attach documents to the FDR."""
    fdr = db.session.get(FDRRecord, fdr_id)
    if not fdr:
        raise FDRNotFoundError("FDR record not found.")

    user_category = UserRole.normalize_category(current_user.role)
    if user_category == "INSTITUTION":
        if fdr.institution_id != current_user.institution_id:
            # Hide record existence across institutions
            raise FDRNotFoundError("FDR record not found.")

    return fdr


def process_and_save_document(
    fdr_id: int,
    file: FileStorage,
    current_user: User,
    upload_dir: Path,
    max_bytes: int = 10 * 1024 * 1024,
    max_pdf_pages: int = 20,
) -> tuple[Document, dict]:
    """Validate, persist file, run OCR, run discrepancy detection, and persist metadata."""
    fdr = get_authorized_fdr_for_upload(fdr_id, current_user)

    # Validate file and obtain bytes
    original_name, mime_type, content = validate_uploaded_file(file, max_bytes)

    # Ensure upload directory exists
    os.makedirs(upload_dir, exist_ok=True)

    # Generate secure random stored filename
    ext = Path(original_name).suffix.lower()
    random_token = secrets.token_hex(16)
    stored_name = f"fdr_{fdr.id}_{random_token}{ext}"
    target_path = (upload_dir / stored_name).resolve()

    # Prevent path traversal
    if not str(target_path).startswith(str(upload_dir.resolve())):
        raise FDRValidationError({"file": "Invalid target storage path."})

    # Write file to disk
    with open(target_path, "wb") as f:
        f.write(content)

    doc_record = None
    try:
        # Create Document DB record
        doc_record = Document(
            fdr_id=fdr.id,
            original_filename=original_name,
            stored_filename=stored_name,
            file_type=mime_type,
            file_size=len(content),
            processing_status=DocumentProcessingStatus.PENDING.value,
            uploaded_by=current_user.id,
        )
        db.session.add(doc_record)
        db.session.flush()

        # Run text extraction & discrepancy detection
        raw_text, ocr_status, note = extract_text_from_document(
            target_path, mime_type, max_pages=max_pdf_pages
        )

        extracted_fields = extract_fdr_fields(raw_text) if raw_text else {}
        discrepancy_report = detect_fdr_discrepancies(extracted_fields, fdr)

        if note:
            discrepancy_report["processing_note"] = note

        # Update Document processing status
        doc_record.processing_status = (
            DocumentProcessingStatus.PROCESSED.value
            if ocr_status == "PROCESSED"
            else DocumentProcessingStatus.FAILED.value
        )

        # Save structured analysis companion file
        save_analysis_result(upload_dir, stored_name, discrepancy_report)

        # Record audit log
        audit = AuditLog(
            user_id=current_user.id,
            action="DOCUMENT_UPLOADED",
            entity_type="Document",
            entity_id=doc_record.id,
            details=(
                f"Document '{original_name}' uploaded for FDR {fdr.fdr_number}. "
                f"Status: {doc_record.processing_status}, Result: {discrepancy_report.get('overall_result')}"
            ),
        )
        db.session.add(audit)
        db.session.commit()

        return doc_record, discrepancy_report

    except Exception:
        db.session.rollback()
        # Clean up only the newly created file if DB transaction failed
        if target_path.exists():
            try:
                os.remove(target_path)
            except OSError:
                pass
        analysis_path = get_analysis_file_path(upload_dir, stored_name)
        if analysis_path.exists():
            try:
                os.remove(analysis_path)
            except OSError:
                pass
        raise


def get_fdr_documents(fdr_id: int, current_user: User) -> list[Document]:
    """Retrieve all documents attached to an authorized FDR."""
    fdr = get_authorized_fdr_for_upload(fdr_id, current_user)
    return Document.query.filter_by(fdr_id=fdr.id).order_by(Document.uploaded_at.desc()).all()


def get_single_document(
    fdr_id: int, document_id: int, current_user: User, upload_dir: Path
) -> tuple[Document, dict | None]:
    """Retrieve a single document belonging to an authorized FDR with its analysis report."""
    fdr = get_authorized_fdr_for_upload(fdr_id, current_user)

    doc = Document.query.filter_by(id=document_id, fdr_id=fdr.id).first()
    if not doc:
        raise FDRNotFoundError("Document not found for this FDR record.")

    analysis = load_analysis_result(upload_dir, doc.stored_filename)
    return doc, analysis
