from flask import Blueprint, Response, g, jsonify, request

from app.security import login_required
from app.services.fdr_service import FDRValidationError
from app.services.report_service import export_fdr_csv, get_fdr_report, get_petition_report, export_petitions_csv, get_audit_report

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.errorhandler(FDRValidationError)
def handle_report_validation_error(ex: FDRValidationError):
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


@reports_bp.route("/fdr", methods=["GET"])
@login_required
def get_reports():
    """
    Paginated FDR report endpoint with comprehensive database-side filtering and sorting:
    - scrutiny_status: DRAFT, SUBMITTED, PENDING_VERIFICATION, VERIFIED, RETURNED, REJECTED
    - validity_status: ACTIVE, EXPIRING_SOON, MATURED, OVERDUE_ACTION
    - maturity_from / maturity_to: YYYY-MM-DD
    - created_from / created_to: YYYY-MM-DD
    - institution_id: filtered for officers/admins, strictly scoped for institution users
    - bank_name: case-insensitive partial match
    - sort_by: id, fdr_number, amount, issue_date, maturity_date, scrutiny_status, validity_status, created_at, bank_name
    - order: asc, desc
    - page: positive integer
    - per_page: integer 1-100
    """
    filters = request.args.to_dict()
    records, pagination, summary = get_fdr_report(g.current_user, filters)

    return (
        jsonify(
            {
                "success": True,
                "data": records,
                "pagination": pagination,
                "summary": summary,
            }
        ),
        200,
    )


@reports_bp.route("/fdr/export", methods=["GET"])
@login_required
def export_csv():
    """
    Download filtered FDR report as a CSV file.
    Reuses the exact same filters and authorization rules as the report endpoint.
    Applies formula injection mitigation and returns text/csv attachment.
    """
    filters = request.args.to_dict()
    csv_content, filename = export_fdr_csv(g.current_user, filters)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


@reports_bp.route("/petitions", methods=["GET"])
@login_required
def get_petitions_report_route():
    """Paginated petition report with filtering across statuses, types, and assignees."""
    filters = request.args.to_dict()
    records, pagination, summary = get_petition_report(g.current_user, filters)
    return jsonify({
        "success": True,
        "data": records,
        "pagination": pagination,
        "summary": summary,
    }), 200


@reports_bp.route("/petitions/export", methods=["GET"])
@login_required
def export_petitions_csv_route():
    """Download filtered petitions report as CSV file."""
    filters = request.args.to_dict()
    csv_content, filename = export_petitions_csv(g.current_user, filters)
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


@reports_bp.route("/audit", methods=["GET"])
@login_required
def get_audit_logs():
    """Searchable, tenant-scoped audit trail of system activities."""
    filters = request.args.to_dict()
    records, pagination = get_audit_report(g.current_user, filters)
    return jsonify({
        "success": True,
        "data": records,
        "pagination": pagination,
    }), 200
