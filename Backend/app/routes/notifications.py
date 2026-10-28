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
