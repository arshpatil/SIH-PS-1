from flask import Blueprint, current_app, g, jsonify, request
from app.models.enums import NotificationType, ScrutinyStatus, UserRole
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.extensions import db
from app.security import login_required, roles_required
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
    check_fdr_duplicates,
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




@fdr_bp.route("/check-duplicate", methods=["POST"])
@login_required
def check_duplicate():
    """Check for identical or normalized FDR number intra- and cross-institution."""
    data = request.get_json(silent=True) or {}
    fdr_number = str(data.get("fdr_number", "")).strip()
    institution_id = data.get("institution_id")

    user_category = UserRole.normalize_category(g.current_user.role)
    if user_category == "INSTITUTION":
        institution_id = g.current_user.institution_id
    elif not institution_id:
        institution_id = g.current_user.institution_id or 1

    result = check_fdr_duplicates(fdr_number, institution_id, g.current_user)
    return jsonify({"success": True, **result}), 200


@fdr_bp.route("/<int:fdr_id>/documents/<int:document_id>/verify", methods=["POST"])
@roles_required(UserRole.AICTE_OFFICER, UserRole.ADMIN)
def verify_document_decision(fdr_id: int, document_id: int):
    """AICTE Officer records verification decision on an attached document and/or individual fields."""
    data = request.get_json(silent=True) or {}
    raw_decision = data.get("decision")
    decision = str(raw_decision).strip().upper() if raw_decision else None
    remarks = str(data.get("remarks", "")).strip()
    field_reviews = data.get("field_reviews")

    if not decision and not field_reviews:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Request must include a document-level 'decision' or a 'field_reviews' object.",
                    "code": "MISSING_DECISION_OR_FIELDS",
                }
            ),
            400,
        )

    valid_doc_decisions = {"VERIFIED", "REQUIRES_CORRECTION", "REJECTED"}
    if decision and decision not in valid_doc_decisions:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid document decision '{decision}'. Must be one of: {sorted(list(valid_doc_decisions))}",
                    "code": "INVALID_DECISION",
                }
            ),
            400,
        )

    valid_field_names = {
        "fdr_number",
        "bank_name",
        "branch_name",
        "amount",
        "issue_date",
        "maturity_date",
        "joint_lien",
    }
    valid_field_decisions = {"VERIFIED", "DISCREPANCY", "NEEDS_CORRECTION"}

    if field_reviews is not None:
        if not isinstance(field_reviews, dict):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "'field_reviews' must be a dictionary of field review objects.",
                        "code": "INVALID_FIELD_REVIEWS",
                    }
                ),
                400,
            )
        for fname, fval in field_reviews.items():
            if fname not in valid_field_names:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"Invalid field name '{fname}'. Allowed fields: {sorted(list(valid_field_names))}",
                            "code": "INVALID_FIELD_NAME",
                        }
                    ),
                    400,
                )
            if not isinstance(fval, dict) or "decision" not in fval:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"Field review for '{fname}' must include a 'decision'.",
                            "code": "INVALID_FIELD_REVIEW",
                        }
                    ),
                    400,
                )
            fdec = str(fval["decision"]).strip().upper()
            if fdec not in valid_field_decisions:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"Invalid decision '{fdec}' for field '{fname}'. Allowed: {sorted(list(valid_field_decisions))}",
                            "code": "INVALID_FIELD_DECISION",
                        }
                    ),
                    400,
                )

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    doc, analysis = get_single_document(fdr_id, document_id, g.current_user, upload_dir)
    fdr = get_authorized_fdr(fdr_id, g.current_user)

    if not analysis:
        analysis = {}

    if "field_reviews" not in analysis:
        analysis["field_reviews"] = {}

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # Apply and log field-level reviews
    if field_reviews:
        for fname, fval in field_reviews.items():
            fdec = str(fval["decision"]).strip().upper()
            frem = str(fval.get("remarks", "")).strip()[:1000]
            analysis["field_reviews"][fname] = {
                "decision": fdec,
                "remarks": frem,
                "reviewed_by_id": g.current_user.id,
                "reviewed_by_email": g.current_user.email,
                "reviewed_by_name": getattr(g.current_user, "full_name", None) or g.current_user.email,
                "reviewed_at": now_iso,
            }
            audit_field = AuditLog(
                user_id=g.current_user.id,
                action=f"DOCUMENT_FIELD_REVIEW_{fname.upper()}",
                entity_type="Document",
                entity_id=doc.id,
                details=f"Officer {g.current_user.email} marked field '{fname}' as {fdec} for Document {doc.id} (FDR {fdr.fdr_number}). Remarks: {frem}",
            )
            db.session.add(audit_field)

    # Apply and log document-level review if supplied
    if decision:
        analysis["document_review"] = {
            "decision": decision,
            "remarks": remarks,
            "reviewed_by_id": g.current_user.id,
            "reviewed_by_email": g.current_user.email,
            "reviewed_by_name": getattr(g.current_user, "full_name", None) or g.current_user.email,
            "reviewed_at": now_iso,
        }
        audit = AuditLog(
            user_id=g.current_user.id,
            action=f"DOCUMENT_DECISION_{decision}",
            entity_type="Document",
            entity_id=doc.id,
            details=f"Officer {g.current_user.email} marked document '{doc.original_filename}' as {decision}. Remarks: {remarks}",
        )
        db.session.add(audit)

        # Notify institution user
        notif_type = NotificationType.INFO
        if decision == "REQUIRES_CORRECTION":
            notif_type = NotificationType.ACTION_REQUIRED
        elif decision == "REJECTED":
            notif_type = NotificationType.ALERT

        notif = Notification(
            user_id=fdr.created_by,
            title=f"Document Review: {decision} ({fdr.fdr_number})",
            message=f"Document '{doc.original_filename}' for FDR {fdr.fdr_number} review outcome: {decision}. {f'Remarks: {remarks}' if remarks else ''}".strip(),
            notification_type=notif_type.value,
            is_read=False,
        )
        db.session.add(notif)

    from app.services.document_service import save_analysis_result
    save_analysis_result(upload_dir, doc.stored_filename, analysis)
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": "Document verification decision recorded successfully.",
                "decision": decision,
                "remarks": remarks,
                "field_reviews": analysis.get("field_reviews", {}),
                "document": doc.to_dict(),
                "discrepancy_report": analysis,
            }
        ),
        200,
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

    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

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


