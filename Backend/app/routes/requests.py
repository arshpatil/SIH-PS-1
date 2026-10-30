from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import os
from pathlib import Path
from flask import Blueprint, current_app, g, jsonify, request, send_file
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.enums import DocumentProcessingStatus, NotificationType, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.notification import Notification
from app.models.renewal_history import FDRRenewalHistory
from app.models.user import User
from app.security import login_required, roles_required
from app.services.maturity_service import classify_validity_status, get_business_date

requests_bp = Blueprint("requests", __name__, url_prefix="/api/requests")

# Standardized petition statuses and their respective default stages
VALID_REQUEST_STATUSES = {
    "Submitted": "Desk Scrutiny",
    "Under Review": "Bureau Officer Scrutiny",
    "Documents Required": "Awaiting Institutional Documents",
    "Resubmitted / Awaiting Review": "Resubmitted for Review",
    "Approved": "Approved — Awaiting Renewed Deposit Receipt",
    "Pending Verification": "Pending Renewal Receipt Verification",
    "Rejected": "Rejected & Closed",
    "Closed": "Case Closed",
}


def parse_request_id(raw_id: str | int | None) -> int | None:
    """Safely parse numeric integer ID from int or strings like '12', 'REQ-0012'."""
    if raw_id is None:
        return None
    if isinstance(raw_id, int):
        return raw_id
    cleaned = str(raw_id).strip()
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned.upper().startswith("REQ-"):
        num_part = cleaned.upper().replace("REQ-", "")
        if num_part.isdigit():
            return int(num_part)
    return None


@requests_bp.route("", methods=["GET"])
@login_required
def list_requests():
    """List FDR renewal and release requests with multi-tenant data isolation and advanced filtering."""
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    query = FDRRequest.query

    # Multi-tenant scoping
    if user_category == "INSTITUTION":
        if not user.institution_id:
            return jsonify({"success": True, "data": [], "count": 0}), 200
        query = query.filter_by(institution_id=user.institution_id)
    else:
        inst_id = request.args.get("institution_id", type=int)
        if inst_id:
            query = query.filter_by(institution_id=inst_id)

    # Filter by specific FDR
    fdr_id = request.args.get("fdr_id", type=int)
    if fdr_id:
        query = query.filter_by(fdr_id=fdr_id)

    # Filter by assigned officer / unassigned
    unassigned_param = request.args.get("unassigned")
    assigned_to_param = request.args.get("assigned_to")
    if (unassigned_param and unassigned_param.lower() in ("true", "1", "yes")) or assigned_to_param == "unassigned":
        query = query.filter(FDRRequest.assigned_to.is_(None))
    elif assigned_to_param:
        if str(assigned_to_param).lower() == "me":
            query = query.filter_by(assigned_to=user.id)
        else:
            try:
                query = query.filter_by(assigned_to=int(assigned_to_param))
            except (ValueError, TypeError):
                pass

    # Filter by status
    status_filter = request.args.get("status")
    if status_filter and status_filter.upper() != "ALL":
        clean_status = status_filter.strip()
        matched = next((k for k in VALID_REQUEST_STATUSES if k.lower() == clean_status.lower()), None)
        if matched:
            query = query.filter(FDRRequest.status == matched)
        else:
            query = query.filter(FDRRequest.status.ilike(f"%{clean_status}%"))

    # Filter by request type
    type_filter = request.args.get("type")
    if type_filter and type_filter.upper() != "ALL":
        query = query.filter(FDRRequest.request_type.ilike(f"%{type_filter.strip()}%"))

    # Filter by overdue status (> 14 days pending review)
    overdue_param = request.args.get("overdue")
    if overdue_param and overdue_param.lower() in ("true", "1", "yes"):
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        active_statuses = ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]
        query = query.filter(FDRRequest.status.in_(active_statuses), FDRRequest.created_at <= cutoff)

    # Search filter (Request ID, FDR Number, Bank Name)
    search_q = request.args.get("search")
    if search_q and search_q.strip():
        q_term = f"%{search_q.strip()}%"
        # Support search by REQ-0004 or raw number
        raw_num = search_q.strip().upper().replace("REQ-", "")
        if raw_num.isdigit():
            req_id_match = int(raw_num)
            query = query.join(FDRRecord).filter(
                or_(
                    FDRRequest.id == req_id_match,
                    FDRRecord.fdr_number.ilike(q_term),
                    FDRRecord.bank_name.ilike(q_term),
                )
            )
        else:
            query = query.join(FDRRecord).filter(
                or_(
                    FDRRecord.fdr_number.ilike(q_term),
                    FDRRecord.bank_name.ilike(q_term),
                )
            )

    # Ordering
    query = query.order_by(FDRRequest.created_at.desc(), FDRRequest.id.desc())

    # Pagination
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    if page and per_page:
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        return (
            jsonify(
                {
                    "success": True,
                    "data": [r.to_dict() for r in paginated.items],
                    "total": paginated.total,
                    "page": paginated.page,
                    "pages": paginated.pages,
                    "count": len(paginated.items),
                }
            ),
            200,
        )

    reqs = query.all()
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


