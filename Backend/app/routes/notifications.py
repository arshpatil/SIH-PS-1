from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.notification import Notification
from app.security import login_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.route("", methods=["GET"])
@login_required
def list_notifications():
    """
    List notifications for the authenticated user with pagination and unread filtering.
    Never accepts client-supplied user IDs.
    """
    user = g.current_user

    # Parse pagination parameters safely
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20

    query = Notification.query.filter_by(user_id=user.id)

    # Optional unread-only filtering
    unread_only_param = request.args.get("unread_only", "").strip().lower()
    if unread_only_param in ("true", "1", "yes"):
        query = query.filter_by(is_read=False)

    # Order by newest first
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "success": True,
                "notifications": [notif.to_dict() for notif in paginated.items],
                "pagination": {
                    "page": paginated.page,
                    "per_page": paginated.per_page,
                    "total": paginated.total,
                    "pages": paginated.pages,
                    "has_next": paginated.has_next,
                    "has_prev": paginated.has_prev,
                },
            }
        ),
        200,
    )


@notifications_bp.route("/unread-count", methods=["GET"])
@login_required
def get_unread_count():
    """Return the total number of unread notifications for the current user."""
    user = g.current_user
    count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return jsonify({"success": True, "unread_count": count}), 200


@notifications_bp.route("/<int:notification_id>/read", methods=["PATCH"])
@login_required
def mark_notification_as_read(notification_id: int):
    """
    Mark a single notification owned by the current user as read.
    Returns 404 if not found or owned by a different user.
    """
    user = g.current_user
    notif = Notification.query.filter_by(id=notification_id, user_id=user.id).first()

    if not notif:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Notification not found.",
                    "code": "NOTIFICATION_NOT_FOUND",
                }
            ),
            404,
        )

    if not notif.is_read:
        notif.is_read = True
        db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": "Notification marked as read.",
                "notification": notif.to_dict(),
            }
        ),
        200,
    )


@notifications_bp.route("/read-all", methods=["PATCH", "POST"])
@notifications_bp.route("/mark-all-read", methods=["POST", "PATCH"])
@login_required
def mark_all_notifications_as_read():
    """
    Mark all unread notifications for the authenticated user as read.
    """
    user = g.current_user
    unread_notifs = Notification.query.filter_by(user_id=user.id, is_read=False).all()
    marked_count = len(unread_notifs)

    for notif in unread_notifs:
        notif.is_read = True

    if marked_count > 0:
        db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": f"Successfully marked {marked_count} notification(s) as read.",
                "marked_count": marked_count,
            }
        ),
        200,
    )


@notifications_bp.route("/email-logs", methods=["GET"])
@login_required
def list_email_logs():
    """
    Diagnostic endpoint to audit and inspect email notification delivery logs.
    Supports filtering by status (e.g. FAILED, SENT), email_type, FDR, and petition.
    Enforces multi-tenant isolation for institutions.
    """
    from app.models.email_log import EmailNotificationLog
    from app.models.enums import UserRole

    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    query = EmailNotificationLog.query

    # Multi-tenant isolation: institutions only inspect their own college's logs
    if user_category == "INSTITUTION":
        if not user.institution_id:
            return jsonify({"success": True, "logs": [], "pagination": {"page": 1, "per_page": 20, "total": 0, "pages": 0}}), 200
        query = query.filter_by(institution_id=user.institution_id)
    else:
        inst_id = request.args.get("institution_id")
        if inst_id:
            try:
                query = query.filter_by(institution_id=int(inst_id))
            except (ValueError, TypeError):
                pass

    # Optional filters
    status = request.args.get("status", "").strip().upper()
    if status in ("SENT", "FAILED", "SUPPRESSED"):
        query = query.filter_by(status=status)

    email_type = request.args.get("email_type", "").strip()
    if email_type:
        query = query.filter_by(email_type=email_type)

    fdr_id = request.args.get("fdr_id")
    if fdr_id:
        try:
            query = query.filter_by(fdr_id=int(fdr_id))
        except (ValueError, TypeError):
            pass

    request_id = request.args.get("request_id")
    if request_id:
        try:
            query = query.filter_by(request_id=int(request_id))
        except (ValueError, TypeError):
            pass

    # Count failed logs for diagnostic summary
    failed_count = query.session.query(EmailNotificationLog).filter_by(status="FAILED")
    if user_category == "INSTITUTION":
        failed_count = failed_count.filter_by(institution_id=user.institution_id)
    failed_count = failed_count.count()

    # Pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20

    query = query.order_by(EmailNotificationLog.created_at.desc(), EmailNotificationLog.id.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify(
            {
                "success": True,
                "logs": [log.to_dict() for log in paginated.items],
                "failed_count": failed_count,
                "pagination": {
                    "page": paginated.page,
                    "per_page": paginated.per_page,
                    "total": paginated.total,
                    "pages": paginated.pages,
                    "has_next": paginated.has_next,
                    "has_prev": paginated.has_prev,
                },
            }
        ),
        200,
    )


@notifications_bp.route("/email-logs/<int:log_id>/retry", methods=["POST"])
@login_required
def retry_email_log_endpoint(log_id: int):
    """
    Retry delivering a failed statutory email notification.
    Enforces multi-tenant isolation for institutions.
    """
    from app.models.email_log import EmailNotificationLog
    from app.models.enums import UserRole
    from app.services.email_service import retry_email_notification

    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    log_entry = db.session.get(EmailNotificationLog, log_id)
    if not log_entry:
        return jsonify({"success": False, "error": "Email log entry not found.", "code": "NOT_FOUND"}), 404

    # Multi-tenant isolation: institutions can only retry their own college logs
    if user_category == "INSTITUTION":
        if not user.institution_id or log_entry.institution_id != user.institution_id:
            return jsonify({"success": False, "error": "Access denied.", "code": "FORBIDDEN"}), 403

    success, message = retry_email_notification(log_id)
    return jsonify({
        "success": success,
        "message": message,
        "status": "SENT" if success else "FAILED",
    }), (200 if success else 400)

