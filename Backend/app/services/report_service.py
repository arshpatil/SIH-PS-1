import csv
from datetime import date, datetime, time, timezone
from decimal import Decimal
import io
from typing import Any

from sqlalchemy import func

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.user import User
from app.services.fdr_service import FDRValidationError, parse_strict_date

# Supported database columns for report sorting
REPORT_SORT_COLUMNS = {
    "id": FDRRecord.id,
    "fdr_number": FDRRecord.fdr_number,
    "amount": FDRRecord.amount,
    "issue_date": FDRRecord.issue_date,
    "maturity_date": FDRRecord.maturity_date,
    "scrutiny_status": FDRRecord.scrutiny_status,
    "validity_status": FDRRecord.validity_status,
    "created_at": FDRRecord.created_at,
    "bank_name": FDRRecord.bank_name,
}


def build_filtered_report_query(current_user: User, filters: dict):
    """
    Construct a database-side filtered and sorted SQLAlchemy query for FDR reports,
    enforcing RBAC, tenant isolation, and strict parameter validation.
    """
    query = FDRRecord.query
    user_category = UserRole.normalize_category(current_user.role)

    # 1. Enforce strict institution isolation
    if user_category == "INSTITUTION":
        if not current_user.institution_id:
            return query.filter(FDRRecord.id == -1)

        # Reject client attempt to spoof another institution's ID
        requested_inst_id = filters.get("institution_id")
        if requested_inst_id is not None and str(requested_inst_id).strip() != "":
            try:
                if int(requested_inst_id) != current_user.institution_id:
                    raise FDRValidationError(
                        {"institution_id": "Institution users cannot query or access records of another institution."}
                    )
            except ValueError:
                raise FDRValidationError({"institution_id": "Institution ID must be an integer."})

        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    else:
        # AICTE Officer / Admin cross-institution filtering
        requested_inst_id = filters.get("institution_id")
        if requested_inst_id is not None and str(requested_inst_id).strip() != "":
            try:
                query = query.filter(FDRRecord.institution_id == int(requested_inst_id))
            except (ValueError, TypeError):
                raise FDRValidationError({"institution_id": "Query param 'institution_id' must be an integer."})

    # 2. Filter by workflow / scrutiny status
    scrutiny_status = filters.get("scrutiny_status")
    if scrutiny_status:
        val = str(scrutiny_status).strip().upper()
        if val not in ScrutinyStatus.values():
            raise FDRValidationError(
                {"scrutiny_status": f"Invalid scrutiny status filter '{val}'. Allowed: {sorted(list(ScrutinyStatus.values()))}"}
            )
        query = query.filter(FDRRecord.scrutiny_status == val)

    # 3. Filter by validity / maturity status
    validity_status = filters.get("validity_status")
    if validity_status:
        val = str(validity_status).strip().upper()
        if val not in ValidityStatus.values():
            raise FDRValidationError(
                {"validity_status": f"Invalid validity status filter '{val}'. Allowed: {sorted(list(ValidityStatus.values()))}"}
            )
        query = query.filter(FDRRecord.validity_status == val)

    # 3b. Filter by maturity bracket if specified
    mat_bracket = filters.get("maturity_bracket") or filters.get("maturity_filter")
    if mat_bracket and str(mat_bracket).strip().upper() != "ALL":
        from datetime import timedelta
        from app.services.maturity_service import get_business_date
        ref_d = get_business_date()
        mb = str(mat_bracket).strip().upper()
        if mb in ("MATURING_90", "MATURING_90_DAYS", "90D"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=60), FDRRecord.maturity_date <= ref_d + timedelta(days=90))
        elif mb in ("MATURING_60", "MATURING_60_DAYS", "60D"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=30), FDRRecord.maturity_date <= ref_d + timedelta(days=60))
        elif mb in ("MATURING_30", "MATURING_30_DAYS", "MATURING_SOON", "30D"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=7), FDRRecord.maturity_date <= ref_d + timedelta(days=30))
        elif mb in ("MATURING_7", "MATURING_7_DAYS", "7D"):
            query = query.filter(FDRRecord.maturity_date >= ref_d, FDRRecord.maturity_date <= ref_d + timedelta(days=7))
        elif mb == "MATURED":
            query = query.filter(FDRRecord.maturity_date >= ref_d - timedelta(days=30), FDRRecord.maturity_date < ref_d)
        elif mb in ("OVERDUE", "OVERDUE_ACTION"):
            query = query.filter(FDRRecord.maturity_date < ref_d - timedelta(days=30))
        elif mb in ("ACTIVE", "FUTURE"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=90))

    # 4. Filter by maturity date range
    m_from_date = None
    m_to_date = None
    maturity_from = filters.get("maturity_from")
    if maturity_from:
        try:
            m_from_date = parse_strict_date(maturity_from, "maturity_from")
            query = query.filter(FDRRecord.maturity_date >= m_from_date)
        except ValueError as ex:
            raise FDRValidationError({"maturity_from": str(ex)})

    maturity_to = filters.get("maturity_to")
    if maturity_to:
        try:
            m_to_date = parse_strict_date(maturity_to, "maturity_to")
            query = query.filter(FDRRecord.maturity_date <= m_to_date)
        except ValueError as ex:
            raise FDRValidationError({"maturity_to": str(ex)})

    if m_from_date and m_to_date and m_from_date > m_to_date:
        raise FDRValidationError({"maturity_from": "maturity_from cannot be after maturity_to."})

    # 5. Filter by creation date range
    c_from_date = None
    c_to_date = None
    created_from = filters.get("created_from")
    if created_from:
        try:
            c_from_date = parse_strict_date(created_from, "created_from")
            start_dt = datetime.combine(c_from_date, time.min).replace(tzinfo=timezone.utc)
            query = query.filter(FDRRecord.created_at >= start_dt)
        except ValueError as ex:
            raise FDRValidationError({"created_from": str(ex)})

    created_to = filters.get("created_to")
    if created_to:
        try:
            c_to_date = parse_strict_date(created_to, "created_to")
            end_dt = datetime.combine(c_to_date, time.max).replace(tzinfo=timezone.utc)
            query = query.filter(FDRRecord.created_at <= end_dt)
        except ValueError as ex:
            raise FDRValidationError({"created_to": str(ex)})

    if c_from_date and c_to_date and c_from_date > c_to_date:
        raise FDRValidationError({"created_from": "created_from cannot be after created_to."})

    # 6. Filter by bank name (optional partial match)
    bank_name = filters.get("bank_name")
    if bank_name:
        query = query.filter(FDRRecord.bank_name.ilike(f"%{str(bank_name).strip()}%"))

    # 7. Sorting
    sort_by = filters.get("sort_by", "created_at")
    if sort_by not in REPORT_SORT_COLUMNS:
        raise FDRValidationError(
            {"sort_by": f"Invalid sort field '{sort_by}'. Allowed: {sorted(list(REPORT_SORT_COLUMNS.keys()))}"}
        )

    order = str(filters.get("order", "desc")).strip().lower()
    if order not in ("asc", "desc"):
        raise FDRValidationError({"order": "Sort order must be 'asc' or 'desc'."})

    sort_col = REPORT_SORT_COLUMNS[sort_by]
    if order == "asc":
        query = query.order_by(sort_col.asc(), FDRRecord.id.asc())
    else:
        query = query.order_by(sort_col.desc(), FDRRecord.id.desc())

    return query


