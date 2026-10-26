from flask import Blueprint, current_app, g, jsonify, request
from app.models.enums import ScrutinyStatus
from app.security import login_required
from app.services.document_service import (
    get_fdr_documents,
    get_single_document,
    process_and_save_document,
)
from app.services.fdr_service import (
    FDRDuplicateError,
    FDRNotFoundError,
    FDRPermissionError,
    FDRServiceError,
    FDRValidationError,
    create_fdr_record,
    get_authorized_fdr,
    list_authorized_fdrs,
    update_fdr_record,
)
from app.services.workflow_service import (
    get_available_workflow_actions,
    get_fdr_workflow_history,
    transition_fdr_scrutiny_status,
)

fdr_bp = Blueprint("fdr", __name__, url_prefix="/api/fdr")


@fdr_bp.errorhandler(FDRValidationError)
def handle_fdr_validation_error(ex: FDRValidationError):
    return (
        jsonify(
            {
                "success": False,
                "error": ex.message,
                "code": ex.code,
                "details": ex.errors,
            }
        ),
        ex.status_code,
    )


@fdr_bp.errorhandler(FDRDuplicateError)
def handle_fdr_duplicate_error(ex: FDRDuplicateError):
    return (
        jsonify(
            {
                "success": False,
                "error": ex.message,
                "code": ex.code,
            }
        ),
        ex.status_code,
    )


@fdr_bp.errorhandler(FDRNotFoundError)
def handle_fdr_not_found_error(ex: FDRNotFoundError):
    return (
        jsonify(
            {
                "success": False,
                "error": ex.message,
                "code": ex.code,
            }
        ),
        ex.status_code,
    )


@fdr_bp.errorhandler(FDRPermissionError)
def handle_fdr_permission_error(ex: FDRPermissionError):
    return (
        jsonify(
            {
                "success": False,
                "error": ex.message,
                "code": ex.code,
            }
        ),
        ex.status_code,
    )


@fdr_bp.errorhandler(FDRServiceError)
def handle_generic_fdr_service_error(ex: FDRServiceError):
    return (
        jsonify(
            {
                "success": False,
                "error": ex.message,
                "code": ex.code,
            }
        ),
        ex.status_code,
    )


@fdr_bp.route("", methods=["POST"])
@login_required
def create_fdr():
    """Create a new FDR record for an authorized institution."""
    if not request.is_json:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Request body must be valid JSON.",
                    "code": "INVALID_JSON",
                }
            ),
            400,
        )

    payload = request.get_json(silent=True) or {}
    fdr = create_fdr_record(payload, g.current_user)
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR record created successfully.",
                "data": fdr.to_dict(),
            }
        ),
        201,
    )


@fdr_bp.route("", methods=["GET"])
@login_required
def list_fdrs():
    """List authorized FDR records with filtering and pagination."""
    items, pagination = list_authorized_fdrs(g.current_user, request.args)
    return (
        jsonify(
            {
                "success": True,
                "data": [item.to_dict() for item in items],
                "pagination": pagination,
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>", methods=["GET"])
@login_required
def get_fdr(fdr_id: int):
    """Retrieve an authorized FDR record by ID."""
    fdr = get_authorized_fdr(fdr_id, g.current_user)
    return (
        jsonify(
            {
                "success": True,
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>", methods=["PATCH"])
@login_required
def update_fdr(fdr_id: int):
    """Update permitted fields of an existing authorized FDR record."""
    if not request.is_json:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Request body must be valid JSON.",
                    "code": "INVALID_JSON",
                }
            ),
            400,
        )

    payload = request.get_json(silent=True) or {}
    fdr = update_fdr_record(fdr_id, payload, g.current_user)
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR record updated successfully.",
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


# ---------------------------------------------------------
# Document Upload and Discrepancy Endpoints
# ---------------------------------------------------------


@fdr_bp.route("/<int:fdr_id>/documents", methods=["POST"])
@login_required
def upload_fdr_document(fdr_id: int):
    """Upload a supporting FDR receipt document, run local OCR, and detect discrepancies."""
    if "file" not in request.files:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Multipart form request must include a 'file' field.",
                    "code": "MISSING_FILE",
                }
            ),
            400,
        )

    file = request.files["file"]
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
    max_pages = current_app.config.get("MAX_PDF_PAGES", 20)

    doc, discrepancy_report = process_and_save_document(
        fdr_id=fdr_id,
        file=file,
        current_user=g.current_user,
        upload_dir=upload_dir,
        max_bytes=max_bytes,
        max_pdf_pages=max_pages,
    )

    return (
        jsonify(
            {
                "success": True,
                "message": "Document uploaded and processed successfully.",
                "data": {
                    "document": doc.to_dict(),
                    "discrepancy_report": discrepancy_report,
                },
            }
        ),
        201,
    )


