from flask import Blueprint, g, jsonify, request

from app.models.enums import UserRole
from app.security import login_required
from app.services.dashboard_service import get_dashboard_statistics
from app.services.fdr_service import FDRValidationError

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.errorhandler(FDRValidationError)
def handle_dashboard_validation_error(ex: FDRValidationError):
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


@dashboard_bp.route("/stats", methods=["GET"])
@login_required
def get_stats():
    """
    Return comprehensive aggregate dashboard statistics including:
    - Total FDR records and monetary valuation
    - Status-wise counts (guaranteed zero for empty categories)
    - Validity/maturity counts evaluated against business date boundaries
    - Monthly trends and recent workflow transitions
    Strictly scoped to the calling user's institution or role boundaries.
    """
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    institution_id = None
    inst_param = request.args.get("institution_id")
    if inst_param is not None and str(inst_param).strip() != "":
        if user_category == "INSTITUTION":
            # Prevent client-side institution spoofing
            try:
                if int(inst_param) != user.institution_id:
                    raise FDRValidationError(
                        {"institution_id": "Institution users cannot access statistics of another institution."}
                    )
            except ValueError:
                raise FDRValidationError({"institution_id": "Institution ID must be an integer."})
            institution_id = user.institution_id
        else:
            try:
                institution_id = int(inst_param)
            except (ValueError, TypeError):
                raise FDRValidationError({"institution_id": "Institution ID must be an integer."})

    stats = get_dashboard_statistics(user, institution_id=institution_id)
    return jsonify({"success": True, "data": stats}), 200


@dashboard_bp.route("/charts", methods=["GET"])
@login_required
def get_charts():
    """
    Return formatted chart-ready distributions and time-series summaries:
    - workflow_distribution: percentages and counts by scrutiny status
    - validity_distribution: percentages and counts by validity/maturity status
    - monthly_trends: month-by-month submission volume and values
    - summary: high-level counts and totals
    """
    user = g.current_user
    user_category = UserRole.normalize_category(user.role)

    institution_id = None
    inst_param = request.args.get("institution_id")
    if inst_param is not None and str(inst_param).strip() != "":
        if user_category == "INSTITUTION":
            try:
                if int(inst_param) != user.institution_id:
                    raise FDRValidationError(
                        {"institution_id": "Institution users cannot access statistics of another institution."}
                    )
            except ValueError:
                raise FDRValidationError({"institution_id": "Institution ID must be an integer."})
            institution_id = user.institution_id
        else:
            try:
                institution_id = int(inst_param)
            except (ValueError, TypeError):
                raise FDRValidationError({"institution_id": "Institution ID must be an integer."})

    stats = get_dashboard_statistics(user, institution_id=institution_id)

    chart_payload = {
        "summary": {
            "total_fdrs": stats["total_fdrs"],
            "total_value": stats["total_value"],
            "total_value_formatted": stats["total_value_formatted"],
        },
        "workflow_distribution": stats["status_breakdown"],
        "validity_distribution": stats["validity_breakdown"],
        "monthly_trends": stats["monthly_trends"],
    }
    return jsonify({"success": True, "data": chart_payload}), 200