@requests_bp.route("/stats", methods=["GET"])
@login_required
def get_request_stats():
    """Aggregate petition statistics and backlog metrics."""
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    query = FDRRequest.query
    if user_category == "INSTITUTION":
        if not user.institution_id:
            return jsonify({"success": True, "stats": {}}), 200
        query = query.filter_by(institution_id=user.institution_id)

    total = query.count()
    submitted = query.filter_by(status="Submitted").count()
    under_review = query.filter_by(status="Under Review").count()
    docs_required = query.filter_by(status="Documents Required").count()
    resubmitted = query.filter_by(status="Resubmitted / Awaiting Review").count()
    approved = query.filter_by(status="Approved").count()
    rejected = query.filter_by(status="Rejected").count()
    closed = query.filter_by(status="Closed").count()

    # Overdue threshold: 14 days without resolution
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    active_statuses = ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]
    overdue = query.filter(FDRRequest.status.in_(active_statuses), FDRRequest.created_at <= cutoff).count()

    stats = {
        "total": total,
        "submitted": submitted,
        "under_review": under_review,
        "documents_required": docs_required,
        "resubmitted": resubmitted,
        "approved": approved,
        "rejected": rejected,
        "closed": closed,
        "overdue": overdue,
    }

    return jsonify({"success": True, "stats": stats}), 200


@requests_bp.route("/<request_id>", methods=["GET"])
@login_required
def get_request_detail(request_id):
    """Get full details and audit history of a specific petition."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"success": False, "error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"success": False, "error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    # Multi-tenant authorization
    if user_category == "INSTITUTION":
        if not user.institution_id or fdr_req.institution_id != user.institution_id:
            return jsonify({"success": False, "error": "Petition request not found or inaccessible.", "code": "NOT_FOUND"}), 404

    # Retrieve audit history for this petition
    audit_events = (
        AuditLog.query.filter_by(entity_type="FDRRequest", entity_id=fdr_req.id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    history = [
        {
            "id": a.id,
            "action": a.action,
            "actor_id": a.user_id,
            "actor_name": a.user.full_name if a.user else "System",
            "actor_role": a.user.role if a.user else None,
            "details": a.details,
            "timestamp": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audit_events
    ]

    req_dict = fdr_req.to_dict()
    req_dict["history"] = history

    return jsonify({"success": True, "data": req_dict}), 200


@requests_bp.route("", methods=["POST"])
@login_required
def create_request():
    """Submit a statutory renewal or release petition for an FDR.

    Prevents duplicate active requests of the same type for the same FDR.
    """
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
        return jsonify({"error": "Field 'fdr_id' is required.", "code": "MISSING_FIELD"}), 400

    try:
        fdr_id = int(fdr_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Field 'fdr_id' must be a valid integer ID.", "code": "INVALID_FIELD"}), 400

    # Multi-tenant authorization check
    if user_category == "INSTITUTION":
        if not user.institution_id:
            return jsonify({"error": "User account is not linked to any institution.", "code": "UNLINKED_INSTITUTION"}), 403
        fdr = FDRRecord.query.filter_by(id=fdr_id, institution_id=user.institution_id).first()
    else:
        fdr = db.session.get(FDRRecord, fdr_id)

    if not fdr:
        return jsonify({"error": "FDR record not found or inaccessible.", "code": "FDR_NOT_FOUND"}), 404

    # Validate request type
    if "release" in req_type_input.lower():
        canonical_type = "Release"
    elif "renew" in req_type_input.lower():
        canonical_type = "Renewal"
    else:
        return jsonify({"error": "Field 'request_type' must be either 'Renewal' or 'Release'.", "code": "INVALID_FIELD"}), 400

    # Prevent duplicate active requests for the same FDR and request type
    active_existing = FDRRequest.query.filter(
        FDRRequest.fdr_id == fdr.id,
        FDRRequest.request_type == canonical_type,
        FDRRequest.status.in_(["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]),
    ).first()
    if active_existing:
        return (
            jsonify(
                {
                    "error": f"An active {canonical_type.lower()} petition (REQ-{active_existing.id:04d}) is already in progress for FDR {fdr.fdr_number}.",
                    "code": "DUPLICATE_ACTIVE_REQUEST",
                    "request_id": active_existing.id,
                }
            ),
            409,
        )

    # Validate reason / justification
    if not reason_input:
        return jsonify({"error": "A clear institutional justification is required for submitting this petition.", "code": "MISSING_JUSTIFICATION"}), 400

    file_bytes = None
    if uploaded_file and uploaded_file.filename:
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
            stage=VALID_REQUEST_STATUSES["Submitted"],
            reason=reason_input,
            supporting_document=doc_name,
            document_size=doc_size,
            remarks=remarks_input or "New administrative petition lodged via portal.",
        )
        db.session.add(fdr_req)
        db.session.flush()

        # If a real file was uploaded, persist it safely
        if file_bytes and doc_name:
            req_upload_dir = current_app.config.get("REQUEST_UPLOAD_FOLDER") or (
                current_app.config["UPLOAD_FOLDER"] / "requests"
            )
            os.makedirs(req_upload_dir, exist_ok=True)
            stored_file_path = Path(req_upload_dir) / f"req_{fdr_req.id}_{doc_name}"
            with open(stored_file_path, "wb") as f_out:
                f_out.write(file_bytes)

        # Audit log creation
        audit = AuditLog(
            user_id=user.id,
            action=f"REQUEST_CREATED_{canonical_type.upper()}",
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
        return jsonify({"error": f"Failed to persist petition: {str(ex)}", "code": "DB_ERROR"}), 500

    # Post-commit statutory email notification (strictly non-blocking on failure)
    try:
        from app.services.email_service import send_petition_status_email
        send_petition_status_email(fdr_req, "Submitted")
    except Exception as email_err:
        current_app.logger.error(
            f"Non-fatal error delivering petition creation email for REQ-{fdr_req.id:04d}: {email_err}"
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


@requests_bp.route("/<request_id>/resubmit", methods=["POST"])
@login_required
def resubmit_request(request_id):
    """Institution resubmits a petition with requested documents after deficiency notification."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"success": False, "error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"success": False, "error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    # Multi-tenant authorization: Only the owning institution can resubmit
    if user_category == "INSTITUTION":
        if not user.institution_id or fdr_req.institution_id != user.institution_id:
            return jsonify({"success": False, "error": "Petition request not found or inaccessible.", "code": "NOT_FOUND"}), 404

    # Petition must be in 'Documents Required' status
    if fdr_req.status != "Documents Required":
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Only petitions in 'Documents Required' status can be resubmitted (current status: {fdr_req.status}).",
                    "code": "INVALID_STATE",
                }
            ),
            400,
        )

    # Extract file or remarks
    uploaded_file = None
    remarks = ""
    if request.content_type and "multipart/form-data" in request.content_type:
        uploaded_file = request.files.get("file") or request.files.get("supporting_document")
        remarks = str(request.form.get("remarks") or request.form.get("response") or "").strip()
    elif request.is_json:
        data = request.get_json(silent=True) or {}
        remarks = str(data.get("remarks") or data.get("response") or "").strip()

    file_bytes = None
    if uploaded_file and uploaded_file.filename:
        original_name = secure_filename(uploaded_file.filename) or "resubmitted_document.pdf"
        file_bytes = uploaded_file.read()
        fdr_req.supporting_document = original_name
        fdr_req.document_size = len(file_bytes)

        req_upload_dir = current_app.config.get("REQUEST_UPLOAD_FOLDER") or (
            current_app.config["UPLOAD_FOLDER"] / "requests"
        )
        os.makedirs(req_upload_dir, exist_ok=True)
        stored_file_path = Path(req_upload_dir) / f"req_{fdr_req.id}_{original_name}"
        with open(stored_file_path, "wb") as f_out:
            f_out.write(file_bytes)

    # Transition status
    fdr_req.status = "Resubmitted / Awaiting Review"
    fdr_req.stage = VALID_REQUEST_STATUSES["Resubmitted / Awaiting Review"]
    if remarks:
        fdr_req.remarks = f"{fdr_req.remarks or ''} | Institution Response: {remarks}".strip(" | ")

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="REQUEST_RESUBMITTED",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=f"Petition REQ-{fdr_req.id:04d} resubmitted by institution with remarks: '{remarks}'. Document: {fdr_req.supporting_document}",
    )
    db.session.add(audit)

    # Notify assigned officer or bureau
    if fdr_req.assigned_to:
        notif = Notification(
            user_id=fdr_req.assigned_to,
            title=f"Petition Resubmitted (REQ-{fdr_req.id:04d})",
            message=f"Institution has resubmitted required documentation for {fdr_req.request_type} petition REQ-{fdr_req.id:04d}.",
            notification_type=NotificationType.ACTION_REQUIRED.value,
            is_read=False,
        )
        db.session.add(notif)

    db.session.commit()

    # Post-commit statutory email notification (strictly non-blocking on failure)
    try:
        from app.services.email_service import send_petition_status_email
        send_petition_status_email(fdr_req, "Resubmitted / Awaiting Review", remarks=remarks)
    except Exception as email_err:
        current_app.logger.error(
            f"Non-fatal error delivering resubmit status email for REQ-{fdr_req.id:04d}: {email_err}"
        )

    return (
        jsonify(
            {
                "success": True,
                "message": f"Petition REQ-{fdr_req.id:04d} resubmitted successfully for AICTE review.",
                "data": fdr_req.to_dict(),
            }
        ),
        200,
    )


