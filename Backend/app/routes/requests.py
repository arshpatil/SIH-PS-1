from flask import Blueprint, g, jsonify, request
from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import NotificationType, UserRole
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.notification import Notification
from app.models.user import User
from app.security import login_required, roles_required

requests_bp = Blueprint("requests", __name__, url_prefix="/api/requests")


@requests_bp.route("", methods=["GET"])
@login_required
def list_requests():
    """List FDR renewal and release requests with role-based data isolation."""
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    query = FDRRequest.query

    if user_category == "INSTITUTION":
        if not user.institution_id:
            return jsonify({"success": True, "data": [], "count": 0}), 200
        query = query.filter_by(institution_id=user.institution_id)
    else:
        # AICTE Officers & Admins can filter by institution_id or fdr_id
        inst_id = request.args.get("institution_id", type=int)
        if inst_id:
            query = query.filter_by(institution_id=inst_id)

    fdr_id = request.args.get("fdr_id", type=int)
    if fdr_id:
        query = query.filter_by(fdr_id=fdr_id)

    status_filter = request.args.get("status")
    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(FDRRequest.status.ilike(f"%{status_filter}%"))

    type_filter = request.args.get("type")
    if type_filter and type_filter.upper() != "ALL":
        query = query.filter(FDRRequest.request_type.ilike(f"%{type_filter}%"))

    reqs = query.order_by(FDRRequest.created_at.desc()).all()
    return (
        jsonify(
            {
                "success": True,
                "data": [r.to_dict() for r in reqs],
                "count": len(reqs),
            }
        ),
        200,
    )


