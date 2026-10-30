from datetime import datetime, timezone, timedelta
from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User
from app.security import login_required, roles_required
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


@dashboard_bp.route("/workload", methods=["GET"])
@login_required
def get_workload():
    """Officer workload, escalation queue, and pending review metrics for AICTE officers/admins."""
    user = g.current_user
    user_cat = UserRole.normalize_category(user.role)
    if user_cat not in ("AICTE_OFFICER", "ADMIN"):
        return jsonify({"success": False, "error": "Only officers and admins can access bureau workload.", "code": "FORBIDDEN"}), 403

    from datetime import datetime, timezone, timedelta
    from app.models.fdr_request import FDRRequest
    from app.models.fdr import FDRRecord
    from app.models.user import User

    # 1. Pending petitions
    active_statuses = ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]
    pending_petitions_count = FDRRequest.query.filter(FDRRequest.status.in_(active_statuses)).count()

    # 2. Overdue petitions (> 14 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    overdue_petitions = (
        FDRRequest.query.filter(FDRRequest.status.in_(active_statuses), FDRRequest.created_at <= cutoff)
        .order_by(FDRRequest.created_at.asc())
        .all()
    )

    # 3. Pending FDR scrutiny
    pending_fdrs_count = FDRRecord.query.filter(
        FDRRecord.scrutiny_status.in_(["SUBMITTED", "PENDING_VERIFICATION"])
    ).count()

    # 4. Workload by officer
    officers = User.query.filter(
        User.role.in_([UserRole.AICTE_OFFICER.value, UserRole.ADMIN.value]),
        User.is_active == True,
    ).all()

    officer_workloads = []
    for off in officers:
        assigned_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(active_statuses),
        ).count()
        resolved_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(["Approved", "Rejected", "Closed"]),
        ).count()
        officer_workloads.append({
            "officer_id": off.id,
            "officer_name": off.full_name,
            "officer_email": off.email,
            "active_assigned_cases": assigned_count,
            "resolved_cases": resolved_count,
        })

    return jsonify({
        "success": True,
        "data": {
            "pending_petitions": pending_petitions_count,
            "overdue_petitions_count": len(overdue_petitions),
            "pending_fdrs_scrutiny": pending_fdrs_count,
            "overdue_petitions": [p.to_dict() for p in overdue_petitions[:10]],
            "officers_workload": officer_workloads,
        }
    }), 200