@fdr_bp.route("/<int:fdr_id>/documents", methods=["GET"])
@login_required
def list_fdr_documents(fdr_id: int):
    """List metadata for all documents attached to an authorized FDR record."""
    documents = get_fdr_documents(fdr_id, g.current_user)
    return (
        jsonify(
            {
                "success": True,
                "data": [doc.to_dict() for doc in documents],
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/documents/<int:document_id>", methods=["GET"])
@login_required
def get_fdr_document_detail(fdr_id: int, document_id: int):
    """Retrieve metadata and latest OCR discrepancy report for a specific document."""
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    doc, analysis = get_single_document(
        fdr_id, document_id, g.current_user, upload_dir
    )

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "document": doc.to_dict(),
                    "discrepancy_report": analysis,
                },
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/documents/<int:document_id>/download", methods=["GET"])
@login_required
def download_fdr_document(fdr_id: int, document_id: int):
    """Securely stream attached document file with Content-Disposition attachment."""
    from flask import send_file
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    doc, _ = get_single_document(fdr_id, document_id, g.current_user, upload_dir)
    file_path = upload_dir / doc.stored_filename
    if not file_path.exists():
        return (
            jsonify(
                {
                    "success": False,
                    "error": "File not found on storage disk.",
                    "code": "FILE_NOT_FOUND",
                }
            ),
            404,
        )
    return send_file(
        file_path,
        mimetype=doc.file_type or "application/octet-stream",
        as_attachment=True,
        download_name=doc.original_filename,
    )


# ---------------------------------------------------------
# FDR Scrutiny Workflow Endpoints (Step 7B)
# ---------------------------------------------------------


@fdr_bp.route("/<int:fdr_id>/submit", methods=["POST"])
@login_required
def submit_fdr(fdr_id: int):
    """
    Institution user submits a DRAFT or resubmits a RETURNED FDR for AICTE verification.
    Enforces that mandatory fields and at least one supporting document are present.
    """
    payload = request.get_json(silent=True) or {} if request.is_json else {}
    remarks = payload.get("remarks") if isinstance(payload, dict) else None

    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr_id,
        target_status=ScrutinyStatus.SUBMITTED,
        current_user=g.current_user,
        remarks=remarks,
        enforce_submission_requirements=True,
    )
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR submitted successfully for AICTE verification.",
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/start-review", methods=["POST"])
@login_required
def start_fdr_review(fdr_id: int):
    """
    Authorized AICTE officer transitions a SUBMITTED FDR into PENDING_VERIFICATION.
    """
    payload = request.get_json(silent=True) or {} if request.is_json else {}
    remarks = payload.get("remarks") if isinstance(payload, dict) else None

    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr_id,
        target_status=ScrutinyStatus.PENDING_VERIFICATION,
        current_user=g.current_user,
        remarks=remarks,
    )
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR review initiated successfully.",
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/verify", methods=["POST"])
@login_required
def verify_fdr(fdr_id: int):
    """
    Authorized AICTE officer approves and verifies an FDR in PENDING_VERIFICATION status.
    Accepts optional remarks (max 2000 chars).
    """
    payload = request.get_json(silent=True) or {} if request.is_json else {}
    remarks = payload.get("remarks") if isinstance(payload, dict) else None

    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr_id,
        target_status=ScrutinyStatus.VERIFIED,
        current_user=g.current_user,
        remarks=remarks,
    )
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR verified and approved successfully.",
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/return", methods=["POST"])
@login_required
def return_fdr(fdr_id: int):
    """
    Authorized AICTE officer returns an FDR in PENDING_VERIFICATION to the institution.
    Requires a non-empty reason/remarks (max 2000 chars).
    """
    payload = request.get_json(silent=True) or {} if request.is_json else {}
    reason = None
    if isinstance(payload, dict):
        reason = payload.get("reason") or payload.get("remarks")

    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr_id,
        target_status=ScrutinyStatus.RETURNED,
        current_user=g.current_user,
        remarks=reason,
    )
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR returned to institution for correction.",
                "reason": str(reason).strip() if reason else None,
                "scrutiny_status": fdr.scrutiny_status,
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/reject", methods=["POST"])
@login_required
def reject_fdr(fdr_id: int):
    """
    Authorized AICTE officer rejects an FDR in PENDING_VERIFICATION.
    Requires a non-empty reason/remarks (max 2000 chars).
    """
    payload = request.get_json(silent=True) or {} if request.is_json else {}
    reason = None
    if isinstance(payload, dict):
        reason = payload.get("reason") or payload.get("remarks")

    fdr = transition_fdr_scrutiny_status(
        fdr_id=fdr_id,
        target_status=ScrutinyStatus.REJECTED,
        current_user=g.current_user,
        remarks=reason,
    )
    return (
        jsonify(
            {
                "success": True,
                "message": "FDR submission rejected.",
                "reason": str(reason).strip() if reason else None,
                "scrutiny_status": fdr.scrutiny_status,
                "data": fdr.to_dict(),
            }
        ),
        200,
    )


@fdr_bp.route("/<int:fdr_id>/workflow", methods=["GET"])
@login_required
def get_fdr_workflow(fdr_id: int):
    """
    Retrieve workflow state, permitted actions, structured history, and deficiency notices for an authorized FDR.
    Supports optional pagination via page and per_page query parameters.
    """
    fdr = get_authorized_fdr(fdr_id, g.current_user)
    available_actions = get_available_workflow_actions(fdr, g.current_user)

    page = request.args.get("page")
    per_page = request.args.get("per_page")

    history, pagination, deficiencies = get_fdr_workflow_history(
        fdr, g.current_user, page=page, per_page=per_page
    )

    data = {
        "fdr_id": fdr.id,
        "fdr_number": fdr.fdr_number,
        "scrutiny_status": fdr.scrutiny_status,
        "validity_status": fdr.validity_status,
        "is_authorized": True,
        "available_actions": available_actions,
        "workflow_history": history,
        "deficiencies": deficiencies,
    }
    if pagination:
        data["pagination"] = pagination

    return (
        jsonify(
            {
                "success": True,
                "data": data,
            }
        ),
        200,
    )