@requests_bp.route("", methods=["POST"])
@login_required
def create_request():
    """Submit a statutory renewal or release petition for an FDR."""
    uploaded_file = None
    if request.content_type and "multipart/form-data" in request.content_type:
        form_data = request.form
        fdr_id = form_data.get("fdr_id") or form_data.get("fdrId")
        req_type_input = str(form_data.get("request_type") or form_data.get("requestType") or "Renewal").strip()
        reason_input = str(form_data.get("reason") or form_data.get("justification") or "").strip()
        remarks_input = form_data.get("remarks")
        uploaded_file = request.files.get("file") or request.files.get("supporting_document")
        doc_name = form_data.get("supporting_document") or form_data.get("supportingDocument")
        doc_size = form_data.get("document_size") or form_data.get("documentSize")
    elif request.is_json:
        data = request.get_json(silent=True) or {}
        fdr_id = data.get("fdr_id") or data.get("fdrId")
        req_type_input = str(data.get("request_type") or data.get("requestType") or "Renewal").strip()
        reason_input = str(data.get("reason") or data.get("justification") or "").strip()
        remarks_input = data.get("remarks")
        doc_name = str(data.get("supporting_document") or data.get("supportingDocument") or "").strip() or None
        doc_size = data.get("document_size") or data.get("documentSize")
    else:
        return (
            jsonify({"error": "Request body must be valid JSON or multipart/form-data.", "code": "INVALID_CONTENT_TYPE"}),
            400,
        )

    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    if not fdr_id:
        return (
            jsonify({"error": "Field 'fdr_id' is required.", "code": "MISSING_FIELD"}),
            400,
        )

    try:
        fdr_id = int(fdr_id)
    except (ValueError, TypeError):
        return (
            jsonify({"error": "Field 'fdr_id' must be a valid integer ID.", "code": "INVALID_FIELD"}),
            400,
        )

    # Multi-tenant authorization check
    if user_category == "INSTITUTION":
        if not user.institution_id:
            return (
                jsonify(
                    {
                        "error": "User account is not linked to any institution.",
                        "code": "UNLINKED_INSTITUTION",
                    }
                ),
                403,
            )
        fdr = FDRRecord.query.filter_by(id=fdr_id, institution_id=user.institution_id).first()
    else:
        fdr = FDRRecord.query.get(fdr_id)

    if not fdr:
        return (
            jsonify(
                {
                    "error": "FDR record not found or inaccessible.",
                    "code": "FDR_NOT_FOUND",
                }
            ),
            404,
        )

    # Validate request type
    if "release" in req_type_input.lower():
        canonical_type = "Release"
    elif "renew" in req_type_input.lower():
        canonical_type = "Renewal"
    else:
        return (
            jsonify(
                {
                    "error": "Field 'request_type' must be either 'Renewal' or 'Release'.",
                    "code": "INVALID_FIELD",
                }
            ),
            400,
        )

    # Validate reason / justification
    if not reason_input:
        return (
            jsonify(
                {
                    "error": "A clear institutional justification is required for submitting this petition.",
                    "code": "MISSING_JUSTIFICATION",
                }
            ),
            400,
        )

    file_bytes = None
    if uploaded_file and uploaded_file.filename:
        from werkzeug.utils import secure_filename
        original_name = secure_filename(uploaded_file.filename) or "supporting_document.pdf"
        file_bytes = uploaded_file.read()
        doc_name = original_name
        doc_size = len(file_bytes)
    else:
        if doc_size:
            try:
                doc_size = int(doc_size)
            except (ValueError, TypeError):
                doc_size = None

    try:
        fdr_req = FDRRequest(
            fdr_id=fdr.id,
            institution_id=fdr.institution_id,
            created_by=user.id,
            request_type=canonical_type,
            status="Submitted",
            stage="Desk Review",
            reason=reason_input,
            supporting_document=doc_name,
            document_size=doc_size,
            remarks=remarks_input or "New administrative petition lodged via portal.",
        )
        db.session.add(fdr_req)
        db.session.flush()

        # If a file was uploaded, save it to request uploads directory
        if file_bytes and doc_name:
            import os
            from pathlib import Path
            from flask import current_app
            req_upload_dir = current_app.config.get("REQUEST_UPLOAD_FOLDER") or (
                current_app.config["UPLOAD_FOLDER"] / "requests"
            )
            os.makedirs(req_upload_dir, exist_ok=True)
            save_path = (Path(req_upload_dir) / f"req_{fdr_req.id}_{doc_name}").resolve()
            with open(save_path, "wb") as f:
                f.write(file_bytes)
        db.session.flush()

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action=f"REQUEST_SUBMITTED_{canonical_type.upper()}",
            entity_type="FDRRequest",
            entity_id=fdr_req.id,
            details=f"Submitted {canonical_type} petition REQ-{fdr_req.id:04d} for FDR {fdr.fdr_number}.",
        )
        db.session.add(audit)

        # Notify institution user
        notif = Notification(
            user_id=user.id,
            title=f"{canonical_type} Petition Lodged (REQ-{fdr_req.id:04d})",
            message=f"Your {canonical_type.lower()} petition for FDR {fdr.fdr_number} ({fdr.bank_name}) has been registered and queued for AICTE desk scrutiny.",
            notification_type=NotificationType.INFO.value,
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return (
            jsonify({"error": f"Failed to persist petition: {str(ex)}", "code": "DB_ERROR"}),
            500,
        )

    return (
        jsonify(
            {
                "success": True,
                "message": f"{canonical_type} petition REQ-{fdr_req.id:04d} submitted successfully.",
                "data": fdr_req.to_dict(),
            }
        ),
        201,
    )


@requests_bp.route("/<int:request_id>/status", methods=["PATCH"])
@roles_required(UserRole.AICTE_OFFICER, UserRole.ADMIN)
def update_request_status(request_id):
    """AICTE Officer status transition for FDR petitions."""
    if not request.is_json:
        return jsonify({"error": "Request body must be valid JSON.", "code": "INVALID_JSON"}), 400

    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip()
    valid_statuses = {"Submitted", "Under Review", "Approved", "Rejected"}

    matched_status = next((s for s in valid_statuses if s.lower() == new_status.lower()), None)
    if not matched_status:
        return (
            jsonify({"error": f"Invalid status. Must be one of: {sorted(valid_statuses)}", "code": "INVALID_STATUS"}),
            400,
        )

    fdr_req = FDRRequest.query.get(request_id)
    if not fdr_req:
        return jsonify({"error": "Request not found.", "code": "NOT_FOUND"}), 404

    remarks = str(data.get("remarks", "")).strip()
    fdr_req.status = matched_status
    if remarks:
        fdr_req.remarks = remarks

    if matched_status == "Approved":
        fdr_req.stage = "Processed & Finalized"
    elif matched_status == "Rejected":
        fdr_req.stage = "Decision Rendered"
    elif matched_status == "Under Review":
        fdr_req.stage = "Bureau Officer Scrutiny"

    audit = AuditLog(
        user_id=g.current_user.id,
        action=f"REQUEST_STATUS_UPDATED_{matched_status.upper()}",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=f"Petition REQ-{fdr_req.id:04d} transitioned to {matched_status}. Remarks: {remarks}",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": f"Petition status updated to {matched_status}.",
                "data": fdr_req.to_dict(),
            }
        ),
        200,
    )