@fdr_bp.route("/<int:fdr_id>/bank-verify", methods=["POST"])
@login_required
def fdr_bank_verify_alias(fdr_id: int):
    """Alias for POST /api/bank/verify-fdr/<id>."""
    from app.routes.bank import verify_fdr_endpoint
    return verify_fdr_endpoint(fdr_id)


@fdr_bp.route("/<int:fdr_id>/demo-renewal-receipt", methods=["GET"])
@login_required
def download_demo_renewal_receipt(fdr_id: int):
    """
    Download a synthetic PDF renewal receipt for local testing and demonstration.
    Strictly forbidden in production environments.
    """
    from flask import send_file
    import io
    from app.services.synthetic_receipt_service import (
        is_demo_environment,
        generate_synthetic_renewal_receipt,
    )
    if not is_demo_environment():
        return (
            jsonify(
                {
                    "error": "Synthetic demo receipts are disabled in production mode.",
                    "code": "DEMO_DISABLED",
                }
            ),
            403,
        )

    fdr = get_authorized_fdr(fdr_id, g.current_user)

    new_fdr_num = request.args.get("new_fdr_number")
    pdf_bytes = generate_synthetic_renewal_receipt(
        fdr=fdr,
        new_fdr_number=new_fdr_num,
    )

    clean_num = "".join(c for c in fdr.fdr_number if c.isalnum() or c in "-_") or "fdr"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"DEMO_Renewal_Receipt_{clean_num}.pdf",
    )


@fdr_bp.route("/<int:fdr_id>/synthetic-documents/scenarios", methods=["GET"])
@login_required
def get_synthetic_document_scenarios(fdr_id: int):
    """
    List available synthetic FDR document scenarios for testing and demonstration.
    Strictly forbidden in production environments.
    """
    from app.services.synthetic_receipt_service import is_demo_environment
    from app.services.synthetic_fdr_generator import SYNTHETIC_SCENARIOS

    if not is_demo_environment():
        return (
            jsonify(
                {
                    "error": "Synthetic demo documents are disabled in production mode.",
                    "code": "DEMO_DISABLED",
                }
            ),
            403,
        )

    get_authorized_fdr(fdr_id, g.current_user)
    return jsonify({
        "success": True,
        "scenarios": list(SYNTHETIC_SCENARIOS.values()),
        "formats": [
            {"id": "pdf", "name": "Digital Vector PDF (PyMuPDF Text Extraction)"},
            {"id": "scanned_pdf", "name": "Scanned Raster PDF (Image-based, Tesseract OCR)"},
            {"id": "image", "name": "PNG Image Receipt (Tesseract OCR)"},
        ],
    })