def get_fdr_report(current_user: User, filters: dict) -> tuple[list[dict], dict, dict]:
    """
    Execute paginated report query with database-side filtering, sorting, and aggregate summary.
    """
    query = build_filtered_report_query(current_user, filters)

    # Validate pagination parameters
    try:
        page = int(filters.get("page", 1))
        if page < 1:
            raise ValueError()
    except (ValueError, TypeError):
        raise FDRValidationError({"page": "Page parameter must be a positive integer."})

    try:
        per_page = int(filters.get("per_page", 20))
        if per_page < 1 or per_page > 100:
            raise ValueError()
    except (ValueError, TypeError):
        raise FDRValidationError({"per_page": "Per-page parameter must be a positive integer between 1 and 100."})

    # Paginate using SQLAlchemy
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    # Compute overall filtered aggregates (clearing order_by for optimal SQL execution)
    unorder_q = query.order_by(None)
    total_records = unorder_q.count()
    sum_row = unorder_q.with_entities(func.coalesce(func.sum(FDRRecord.amount), Decimal("0"))).first()
    total_amount_dec = Decimal(str(sum_row[0])) if sum_row and sum_row[0] is not None else Decimal("0")

    records = [fdr.to_dict() for fdr in paginated.items]

    pagination = {
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "has_next": paginated.has_next,
        "has_prev": paginated.has_prev,
    }

    summary = {
        "total_records": total_records,
        "total_value": float(total_amount_dec),
        "total_value_formatted": f"{total_amount_dec:,.2f}",
    }

    return records, pagination, summary