@requests_bp.route("/<request_id>/download", methods=["GET"])
@login_required
def download_request_attachment(request_id):
    """Securely stream request supporting document with Content-Disposition attachment.

    Enforces multi-tenant authorization:
    - Institutions can only download attachments of requests belonging to their own institution.
    - AICTE Officers and Admins can download attachments across institutions.
    """
    import mimetypes
    from pathlib import Path
    from flask import current_app, send_file

    # Parse numeric request ID (supports e.g. 3 or "REQ-0003")
    numeric_id = None
    if isinstance(request_id, int):
        numeric_id = request_id
    elif isinstance(request_id, str):
        cleaned = request_id.strip()
        if cleaned.isdigit():
            numeric_id = int(cleaned)
        elif cleaned.upper().startswith("REQ-"):
            raw = cleaned.upper().replace("REQ-", "")
            if raw.isdigit():
                numeric_id = int(raw)

    if not numeric_id:
        return (
            jsonify({"error": "Invalid request ID format.", "code": "INVALID_ID"}),
            400,
        )

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return (
            jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}),
            404,
        )

    # Multi-tenant authorization check
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    if user_category == "INSTITUTION":
        if not user.institution_id or fdr_req.institution_id != user.institution_id:
            return (
                jsonify(
                    {
                        "error": "Petition request not found or inaccessible.",
                        "code": "NOT_FOUND",
                    }
                ),
                404,
            )

    # Check if request has an attachment filename
    if not fdr_req.supporting_document:
        return (
            jsonify(
                {
                    "error": "No supporting document is attached to this petition.",
                    "code": "ATTACHMENT_NOT_FOUND",
                }
            ),
            404,
        )

    doc_name = fdr_req.supporting_document.strip()

    # Search for the document file across configured upload directories
    req_upload_dir = current_app.config.get("REQUEST_UPLOAD_FOLDER") or (
        current_app.config["UPLOAD_FOLDER"] / "requests"
    )
    fdr_upload_dir = current_app.config["UPLOAD_FOLDER"]

    candidate_paths = [
        (Path(req_upload_dir) / f"req_{fdr_req.id}_{doc_name}").resolve(),
        (Path(req_upload_dir) / doc_name).resolve(),
        (Path(fdr_upload_dir) / f"req_{fdr_req.id}_{doc_name}").resolve(),
        (Path(fdr_upload_dir) / doc_name).resolve(),
    ]

    stored_name = getattr(fdr_req, "stored_filename", None)
    if stored_name:
        candidate_paths.insert(0, (Path(req_upload_dir) / stored_name).resolve())
        candidate_paths.insert(1, (Path(fdr_upload_dir) / stored_name).resolve())

    # If the request matches the underlying FDR document, check FDR documents too
    if fdr_req.fdr and fdr_req.fdr.documents:
        for fdr_doc in fdr_req.fdr.documents:
            if fdr_doc.stored_filename:
                candidate_paths.append((Path(fdr_upload_dir) / fdr_doc.stored_filename).resolve())

    file_path = None
    for p in candidate_paths:
        try:
            # Ensure path is inside approved directory bounds (prevent traversal)
            req_dir_res = Path(req_upload_dir).resolve()
            fdr_dir_res = Path(fdr_upload_dir).resolve()
            if (
                str(p).startswith(str(req_dir_res))
                or str(p).startswith(str(fdr_dir_res))
            ) and p.is_file():
                file_path = p
                break
        except Exception:
            continue

    if not file_path or not file_path.exists():
        return (
            jsonify(
                {
                    "error": f"Supporting document file '{doc_name}' not found on storage disk.",
                    "code": "FILE_NOT_FOUND",
                }
            ),
            404,
        )

    # Audit log the successful download
    try:
        audit = AuditLog(
            user_id=user.id,
            action="REQUEST_ATTACHMENT_DOWNLOADED",
            entity_type="FDRRequest",
            entity_id=fdr_req.id,
            details=f"Downloaded supporting document '{doc_name}' for petition REQ-{fdr_req.id:04d}.",
        )
        db.session.add(audit)
        db.session.commit()
    except Exception:
        db.session.rollback()

    mime_type, _ = mimetypes.guess_type(str(file_path))
    return send_file(
        file_path,
        mimetype=mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=doc_name,
    )