@requests_bp.route("/<request_id>/status", methods=["PATCH"])
@roles_required(UserRole.AICTE_OFFICER, UserRole.ADMIN)
def update_request_status(request_id):
    """AICTE Officer status transition for FDR petitions with comprehensive lifecycle validation."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    if not request.is_json:
        return jsonify({"error": "Request body must be valid JSON.", "code": "INVALID_JSON"}), 400

    data = request.get_json(silent=True) or {}
    new_status_input = str(data.get("status", "")).strip()

    matched_status = next(
        (s for s in VALID_REQUEST_STATUSES if s.lower() == new_status_input.lower()),
        None,
    )
    if not matched_status:
        return (
            jsonify(
                {
                    "error": f"Invalid status. Must be one of: {sorted(list(VALID_REQUEST_STATUSES.keys()))}",
                    "code": "INVALID_STATUS",
                }
            ),
            400,
        )

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    remarks = str(data.get("remarks", "")).strip()

    # Mandatory remarks check for deficiency (Documents Required) or rejection
    if matched_status in ("Documents Required", "Rejected") and not remarks:
        return (
            jsonify(
                {
                    "error": f"Official remarks/reason are required when setting status to '{matched_status}'.",
                    "code": "REMARKS_REQUIRED",
                }
            ),
            400,
        )

    fdr_req.status = matched_status
    if matched_status == "Approved" and fdr_req.request_type == "Renewal":
        fdr_req.stage = "Approved — Awaiting Renewed Deposit Receipt"
    else:
        fdr_req.stage = VALID_REQUEST_STATUSES[matched_status]
    if remarks:
        fdr_req.remarks = remarks

    # Record audit log
    audit = AuditLog(
        user_id=g.current_user.id,
        action=f"REQUEST_STATUS_UPDATED_{matched_status.upper().replace(' ', '_').replace('/', '_')}",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=f"Petition REQ-{fdr_req.id:04d} transitioned to '{matched_status}'. Remarks: '{remarks}'. Stage: '{fdr_req.stage}'",
    )
    db.session.add(audit)

    # Notify institution user
    notif_type = NotificationType.INFO
    if matched_status == "Documents Required":
        notif_type = NotificationType.ACTION_REQUIRED
    elif matched_status == "Rejected":
        notif_type = NotificationType.ALERT

    if matched_status == "Approved" and fdr_req.request_type == "Renewal":
        notif_title = f"Renewal Petition Approved (REQ-{fdr_req.id:04d})"
        notif_msg = (
            f"Your renewal petition for FDR {fdr_req.fdr.fdr_number if fdr_req.fdr else ''} has been approved by AICTE. "
            f"Please upload the renewed FDR receipt and updated details from your issuing bank."
        )
    else:
        notif_title = f"Petition Status Update: {matched_status} (REQ-{fdr_req.id:04d})"
        notif_msg = f"Your {fdr_req.request_type} petition REQ-{fdr_req.id:04d} status has been updated to '{matched_status}'. {f'Remarks: {remarks}' if remarks else ''}".strip()

    notif = Notification(
        user_id=fdr_req.created_by,
        title=notif_title,
        message=notif_msg,
        notification_type=notif_type.value,
        is_read=False,
    )
    db.session.add(notif)
    db.session.commit()

    # Post-commit statutory email notification (strictly non-blocking on failure)
    try:
        from app.services.email_service import (
            send_petition_status_email,
            send_renewal_receipt_required_email,
        )
        send_petition_status_email(fdr_req, matched_status, remarks=remarks)
        if matched_status == "Approved" and fdr_req.request_type == "Renewal":
            send_renewal_receipt_required_email(fdr_req)
    except Exception as email_err:
        current_app.logger.error(
            f"Non-fatal error delivering petition status email for REQ-{fdr_req.id:04d}: {email_err}"
        )

    return (
        jsonify(
            {
                "success": True,
                "message": f"Petition status updated to '{matched_status}'.",
                "data": fdr_req.to_dict(),
            }
        ),
        200,
    )


@requests_bp.route("/<request_id>/submit-renewal", methods=["POST"])
@login_required
def submit_renewal(request_id):
    """Institution uploads renewed FDR receipt and details after renewal petition approval."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    # Multi-tenant authorization
    if user_category == "INSTITUTION":
        if not user.institution_id or fdr_req.institution_id != user.institution_id:
            return jsonify({"error": "Petition request not found or inaccessible.", "code": "NOT_FOUND"}), 404

    if fdr_req.request_type != "Renewal":
        return jsonify({"error": "Only renewal petitions accept renewed FDR receipt submissions.", "code": "INVALID_REQUEST_TYPE"}), 400

    if fdr_req.status not in ("Approved", "Documents Required", "Pending Verification"):
        return jsonify({
            "error": f"Renewed FDR receipt can only be submitted for approved petitions (current status: {fdr_req.status}).",
            "code": "INVALID_STATE",
        }), 400

    # Extract input from multipart/form-data or json
    uploaded_file = None
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        new_fdr_num = str(form.get("new_fdr_number") or form.get("fdr_number") or form.get("newFdrNumber") or (fdr_req.fdr.fdr_number if fdr_req.fdr else "")).strip()
        issue_d_str = form.get("new_issue_date") or form.get("issue_date") or form.get("newIssueDate")
        mat_d_str = form.get("new_maturity_date") or form.get("maturity_date") or form.get("newMaturityDate")
        amount_raw = form.get("new_amount") or form.get("amount") or form.get("newAmount")
        remarks = str(form.get("remarks") or "").strip()
        uploaded_file = request.files.get("file") or request.files.get("renewal_document") or request.files.get("receipt")
    elif request.is_json:
        data = request.get_json(silent=True) or {}
        new_fdr_num = str(data.get("new_fdr_number") or data.get("fdr_number") or data.get("newFdrNumber") or (fdr_req.fdr.fdr_number if fdr_req.fdr else "")).strip()
        issue_d_str = data.get("new_issue_date") or data.get("issue_date") or data.get("newIssueDate")
        mat_d_str = data.get("new_maturity_date") or data.get("maturity_date") or data.get("newMaturityDate")
        amount_raw = data.get("new_amount") or data.get("amount") or data.get("newAmount")
        remarks = str(data.get("remarks") or "").strip()
    else:
        return jsonify({"error": "Request body must be JSON or multipart/form-data.", "code": "INVALID_CONTENT_TYPE"}), 400

    if not new_fdr_num:
        return jsonify({"error": "Renewed FDR number is required.", "code": "MISSING_FDR_NUMBER"}), 400

    if not issue_d_str:
        return jsonify({"error": "Renewed issue date is required.", "code": "MISSING_ISSUE_DATE"}), 400

    if not mat_d_str:
        return jsonify({"error": "Renewed maturity date is required.", "code": "MISSING_MATURITY_DATE"}), 400

    try:
        new_issue_d = date.fromisoformat(str(issue_d_str)[:10])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid issue date format. Use YYYY-MM-DD.", "code": "INVALID_ISSUE_DATE"}), 400

    try:
        new_mat_d = date.fromisoformat(str(mat_d_str)[:10])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid maturity date format. Use YYYY-MM-DD.", "code": "INVALID_MATURITY_DATE"}), 400

    if new_mat_d <= new_issue_d:
        return jsonify({"error": "Maturity date must be later than the issue date.", "code": "INVALID_MATURITY_DATE"}), 400

    # Validate deposit amount
    if amount_raw is not None and str(amount_raw).strip() != "":
        try:
            new_amt_dec = Decimal(str(amount_raw))
            if new_amt_dec <= Decimal("0"):
                return jsonify({"error": "FDR deposit amount must be greater than zero.", "code": "INVALID_AMOUNT"}), 400
        except Exception:
            return jsonify({"error": "Invalid numeric value for deposit amount.", "code": "INVALID_AMOUNT"}), 400
    else:
        new_amt_dec = fdr_req.fdr.amount if fdr_req.fdr else Decimal("0")

    # Handle file upload with strict validation and honest synthetic receipt detection
    doc_name = fdr_req.renewal_document
    doc_size = fdr_req.renewal_document_size
    is_synthetic = False
    ocr_result = None

    if uploaded_file and uploaded_file.filename:
        from app.services.document_service import validate_uploaded_file
        from app.services.ocr_service import extract_text_from_document
        from app.services.synthetic_receipt_service import detect_synthetic_markers

        # Strict validation: Extension (.pdf, .png, .jpg), max size, magic bytes signature (%PDF-)
        max_bytes = current_app.config.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
        clean_name, mime_type, file_bytes = validate_uploaded_file(uploaded_file, max_bytes=max_bytes)

        filename = secure_filename(clean_name) or "renewal_receipt.pdf"
        doc_name = f"renewal_{fdr_req.id}_{filename}"
        doc_size = len(file_bytes)

        upload_dir = current_app.config.get("REQUEST_UPLOAD_FOLDER") or (
            current_app.config["UPLOAD_FOLDER"] / "requests"
        )
        os.makedirs(upload_dir, exist_ok=True)
        stored_path = Path(upload_dir) / doc_name
        with open(stored_path, "wb") as f_out:
            f_out.write(file_bytes)

        # Honest document analysis: detect whether document contains synthetic watermark
        try:
            raw_text, ocr_status, note = extract_text_from_document(
                stored_path, mime_type, max_pages=current_app.config.get("MAX_PDF_PAGES", 10)
            )
            detected, matched_marker = detect_synthetic_markers(raw_text)
            if detected:
                is_synthetic = True
                ocr_result = {
                    "is_synthetic": True,
                    "matched_marker": matched_marker,
                    "status": "SYNTHETIC_DEMO_DETECTED",
                    "classification": "SYNTHETIC_DEMO_RECEIPT",
                    "disclaimer": (
                        "SYNTHETIC DEMO DOCUMENT DETECTED: Marked as 'SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK'. "
                        "All parameters are fictional and require verification. This is NOT an official bank receipt."
                    ),
                    "note": note,
                }
            else:
                ocr_result = {
                    "is_synthetic": False,
                    "status": ocr_status,
                    "classification": "GENUINE_SUBMISSION_FOR_SCRUTINY",
                    "disclaimer": "Standard receipt submission awaiting officer verification.",
                    "note": note,
                }
        except Exception as ocr_err:
            current_app.logger.warning(f"Error analyzing renewal receipt REQ-{fdr_req.id:04d}: {ocr_err}")
            ocr_result = {
                "is_synthetic": False,
                "status": "FAILED",
                "disclaimer": "OCR extraction failed. Requires manual visual scrutiny.",
            }

    # Persist pending renewal details on the request
    fdr_req.renewal_fdr_number = new_fdr_num
    fdr_req.renewal_issue_date = new_issue_d
    fdr_req.renewal_maturity_date = new_mat_d
    fdr_req.renewal_amount = new_amt_dec
    if doc_name:
        fdr_req.renewal_document = doc_name
        fdr_req.renewal_document_size = doc_size
    fdr_req.renewal_remarks = remarks
    fdr_req.renewal_is_synthetic = is_synthetic
    if ocr_result:
        import json as _json
        fdr_req.renewal_ocr_data = _json.dumps(ocr_result)
    fdr_req.renewal_submitted_at = datetime.now(timezone.utc)
    fdr_req.status = "Pending Verification"
    fdr_req.stage = VALID_REQUEST_STATUSES["Pending Verification"]

    # Transition FDR validity status to RENEWAL_PENDING_VERIFICATION (original maturity date preserved)
    if fdr_req.fdr:
        fdr_req.fdr.validity_status = ValidityStatus.RENEWAL_PENDING_VERIFICATION.value

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="FDR_RENEWAL_RECEIPT_SUBMITTED",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=(
            f"Institution submitted renewed receipt for FDR {fdr_req.fdr.fdr_number if fdr_req.fdr else ''} "
            f"(REQ-{fdr_req.id:04d}). New FDR #: {new_fdr_num}, Proposed maturity: {new_mat_d.isoformat()}."
            + (" [SYNTHETIC DEMO DOCUMENT DETECTED]" if is_synthetic else "")
        ),
    )
    db.session.add(audit)

    # Notify officer if assigned, or general notification
    if fdr_req.assigned_to:
        notif = Notification(
            user_id=fdr_req.assigned_to,
            title=f"Renewed FDR Receipt Uploaded (REQ-{fdr_req.id:04d})",
            message=f"Institution has uploaded renewed FDR receipt for {fdr_req.fdr.fdr_number if fdr_req.fdr else 'FDR'}. Please verify and endorse.",
            notification_type=NotificationType.ACTION_REQUIRED.value,
            is_read=False,
        )
        db.session.add(notif)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Renewed FDR receipt and details submitted successfully. Awaiting AICTE officer verification.",
        "data": fdr_req.to_dict(),
    }), 200