@dashboard_bp.route("/admin", methods=["GET"])
@roles_required(UserRole.ADMIN)
def get_admin_dashboard():
    """System-wide operational metrics, officer workloads, unassigned queue, and recent audit events for Admin."""
    active_statuses = ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]
    now_utc = datetime.now(timezone.utc)
    cutoff_overdue = now_utc - timedelta(days=14)
    cutoff_maturing = (now_utc + timedelta(days=30)).date()

    total_institutions = Institution.query.count()
    total_active_fdrs = FDRRecord.query.filter(
        FDRRecord.scrutiny_status.in_(["VERIFIED", "SUBMITTED", "PENDING_VERIFICATION"])
    ).count()
    total_petitions = FDRRequest.query.count()

    unassigned_query = FDRRequest.query.filter(
        FDRRequest.assigned_to.is_(None),
        FDRRequest.status.in_(active_statuses),
    ).order_by(FDRRequest.created_at.asc())
    unassigned_count = unassigned_query.count()
    unassigned_petitions = [p.to_dict() for p in unassigned_query.all()]

    # Petitions by status
    petitions_by_status = {}
    for st in ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review", "Approved", "Rejected", "Closed"]:
        petitions_by_status[st] = FDRRequest.query.filter(FDRRequest.status == st).count()

    # Active officers
    officers = User.query.filter(
        User.role.in_([UserRole.AICTE_OFFICER.value, UserRole.ADMIN.value]),
    ).order_by(User.full_name.asc()).all()
    active_officers_count = sum(1 for o in officers if o.is_active)

    officer_workloads = []
    for off in officers:
        assigned_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(active_statuses),
        ).count()
        resolved_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(["Approved", "Rejected", "Closed"]),
        ).count()
        overdue_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(active_statuses),
            FDRRequest.created_at <= cutoff_overdue,
        ).count()
        officer_workloads.append({
            "officer_id": off.id,
            "officer_name": off.full_name,
            "officer_email": off.email,
            "is_active": off.is_active,
            "role": off.role,
            "active_assigned_cases": assigned_count,
            "resolved_cases": resolved_count,
            "overdue_cases": overdue_count,
        })

    # Overdue cases count across the system
    overdue_cases_count = FDRRequest.query.filter(
        FDRRequest.status.in_(active_statuses),
        FDRRequest.created_at <= cutoff_overdue,
    ).count()

    # Upcoming maturities (<= 30 days)
    upcoming_maturities_count = FDRRecord.query.filter(
        FDRRecord.maturity_date.isnot(None),
        FDRRecord.maturity_date <= cutoff_maturing,
        FDRRecord.maturity_date >= now_utc.date(),
    ).count()

    # Recent audit events
    recent_audits = (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(15).all()
    )
    audit_list = [
        {
            "id": a.id,
            "action": a.action,
            "actor_id": a.user_id,
            "actor_name": a.user.full_name if a.user else "System",
            "actor_role": a.user.role if a.user else None,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "details": a.details,
            "timestamp": a.created_at.isoformat() if a.created_at else None,
        }
        for a in recent_audits
    ]

    return jsonify({
        "success": True,
        "data": {
            "metrics": {
                "total_institutions": total_institutions,
                "total_active_fdrs": total_active_fdrs,
                "total_petitions": total_petitions,
                "unassigned_petitions_count": unassigned_count,
                "petitions_by_status": petitions_by_status,
                "active_officers_count": active_officers_count,
                "overdue_cases_count": overdue_cases_count,
                "upcoming_maturities_count": upcoming_maturities_count,
            },
            "unassigned_queue": unassigned_petitions,
            "officer_workloads": officer_workloads,
            "recent_audit_events": audit_list,
        }
    }), 200


@dashboard_bp.route("/officer", methods=["GET"])
@roles_required(UserRole.AICTE_OFFICER, UserRole.ADMIN)
def get_officer_dashboard():
    """Personal scrutiny workload overview and assigned cases for scrutiny officers."""
    user = g.current_user
    active_statuses = ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]
    now_utc = datetime.now(timezone.utc)
    cutoff_overdue = now_utc - timedelta(days=14)
    cutoff_new = now_utc - timedelta(days=7)
    cutoff_maturing = (now_utc + timedelta(days=30)).date()

    # 1. Personal Workload Overview Counts
    assigned_query = FDRRequest.query.filter(FDRRequest.assigned_to == user.id)

    assigned_awaiting_review = assigned_query.filter(
        FDRRequest.status.in_(["Submitted", "Under Review"])
    ).count()

    newly_assigned = assigned_query.filter(
        FDRRequest.status.in_(active_statuses),
        FDRRequest.updated_at >= cutoff_new,
    ).count()

    awaiting_institution_corrections = assigned_query.filter(
        FDRRequest.status == "Documents Required"
    ).count()

    resubmitted_awaiting_review = assigned_query.filter(
        FDRRequest.status == "Resubmitted / Awaiting Review"
    ).count()

    approved_cases = assigned_query.filter(FDRRequest.status == "Approved").count()
    rejected_cases = assigned_query.filter(FDRRequest.status == "Rejected").count()

    overdue_cases = assigned_query.filter(
        FDRRequest.status.in_(active_statuses),
        FDRRequest.created_at <= cutoff_overdue,
    ).count()

    approaching_maturity = (
        assigned_query.join(FDRRecord)
        .filter(
            FDRRequest.status.in_(active_statuses),
            FDRRecord.maturity_date.isnot(None),
            FDRRecord.maturity_date <= cutoff_maturing,
            FDRRecord.maturity_date >= now_utc.date(),
        )
        .count()
    )

    documents_requiring_verification = assigned_query.filter(
        FDRRequest.status.in_(["Submitted", "Resubmitted / Awaiting Review"]),
        FDRRequest.supporting_document.isnot(None),
    ).count()

    # 2. My Assigned Cases list
    assigned_cases_raw = (
        assigned_query.order_by(FDRRequest.updated_at.desc(), FDRRequest.created_at.desc()).all()
    )
    assigned_cases = [c.to_dict() for c in assigned_cases_raw]
    priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    assigned_cases.sort(key=lambda x: priority_order.get(x.get("priority", "LOW"), 4))

    # 3. Unassigned / Claimable Petitions
    unassigned_raw = (
        FDRRequest.query.filter(
            FDRRequest.assigned_to.is_(None),
            FDRRequest.status.in_(active_statuses),
        )
        .order_by(FDRRequest.created_at.asc())
        .limit(20)
        .all()
    )
    claimable_cases = [c.to_dict() for c in unassigned_raw]

    return jsonify({
        "success": True,
        "data": {
            "workload_overview": {
                "assigned_awaiting_review": assigned_awaiting_review,
                "newly_assigned": newly_assigned,
                "documents_requiring_verification": documents_requiring_verification,
                "awaiting_institution_corrections": awaiting_institution_corrections,
                "resubmitted_awaiting_review": resubmitted_awaiting_review,
                "approved_cases": approved_cases,
                "rejected_cases": rejected_cases,
                "overdue_cases": overdue_cases,
                "approaching_maturity": approaching_maturity,
                "total_assigned": len(assigned_cases),
            },
            "assigned_cases": assigned_cases,
            "claimable_cases": claimable_cases,
        }
    }), 200