@fdr_bp.route("/<int:fdr_id>/synthetic-documents/download", methods=["GET"])
@login_required
def download_synthetic_fdr_document(fdr_id: int):
    """
    Download a synthetic FDR document for a specific scenario and format.
    Strictly forbidden in production environments.
    """
    from flask import send_file
    import io
    from app.services.synthetic_receipt_service import is_demo_environment
    from app.services.synthetic_fdr_generator import (
        SYNTHETIC_SCENARIOS,
        generate_synthetic_fdr_document,
    )

    if not is_demo_environment():
        return (
            jsonify(
                {
                    "error": "Synthetic demo documents are disabled in production mode.",
                    "code": "DEMO_DISABLED",
                }
            ),
            403,
        )

    fdr = get_authorized_fdr(fdr_id, g.current_user)
    scenario_id = request.args.get("scenario", "MATCHING_FDR")
    doc_format = request.args.get("format", "pdf")

    if scenario_id not in SYNTHETIC_SCENARIOS:
        return (
            jsonify(
                {
                    "error": f"Invalid scenario '{scenario_id}'.",
                    "code": "INVALID_SCENARIO",
                }
            ),
            400,
        )

    raw_bytes, mime_type, filename = generate_synthetic_fdr_document(
        fdr=fdr, scenario_id=scenario_id, doc_format=doc_format
    )

    return send_file(
        io.BytesIO(raw_bytes),
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename,
    )


@fdr_bp.route("/<int:fdr_id>/synthetic-documents/load", methods=["POST"])
@login_required
def load_synthetic_fdr_document(fdr_id: int):
    """
    Generate a synthetic FDR document and immediately process it through the normal
    document processing and OCR verification pipeline on this FDR record.
    Strictly forbidden in production environments.
    """
    import io
    from werkzeug.datastructures import FileStorage
    from app.services.synthetic_receipt_service import is_demo_environment
    from app.services.synthetic_fdr_generator import (
        SYNTHETIC_SCENARIOS,
        generate_synthetic_fdr_document,
    )
    from app.services.document_service import process_and_save_document

    if not is_demo_environment():
        return (
            jsonify(
                {
                    "error": "Synthetic demo documents are disabled in production mode.",
                    "code": "DEMO_DISABLED",
                }
            ),
            403,
        )

    fdr = get_authorized_fdr(fdr_id, g.current_user)
    payload = request.get_json(silent=True) or {}
    scenario_id = payload.get("scenario") or request.args.get("scenario") or "MATCHING_FDR"
    doc_format = payload.get("format") or request.args.get("format") or "pdf"

    if scenario_id not in SYNTHETIC_SCENARIOS:
        return (
            jsonify(
                {
                    "error": f"Invalid scenario '{scenario_id}'.",
                    "code": "INVALID_SCENARIO",
                }
            ),
            400,
        )

    raw_bytes, mime_type, filename = generate_synthetic_fdr_document(
        fdr=fdr, scenario_id=scenario_id, doc_format=doc_format
    )

    file_obj = FileStorage(
        stream=io.BytesIO(raw_bytes),
        filename=filename,
        content_type=mime_type,
    )

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
    max_pages = current_app.config.get("MAX_PDF_PAGES", 20)

    doc, discrepancy_report = process_and_save_document(
        fdr_id=fdr_id,
        file=file_obj,
        current_user=g.current_user,
        upload_dir=upload_dir,
        max_bytes=max_bytes,
        max_pdf_pages=max_pages,
    )

    return (
        jsonify(
            {
                "success": True,
                "message": f"Synthetic demo document ({scenario_id}) loaded and analyzed successfully.",
                "document": doc.to_dict(),
                "discrepancy_report": discrepancy_report,
                "scenario": SYNTHETIC_SCENARIOS[scenario_id],
            }
        ),
        201,
    )