@requests_bp.route("/<request_id>/verify-renewal", methods=["POST"])
@roles_required(UserRole.AICTE_OFFICER, UserRole.ADMIN)
def verify_renewal(request_id):
    """AICTE Officer verifies and endorses the renewed FDR receipt and updates the FDR record."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    if fdr_req.request_type != "Renewal":
        return jsonify({"error": "Only renewal petitions can be verified under this endpoint.", "code": "INVALID_REQUEST_TYPE"}), 400

    if not fdr_req.renewal_maturity_date or not fdr_req.renewal_issue_date:
        return jsonify({"error": "No renewed FDR details have been submitted for verification.", "code": "NO_RENEWAL_SUBMISSION"}), 400

    if fdr_req.status not in ("Pending Verification", "Approved", "Under Review"):
        return jsonify({
            "error": f"Petition is not in a verifiable state (current status: {fdr_req.status}).",
            "code": "INVALID_STATE",
        }), 400

    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "VERIFIED")).strip().upper()
    remarks = str(data.get("remarks") or "").strip()
    is_simulated = bool(data.get("is_simulated") or data.get("isSimulated"))

    from app.services.synthetic_receipt_service import is_demo_environment

    # Prevent simulated verification or synthetic receipt verification in production
    if is_simulated or fdr_req.renewal_is_synthetic:
        if not is_demo_environment():
            return jsonify({
                "error": "Simulated verification and synthetic demo receipts are strictly prohibited in production.",
                "code": "SIMULATION_DISABLED_IN_PROD",
            }), 403

        is_simulated = True
        sim_note = " [SIMULATED DEMO VERIFICATION: Endorsed in local development/demo mode using synthetic receipt. No bank issued this receipt.]"
        if sim_note not in remarks:
            remarks = (remarks + sim_note).strip()

    valid_decisions = {"VERIFIED", "RETURNED", "REJECTED"}
    if decision not in valid_decisions:
        return jsonify({"error": f"Invalid decision '{decision}'. Must be one of: {sorted(list(valid_decisions))}", "code": "INVALID_DECISION"}), 400

    if decision in ("RETURNED", "REJECTED") and not remarks:
        return jsonify({"error": f"Official remarks are mandatory when decision is '{decision}'.", "code": "REMARKS_REQUIRED"}), 400

    fdr = fdr_req.fdr
    if not fdr:
        return jsonify({"error": "Linked FDR record not found.", "code": "FDR_NOT_FOUND"}), 404

    if decision == "VERIFIED":
        # 1. Preserve previous state in immutable FDRRenewalHistory
        history = FDRRenewalHistory(
            fdr_id=fdr.id,
            request_id=fdr_req.id,
            previous_fdr_number=fdr.fdr_number,
            previous_issue_date=fdr.issue_date,
            previous_maturity_date=fdr.maturity_date,
            previous_amount=fdr.amount,
            new_fdr_number=fdr_req.renewal_fdr_number or fdr.fdr_number,
            new_issue_date=fdr_req.renewal_issue_date,
            new_maturity_date=fdr_req.renewal_maturity_date,
            new_amount=fdr_req.renewal_amount or fdr.amount,
            renewal_document=fdr_req.renewal_document,
            verified_by=g.current_user.id,
            remarks=remarks or "Renewed FDR receipt and terms verified against AICTE guidelines.",
        )
        db.session.add(history)

        # 2. Update existing FDR record with the verified renewed details
        fdr.fdr_number = fdr_req.renewal_fdr_number or fdr.fdr_number
        fdr.issue_date = fdr_req.renewal_issue_date
        fdr.maturity_date = fdr_req.renewal_maturity_date
        fdr.amount = fdr_req.renewal_amount or fdr.amount
        fdr.validity_status = classify_validity_status(fdr.maturity_date, as_of_date=get_business_date()).value
        fdr.updated_at = datetime.now(timezone.utc)

        # 3. Create a Document record under FDR if receipt exists
        if fdr_req.renewal_document:
            existing_doc = Document.query.filter_by(
                fdr_id=fdr.id,
                stored_filename=fdr_req.renewal_document,
            ).first()
            if not existing_doc:
                doc = Document(
                    fdr_id=fdr.id,
                    stored_filename=fdr_req.renewal_document,
                    original_filename=fdr_req.renewal_document,
                    file_size=max(1, fdr_req.renewal_document_size or 1024),
                    file_type="application/pdf",
                    processing_status=DocumentProcessingStatus.PROCESSED.value,
                    uploaded_by=g.current_user.id,
                )
                db.session.add(doc)

        # 4. Finalize the request
        fdr_req.status = "Closed"
        fdr_req.stage = "Renewal Verified & Closed"
        fdr_req.renewal_verified_at = datetime.now(timezone.utc)
        fdr_req.renewal_verified_by = g.current_user.id
        if remarks:
            fdr_req.remarks = remarks

        # 5. Audit Log
        audit = AuditLog(
            user_id=g.current_user.id,
            action="FDR_RENEWAL_VERIFIED_SIMULATED" if is_simulated else "FDR_RENEWAL_VERIFIED",
            entity_type="FDRRecord",
            entity_id=fdr.id,
            details=(
                f"Officer {g.current_user.full_name} verified renewal {'(SIMULATED DEMO)' if is_simulated else ''} "
                f"for FDR {fdr.fdr_number} (REQ-{fdr_req.id:04d}). "
                f"Previous maturity: {history.previous_maturity_date}, New maturity: {fdr.maturity_date}."
            ),
        )
        db.session.add(audit)

        # 6. Notification to institution
        notif = Notification(
            user_id=fdr_req.created_by,
            title=f"Renewal Verified (FDR {fdr.fdr_number}) {'[Simulated]' if is_simulated else ''}".strip(),
            message=(
                f"AICTE has recorded verified renewal for FDR {fdr.fdr_number} (Simulated Demo Mode). "
                f"The deposit maturity has been officially extended to {fdr.maturity_date.isoformat()} in the test database."
                if is_simulated else
                f"AICTE has verified and endorsed your renewed FDR receipt. The deposit maturity has been officially extended to {fdr.maturity_date.isoformat()}."
            ),
            notification_type=NotificationType.INFO.value,
            is_read=False,
        )
        db.session.add(notif)

    elif decision == "RETURNED":
        fdr_req.status = "Documents Required"
        fdr_req.stage = "Renewed Receipt Deficient — Re-upload Required"
        fdr_req.remarks = remarks

        # Reset FDR validity status based on original maturity date
        fdr.validity_status = classify_validity_status(fdr.maturity_date, as_of_date=get_business_date()).value

        audit = AuditLog(
            user_id=g.current_user.id,
            action="FDR_RENEWAL_RECEIPT_RETURNED",
            entity_type="FDRRequest",
            entity_id=fdr_req.id,
            details=f"Officer {g.current_user.full_name} returned renewal receipt for REQ-{fdr_req.id:04d}. Remarks: {remarks}",
        )
        db.session.add(audit)

        notif = Notification(
            user_id=fdr_req.created_by,
            title=f"Renewed Receipt Needs Correction (REQ-{fdr_req.id:04d})",
            message=f"Deficiencies found in renewed FDR receipt for {fdr.fdr_number}: {remarks}. Please re-upload corrected receipt.",
            notification_type=NotificationType.ACTION_REQUIRED.value,
            is_read=False,
        )
        db.session.add(notif)

    elif decision == "REJECTED":
        fdr_req.status = "Rejected"
        fdr_req.stage = "Renewal Rejected & Closed"
        fdr_req.remarks = remarks

        fdr.validity_status = classify_validity_status(fdr.maturity_date, as_of_date=get_business_date()).value

        audit = AuditLog(
            user_id=g.current_user.id,
            action="FDR_RENEWAL_REJECTED",
            entity_type="FDRRequest",
            entity_id=fdr_req.id,
            details=f"Officer {g.current_user.full_name} rejected renewal for REQ-{fdr_req.id:04d}. Remarks: {remarks}",
        )
        db.session.add(audit)

        notif = Notification(
            user_id=fdr_req.created_by,
            title=f"Renewal Request Rejected (REQ-{fdr_req.id:04d})",
            message=f"AICTE has rejected the renewal request for FDR {fdr.fdr_number}. Remarks: {remarks}",
            notification_type=NotificationType.ALERT.value,
            is_read=False,
        )
        db.session.add(notif)

    db.session.commit()

    # Post-commit statutory email notification (strictly non-blocking on failure)
    try:
        from app.services.email_service import (
            send_receipt_verification_email,
            send_renewal_completed_email,
        )
        send_receipt_verification_email(fdr_req, decision, remarks=remarks)
        if decision == "VERIFIED":
            send_renewal_completed_email(
                fdr_request=fdr_req,
                fdr=fdr,
                old_mat_date=history.previous_maturity_date if "history" in locals() else None,
                new_mat_date=fdr.maturity_date,
            )
    except Exception as email_err:
        current_app.logger.error(
            f"Non-fatal error delivering renewal verification email for REQ-{fdr_req.id:04d}: {email_err}"
        )

    return jsonify({
        "success": True,
        "message": f"Renewal decision '{decision}' recorded successfully.",
        "data": {
            "request": fdr_req.to_dict(),
            "fdr": fdr.to_dict(),
        },
        "request": fdr_req.to_dict(),
        "fdr": fdr.to_dict(),
    }), 200


@requests_bp.route("/<request_id>/assign", methods=["PATCH"])
@roles_required(UserRole.ADMIN, UserRole.AICTE_OFFICER)
def assign_request(request_id):
    """Assign or reassign a petition to an authorized AICTE scrutiny officer."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    if not request.is_json:
        return jsonify({"error": "Request body must be valid JSON.", "code": "INVALID_JSON"}), 400

    data = request.get_json(silent=True) or {}
    officer_id = data.get("officer_id") or data.get("assigned_to")

    if officer_id is not None:
        try:
            officer_id = int(officer_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Field 'officer_id' must be an integer.", "code": "INVALID_OFFICER_ID"}), 400

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    target_officer = None
    if officer_id:
        target_officer = db.session.get(User, officer_id)
        if not target_officer:
            return jsonify({"error": f"Officer with ID {officer_id} not found.", "code": "OFFICER_NOT_FOUND"}), 404

        officer_cat = UserRole.normalize_category(target_officer.role)
        if officer_cat not in ("AICTE_OFFICER", "ADMIN"):
            return (
                jsonify(
                    {
                        "error": "Assigned user must have AICTE_OFFICER or ADMIN role.",
                        "code": "INVALID_OFFICER_ROLE",
                    }
                ),
                400,
            )

    old_assignee_id = fdr_req.assigned_to
    fdr_req.assigned_to = officer_id

    # Audit log assignment
    audit = AuditLog(
        user_id=g.current_user.id,
        action="REQUEST_ASSIGNED",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=(
            f"Petition REQ-{fdr_req.id:04d} assigned to "
            f"{target_officer.full_name if target_officer else 'Unassigned'} "
            f"(Previous: ID {old_assignee_id})."
        ),
    )
    db.session.add(audit)

    # Notify newly assigned officer
    if target_officer:
        notif = Notification(
            user_id=target_officer.id,
            title=f"Petition Assigned (REQ-{fdr_req.id:04d})",
            message=f"You have been assigned to review {fdr_req.request_type} petition REQ-{fdr_req.id:04d} from {fdr_req.institution.name if fdr_req.institution else 'Institution'}.",
            notification_type=NotificationType.INFO.value,
            is_read=False,
        )
        db.session.add(notif)

    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": f"Petition assigned successfully to {target_officer.full_name if target_officer else 'Unassigned'}.",
                "data": fdr_req.to_dict(),
            }
        ),
        200,
    )


