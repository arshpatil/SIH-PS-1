from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import func

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.user import User
from app.models.workflow_history import FDRWorkflowHistory
from app.services.maturity_service import classify_validity_status, get_business_date


def get_authorized_fdr_query(current_user: User, institution_id: int | None = None):
    """
    Construct a base SQLAlchemy query for FDR records scoped to the user's role and tenant boundaries.
    """
    query = FDRRecord.query
    user_category = UserRole.normalize_category(current_user.role)

    if user_category == "INSTITUTION":
        # Strict tenant isolation: institution user can only ever access their own institution
        if not current_user.institution_id:
            return query.filter(FDRRecord.id == -1)
        return query.filter(FDRRecord.institution_id == current_user.institution_id)

    # For AICTE officers and admins, apply optional institution filter if supplied
    if institution_id is not None:
        return query.filter(FDRRecord.institution_id == institution_id)

    return query


def get_dashboard_statistics(current_user: User, institution_id: int | None = None) -> dict:
    """
    Compute aggregate dashboard metrics including total records, total monetary value,
    status breakdowns, maturity classifications, monthly submission trends, and recent activity.
    """
    base_query = get_authorized_fdr_query(current_user, institution_id=institution_id)

    # 1. Total FDR records
    total_fdrs = base_query.count()

    # 2. Total FDR monetary value
    sum_row = (
        base_query.with_entities(func.coalesce(func.sum(FDRRecord.amount), Decimal("0")))
        .first()
    )
    total_val_dec = Decimal(str(sum_row[0])) if sum_row and sum_row[0] is not None else Decimal("0")
    total_val_float = float(total_val_dec)
    total_val_formatted = f"{total_val_dec:,.2f}"

    # 3. Scrutiny status counts (guaranteeing all statuses present with >= 0)
    status_counts = {s.value: 0 for s in ScrutinyStatus}
    status_rows = (
        base_query.with_entities(FDRRecord.scrutiny_status, func.count(FDRRecord.id))
        .group_by(FDRRecord.scrutiny_status)
        .all()
    )
    for st, count in status_rows:
        if st in status_counts:
            status_counts[st] = count

    # 4. Validity/maturity status counts using established classification rules and business date
    validity_counts = {v.value: 0 for v in ValidityStatus}
    ref_date = get_business_date()

    # Fetch maturity dates and validity status to compute real-time classification accurately across boundaries
    fdr_rows = base_query.with_entities(FDRRecord.maturity_date, FDRRecord.validity_status).all()
    for row in fdr_rows:
        if row.validity_status == ValidityStatus.RENEWAL_PENDING_VERIFICATION.value:
            validity_counts[ValidityStatus.RENEWAL_PENDING_VERIFICATION.value] += 1
        elif row.maturity_date:
            val_enum = classify_validity_status(row.maturity_date, as_of_date=ref_date)
            validity_counts[val_enum.value] += 1
        else:
            validity_counts[ValidityStatus.ACTIVE.value] += 1

    # 5. Status-wise and validity-wise percentage breakdowns suitable for React charts
    status_breakdown = [
        {
            "status": status,
            "count": count,
            "percentage": round((count / total_fdrs * 100), 2) if total_fdrs > 0 else 0.0,
        }
        for status, count in status_counts.items()
    ]

    validity_breakdown = [
        {
            "status": status,
            "count": count,
            "percentage": round((count / total_fdrs * 100), 2) if total_fdrs > 0 else 0.0,
        }
        for status, count in validity_counts.items()
    ]

    # 6. Monthly submission/creation totals for the past 6 months (inclusive of current month)
    now = datetime.now(timezone.utc)
    months_keys = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        months_keys.append(f"{y:04d}-{m:02d}")

    monthly_map = {m: {"count": 0, "total_value": Decimal("0")} for m in months_keys}
    fdr_records = base_query.with_entities(FDRRecord.created_at, FDRRecord.amount).all()
    for rec in fdr_records:
        if rec.created_at:
            m_key = rec.created_at.strftime("%Y-%m")
            if m_key in monthly_map:
                monthly_map[m_key]["count"] += 1
                if rec.amount:
                    monthly_map[m_key]["total_value"] += Decimal(str(rec.amount))

    monthly_trends = [
        {
            "month": m,
            "count": data["count"],
            "total_value": float(data["total_value"]),
            "total_value_formatted": f"{data['total_value']:,.2f}",
        }
        for m, data in monthly_map.items()
    ]

    # 7. Recent FDR activity (latest workflow history transitions or creations)
    recent_activity = _get_recent_activity(current_user, institution_id, limit=10)

    return {
        "total_fdrs": total_fdrs,
        "total_value": total_val_float,
        "total_value_formatted": total_val_formatted,
        "status_counts": status_counts,
        "validity_counts": validity_counts,
        "status_breakdown": status_breakdown,
        "validity_breakdown": validity_breakdown,
        "monthly_trends": monthly_trends,
        "recent_activity": recent_activity,
    }


def _get_recent_activity(current_user: User, institution_id: int | None = None, limit: int = 10) -> list[dict]:
    """Retrieve recent workflow decisions and status transitions scoped to authorization boundaries."""
    user_category = UserRole.normalize_category(current_user.role)

    history_query = (
        db.session.query(FDRWorkflowHistory)
        .join(FDRRecord, FDRWorkflowHistory.fdr_id == FDRRecord.id)
    )

    if user_category == "INSTITUTION":
        if not current_user.institution_id:
            return []
        history_query = history_query.filter(FDRRecord.institution_id == current_user.institution_id)
    elif institution_id is not None:
        history_query = history_query.filter(FDRRecord.institution_id == institution_id)

    recent_history = (
        history_query.order_by(FDRWorkflowHistory.created_at.desc(), FDRWorkflowHistory.id.desc())
        .limit(limit)
        .all()
    )

    activities = []
    for h in recent_history:
        activities.append({
            "id": h.id,
            "fdr_id": h.fdr_id,
            "fdr_number": h.fdr.fdr_number if h.fdr else None,
            "from_status": h.from_status,
            "to_status": h.to_status,
            "action": f"SCRUTINY_TRANSITION_{h.from_status}_TO_{h.to_status}",
            "actor_id": h.actor_id,
            "actor_name": h.actor.full_name if h.actor else "System",
            "actor_role": h.actor.role if h.actor else None,
            "remarks": h.remarks,
            "is_deficiency": h.is_deficiency,
            "timestamp": h.created_at.isoformat() if h.created_at else None,
        })

    # If no workflow history transitions exist yet (e.g., initial draft FDRs only), list recent creations
    if not activities:
        base_query = get_authorized_fdr_query(current_user, institution_id=institution_id)
        recent_creations = (
            base_query.order_by(FDRRecord.created_at.desc(), FDRRecord.id.desc())
            .limit(limit)
            .all()
        )
        for f in recent_creations:
            activities.append({
                "id": f.id,
                "fdr_id": f.id,
                "fdr_number": f.fdr_number,
                "from_status": None,
                "to_status": f.scrutiny_status,
                "action": "FDR_CREATED",
                "actor_id": f.created_by,
                "actor_name": f.creator.full_name if f.creator else "System",
                "actor_role": f.creator.role if f.creator else None,
                "remarks": None,
                "is_deficiency": False,
                "timestamp": f.created_at.isoformat() if f.created_at else None,
            })

    return activities
