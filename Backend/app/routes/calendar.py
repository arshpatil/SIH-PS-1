"""Calendar routes providing unified, role-authorized event feeds for FDR maturities and petition workflows."""

from flask import Blueprint, g, jsonify, request

from app.models.enums import UserRole
from app.security import login_required
from app.services.calendar_service import get_calendar_events

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")


@calendar_bp.route("/events", methods=["GET"])
@login_required
def get_events():
    """
    Retrieve unified calendar events for authorized users:
    - Institutions see only their own FDRs, petitions, and renewal stages.
    - Officers see assigned and claimable petitions, plus operational FDR maturities.
    - Admins see system-wide events and may filter by institution_id.
    """
    user = g.current_user

    start = request.args.get("start")
    end = request.args.get("end")
    event_type = request.args.get("event_type")
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")

    # Only ADMIN or AICTE_OFFICER can supply institution_id filter
    institution_id_filter = None
    if user.role in (UserRole.ADMIN.value, UserRole.AICTE_OFFICER.value):
        raw_inst_id = request.args.get("institution_id")
        if raw_inst_id and raw_inst_id.isdigit():
            institution_id_filter = int(raw_inst_id)

    events = get_calendar_events(
        user=user,
        start_str=start,
        end_str=end,
        event_type=event_type,
        status_filter=status_filter,
        priority_filter=priority_filter,
        institution_id_filter=institution_id_filter,
    )

    return jsonify({
        "events": events,
        "count": len(events),
        "date_range": {
            "start": start,
            "end": end,
        },
    }), 200