@dashboard_bp.route("/officers", methods=["GET"])
@roles_required(UserRole.ADMIN)
def get_admin_officers_list():
    """List officers with account status and current workload for Admin management."""
    active_statuses = ["Submitted", "Under Review", "Documents Required", "Resubmitted / Awaiting Review"]
    cutoff_overdue = datetime.now(timezone.utc) - timedelta(days=14)

    officers = User.query.filter(
        User.role.in_([UserRole.AICTE_OFFICER.value, UserRole.ADMIN.value]),
    ).order_by(User.full_name.asc()).all()

    result = []
    for off in officers:
        assigned_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(active_statuses),
        ).count()
        resolved_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(["Approved", "Rejected", "Closed"]),
        ).count()
        overdue_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(active_statuses),
            FDRRequest.created_at <= cutoff_overdue,
        ).count()
        result.append({
            "id": off.id,
            "full_name": off.full_name,
            "email": off.email,
            "role": off.role,
            "is_active": off.is_active,
            "created_at": off.created_at.isoformat() if off.created_at else None,
            "active_cases": assigned_count,
            "resolved_cases": resolved_count,
            "overdue_cases": overdue_count,
        })

    return jsonify({"success": True, "data": result}), 200


@dashboard_bp.route("/officers/<int:officer_id>/status", methods=["PATCH"])
@roles_required(UserRole.ADMIN)
def update_officer_status(officer_id):
    """Admin activation or deactivation of an officer account."""
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON.", "code": "INVALID_JSON"}), 400

    data = request.get_json(silent=True) or {}
    if "is_active" not in data:
        return jsonify({"error": "Field 'is_active' is required.", "code": "MISSING_FIELD"}), 400

    new_status = bool(data["is_active"])

    officer = db.session.get(User, officer_id)
    if not officer:
        return jsonify({"error": f"Officer with ID {officer_id} not found.", "code": "OFFICER_NOT_FOUND"}), 404

    # Do not allow deactivating the currently logged in admin user
    if officer.id == g.current_user.id and not new_status:
        return jsonify({"error": "Administrators cannot deactivate their own account.", "code": "CANNOT_DEACTIVATE_SELF"}), 400

    # Ensure target user is indeed an officer or admin
    officer_cat = UserRole.normalize_category(officer.role)
    if officer_cat not in ("AICTE_OFFICER", "ADMIN"):
        return jsonify({"error": "Target user is not an officer or administrator.", "code": "INVALID_USER_ROLE"}), 400

    officer.is_active = new_status

    audit = AuditLog(
        user_id=g.current_user.id,
        action="OFFICER_STATUS_UPDATED",
        entity_type="User",
        entity_id=officer.id,
        details=f"Officer account {officer.email} status set to {'Active' if new_status else 'Deactivated'} by admin {g.current_user.full_name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Officer account '{officer.full_name}' {'activated' if new_status else 'deactivated'} successfully.",
        "data": officer.to_dict(),
    }), 200