@requests_bp.route("/<request_id>/claim", methods=["PATCH"])
@roles_required(UserRole.ADMIN, UserRole.AICTE_OFFICER)
def claim_request(request_id):
    """Allow an authorized officer or admin to self-assign / claim an unassigned petition."""
    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    if fdr_req.assigned_to and fdr_req.assigned_to != g.current_user.id:
        return (
            jsonify(
                {
                    "error": f"Petition is already assigned to {fdr_req.assigned_officer.full_name if fdr_req.assigned_officer else 'another officer'}.",
                    "code": "ALREADY_ASSIGNED",
                }
            ),
            409,
        )

    fdr_req.assigned_to = g.current_user.id

    audit = AuditLog(
        user_id=g.current_user.id,
        action="REQUEST_CLAIMED",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=f"Petition REQ-{fdr_req.id:04d} claimed by {g.current_user.full_name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": f"Petition REQ-{fdr_req.id:04d} claimed successfully.",
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

    # Parse numeric request ID (supports e.g. 3 or "REQ-0003")
    numeric_id = parse_request_id(request_id)

    if not numeric_id:
        return jsonify({"error": "Invalid request ID format.", "code": "INVALID_ID"}), 400

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    # Multi-tenant authorization check
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    if user_category == "INSTITUTION":
        if not user.institution_id or fdr_req.institution_id != user.institution_id:
            return jsonify({"error": "Petition request not found or inaccessible.", "code": "NOT_FOUND"}), 404

    # Check if request has an attachment filename (supporting document or renewal receipt)
    is_renewal_req = request.args.get("renewal") or request.args.get("doc_type") == "renewal"
    target_doc = fdr_req.renewal_document if is_renewal_req else fdr_req.supporting_document
    if not target_doc:
        target_doc = fdr_req.supporting_document or fdr_req.renewal_document

    if not target_doc:
        return jsonify({"error": "No supporting document is attached to this petition.", "code": "ATTACHMENT_NOT_FOUND"}), 404

    doc_name = target_doc.strip()

    req_upload_dir = current_app.config.get("REQUEST_UPLOAD_FOLDER") or (
        current_app.config["UPLOAD_FOLDER"] / "requests"
    )
    fdr_upload_dir = current_app.config["UPLOAD_FOLDER"]

    candidate_paths = [
        (Path(req_upload_dir) / doc_name).resolve(),
        (Path(req_upload_dir) / f"req_{fdr_req.id}_{doc_name}").resolve(),
        (Path(req_upload_dir) / f"renewal_{fdr_req.id}_{doc_name}").resolve(),
        (Path(fdr_upload_dir) / doc_name).resolve(),
        (Path(fdr_upload_dir) / f"req_{fdr_req.id}_{doc_name}").resolve(),
    ]

    stored_name = getattr(fdr_req, "stored_filename", None)
    if stored_name:
        candidate_paths.insert(0, (Path(req_upload_dir) / stored_name).resolve())
        candidate_paths.insert(1, (Path(fdr_upload_dir) / stored_name).resolve())

    if fdr_req.fdr and fdr_req.fdr.documents:
        for fdr_doc in fdr_req.fdr.documents:
            if fdr_doc.stored_filename:
                candidate_paths.append((Path(fdr_upload_dir) / fdr_doc.stored_filename).resolve())

    file_path = None
    for p in candidate_paths:
        try:
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
            jsonify({"error": f"Supporting document file '{doc_name}' not found on storage disk.", "code": "FILE_NOT_FOUND"}),
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


@requests_bp.route("/<request_id>/demo-renewal-receipt", methods=["GET"])
@login_required
def download_request_demo_renewal_receipt(request_id):
    """
    Download a synthetic PDF renewal receipt for this petition in demo mode.
    Strictly forbidden in production environments.
    """
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

    numeric_id = parse_request_id(request_id)
    if not numeric_id:
        return jsonify({"error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    fdr_req = db.session.get(FDRRequest, numeric_id)
    if not fdr_req or not fdr_req.fdr:
        return jsonify({"error": "Petition request or linked FDR not found.", "code": "NOT_FOUND"}), 404

    # Multi-tenant scoping
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)
    if user_category == "INSTITUTION":
        if not user.institution_id or fdr_req.institution_id != user.institution_id:
            return jsonify({"error": "Petition request not found or inaccessible.", "code": "NOT_FOUND"}), 404

    pdf_bytes = generate_synthetic_renewal_receipt(
        fdr=fdr_req.fdr,
        new_maturity_date=fdr_req.renewal_maturity_date,
        proposed_amount=fdr_req.renewal_amount,
        new_fdr_number=fdr_req.renewal_fdr_number,
    )

    clean_num = "".join(c for c in fdr_req.fdr.fdr_number if c.isalnum() or c in "-_") or "fdr"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"DEMO_Renewal_Receipt_REQ{fdr_req.id:04d}_{clean_num}.pdf",
    )