def sanitize_csv_cell(value: Any) -> str:
    """
    Protect against CSV Formula Injection (CWE-1236).
    If a cell value starts with an unsafe formula character ('=', '+', '-', '@', tab, or carriage return),
    prefix with a single quote (') to force spreadsheet software to treat the content as raw text.
    """
    if value is None:
        return ""
    str_val = str(value)
    if str_val and str_val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + str_val
    return str_val


def export_fdr_csv(current_user: User, filters: dict, max_export_limit: int = 10000) -> tuple[str, str]:
    """
    Generate CSV export for authorized FDR records matching report filters,
    applying formula injection mitigation, standard formatting, and metadata headers.
    """
    query = build_filtered_report_query(current_user, filters)
    records = query.limit(max_export_limit).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Standard headers
    headers = [
        "FDR ID",
        "FDR Number",
        "Institution ID",
        "Institution Name",
        "Bank Name",
        "Branch Name",
        "Amount (INR)",
        "Issue Date",
        "Maturity Date",
        "Workflow Status",
        "Validity Status",
        "Created At (UTC)",
    ]
    writer.writerow(headers)

    for fdr in records:
        inst_name = fdr.institution.name if fdr.institution else ""
        row = [
            fdr.id,
            sanitize_csv_cell(fdr.fdr_number),
            fdr.institution_id,
            sanitize_csv_cell(inst_name),
            sanitize_csv_cell(fdr.bank_name),
            sanitize_csv_cell(fdr.branch_name),
            f"{fdr.amount:.2f}" if fdr.amount is not None else "0.00",
            fdr.issue_date.isoformat() if fdr.issue_date else "",
            fdr.maturity_date.isoformat() if fdr.maturity_date else "",
            fdr.scrutiny_status,
            fdr.validity_status,
            fdr.created_at.strftime("%Y-%m-%d %H:%M:%S") if fdr.created_at else "",
        ]
        writer.writerow(row)

    csv_content = output.getvalue()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"fdr_report_{timestamp_str}.csv"

    return csv_content, filename


def get_petition_report(current_user: User, filters: dict) -> tuple[list[dict], dict, dict]:
    """Retrieve filtered petitions with summary metrics and pagination."""
    from app.models.fdr_request import FDRRequest

    query = FDRRequest.query
    user_category = UserRole.normalize_category(current_user.role)

    if user_category == "INSTITUTION":
        if not current_user.institution_id:
            return [], {"total": 0, "page": 1, "per_page": 10, "pages": 0}, {}
        query = query.filter(FDRRequest.institution_id == current_user.institution_id)
    else:
        inst_id = filters.get("institution_id")
        if inst_id:
            try:
                query = query.filter(FDRRequest.institution_id == int(inst_id))
            except (ValueError, TypeError):
                pass

    status = filters.get("status")
    if status and status.upper() != "ALL":
        query = query.filter(FDRRequest.status.ilike(f"%{status.strip()}%"))

    req_type = filters.get("request_type") or filters.get("type")
    if req_type and req_type.upper() != "ALL":
        query = query.filter(FDRRequest.request_type.ilike(f"%{req_type.strip()}%"))

    assigned_to = filters.get("assigned_to")
    if assigned_to:
        try:
            query = query.filter(FDRRequest.assigned_to == int(assigned_to))
        except (ValueError, TypeError):
            pass

    total = query.count()
    query = query.order_by(FDRRequest.created_at.desc())

    try:
        page = max(1, int(filters.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(100, max(1, int(filters.get("per_page", 10))))
    except (ValueError, TypeError):
        per_page = 10

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    records = [r.to_dict() for r in paginated.items]

    pagination = {
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total": paginated.total,
        "pages": paginated.pages,
    }

    summary = {
        "total_petitions": total,
        "approved": query.filter(FDRRequest.status == "Approved").count(),
        "rejected": query.filter(FDRRequest.status == "Rejected").count(),
    }

    return records, pagination, summary


def export_petitions_csv(current_user: User, filters: dict) -> tuple[str, str]:
    """Export filtered petitions into CSV format with formula injection protection."""
    from app.models.fdr_request import FDRRequest

    query = FDRRequest.query
    user_category = UserRole.normalize_category(current_user.role)

    if user_category == "INSTITUTION":
        if not current_user.institution_id:
            query = query.filter(FDRRequest.id == -1)
        else:
            query = query.filter(FDRRequest.institution_id == current_user.institution_id)
    else:
        inst_id = filters.get("institution_id")
        if inst_id:
            try:
                query = query.filter(FDRRequest.institution_id == int(inst_id))
            except (ValueError, TypeError):
                pass

    status = filters.get("status")
    if status and status.upper() != "ALL":
        query = query.filter(FDRRequest.status.ilike(f"%{status.strip()}%"))

    req_type = filters.get("request_type") or filters.get("type")
    if req_type and req_type.upper() != "ALL":
        query = query.filter(FDRRequest.request_type.ilike(f"%{req_type.strip()}%"))

    records = query.order_by(FDRRequest.created_at.desc()).limit(10000).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    headers = [
        "Petition ID",
        "Institution ID",
        "Institution Name",
        "FDR Number",
        "Bank Name",
        "Request Type",
        "Status",
        "Stage",
        "Submission Date",
        "Assigned Officer",
        "Remarks",
    ]
    writer.writerow(headers)

    for req in records:
        inst_name = req.institution.name if req.institution else ""
        fdr_num = req.fdr.fdr_number if req.fdr else ""
        bank = req.fdr.bank_name if req.fdr else ""
        officer = req.assigned_officer.full_name if req.assigned_officer else "Unassigned"
        row = [
            f"REQ-{req.id:04d}",
            req.institution_id,
            sanitize_csv_cell(inst_name),
            sanitize_csv_cell(fdr_num),
            sanitize_csv_cell(bank),
            req.request_type,
            req.status,
            sanitize_csv_cell(req.stage),
            req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "",
            sanitize_csv_cell(officer),
            sanitize_csv_cell(req.remarks or ""),
        ]
        writer.writerow(row)

    csv_content = output.getvalue()
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return csv_content, f"petition_report_{timestamp_str}.csv"


def get_audit_report(current_user: User, filters: dict) -> tuple[list[dict], dict]:
    """Retrieve audit logs scoped to user authorization."""
    from app.models.audit import AuditLog

    query = AuditLog.query
    user_category = UserRole.normalize_category(current_user.role)

    if user_category == "INSTITUTION":
        if not current_user.institution_id:
            return [], {"total": 0, "page": 1, "per_page": 20, "pages": 0}
        query = query.filter(AuditLog.user_id == current_user.id)

    action = filters.get("action")
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))

    entity_type = filters.get("entity_type")
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.strip())

    try:
        page = max(1, int(filters.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(100, max(1, int(filters.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20

    query = query.order_by(AuditLog.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    records = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "user_name": a.user.full_name if a.user else "System",
            "user_email": a.user.email if a.user else None,
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "details": a.details,
            "timestamp": a.created_at.isoformat() if a.created_at else None,
        }
        for a in paginated.items
    ]

    pagination = {
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total": paginated.total,
        "pages": paginated.pages,
    }
    return records, pagination
