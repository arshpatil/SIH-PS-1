from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from sqlalchemy import or_

from app.extensions import db
from app.models.enums import UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.services.maturity_service import get_business_date


def parse_date_param(param_str: Optional[str], default_val: date) -> date:
    """Safely parse ISO date string YYYY-MM-DD or return fallback date."""
    if not param_str:
        return default_val
    try:
        return date.fromisoformat(str(param_str).strip()[:10])
    except (ValueError, TypeError):
        return default_val


def get_calendar_events(
    user: Any,
    start_str: Optional[str] = None,
    end_str: Optional[str] = None,
    event_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    institution_id_filter: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Retrieve unified, role-authorized calendar events reflecting:
    - Official FDR maturities
    - Petition submission dates & desk review deadlines
    - Approved renewals awaiting renewed FDR receipts
    - Submitted receipts awaiting officer verification
    - Verified renewal endorsements
    - Correction deficiency deadlines

    Guarantees:
    - Strict institutional data isolation on the backend.
    - Official FDR maturity dates are never altered until verified.
    """
    today = get_business_date()
    start_date = parse_date_param(start_str, today - timedelta(days=90))
    end_date = parse_date_param(end_str, today + timedelta(days=365))

    events: list[dict[str, Any]] = []

    is_institution = user.role == UserRole.INSTITUTION.value
    is_officer = user.role == UserRole.AICTE_OFFICER.value
    is_admin = user.role == UserRole.ADMIN.value

    target_inst_id = user.institution_id if is_institution else institution_id_filter

    # -------------------------------------------------------------
    # 1. Official FDR Maturity Events
    # -------------------------------------------------------------
    fdr_query = FDRRecord.query.filter(
        FDRRecord.maturity_date >= start_date,
        FDRRecord.maturity_date <= end_date,
    )

    if is_institution:
        fdr_query = fdr_query.filter(FDRRecord.institution_id == user.institution_id)
    elif target_inst_id:
        fdr_query = fdr_query.filter(FDRRecord.institution_id == target_inst_id)

    fdrs = fdr_query.all()

    for fdr in fdrs:
        mat_d = fdr.maturity_date.date() if isinstance(fdr.maturity_date, datetime) else fdr.maturity_date
        days_rem = (mat_d - today).days

        # Priority calculation
        if days_rem < 0:
            priority = "URGENT" if days_rem < -30 else "HIGH"
        elif days_rem <= 7:
            priority = "URGENT"
        elif days_rem <= 30:
            priority = "HIGH"
        elif days_rem <= 90:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Check latest petition
        latest_req = None
        req_obj = fdr.requests.order_by(db.text("id DESC")).first()
        if req_obj:
            latest_req = {
                "id": req_obj.id,
                "formatted_id": f"REQ-{req_obj.id:04d}",
                "status": req_obj.status,
                "stage": req_obj.stage,
                "request_type": req_obj.request_type,
            }

        title = f"FDR Maturity: {fdr.fdr_number}"
        if fdr.validity_status == ValidityStatus.RENEWAL_PENDING_VERIFICATION.value:
            desc = (
                f"FDR {fdr.fdr_number} ({fdr.bank_name}) deposit maturity. "
                "Institution has submitted renewed receipt; verification is pending."
            )
        elif latest_req and latest_req["status"] == "Approved":
            desc = (
                f"FDR {fdr.fdr_number} ({fdr.bank_name}) reaches term. "
                "Renewal petition approved — awaiting renewed bank receipt upload."
            )
        else:
            desc = (
                f"Official security deposit of INR {float(fdr.amount):,.2f} "
                f"reaches maturity with {fdr.bank_name}."
            )

        events.append({
            "id": f"fdr-maturity-{fdr.id}",
            "type": "FDR_MATURITY",
            "category": "MATURITY",
            "title": title,
            "description": desc,
            "date": mat_d.isoformat(),
            "fdr_id": fdr.id,
            "fdr_number": fdr.fdr_number,
            "bank_name": fdr.bank_name,
            "branch_name": fdr.branch_name,
            "amount": float(fdr.amount),
            "institution_id": fdr.institution_id,
            "institution_name": fdr.institution.name if fdr.institution else None,
            "status": fdr.validity_status,
            "scrutiny_status": fdr.scrutiny_status,
            "priority": priority,
            "days_remaining": days_rem,
            "linked_request": latest_req,
            "action_required": (
                (days_rem <= 30 and (not latest_req or latest_req["status"] in ("Rejected", "Closed")))
                or (latest_req and latest_req["status"] == "Approved")
            ),
        })

    # -------------------------------------------------------------
    # 2. Petition & Renewal Pipeline Events
    # -------------------------------------------------------------
    req_query = FDRRequest.query

    if is_institution:
        req_query = req_query.filter(FDRRequest.institution_id == user.institution_id)
    elif is_officer:
        req_query = req_query.filter(
            or_(
                FDRRequest.assigned_to == user.id,
                FDRRequest.assigned_to == None,  # noqa: E711
            )
        )
    elif target_inst_id:
        req_query = req_query.filter(FDRRequest.institution_id == target_inst_id)

    requests = req_query.all()

    for req in requests:
        created_d = req.created_at.date() if isinstance(req.created_at, datetime) else today
        fdr_rec = req.fdr

        # A. Petition Submission Event
        if start_date <= created_d <= end_date:
            events.append({
                "id": f"req-sub-{req.id}",
                "type": "PETITION_SUBMITTED",
                "category": "PETITION",
                "title": f"Petition Submitted: REQ-{req.id:04d}",
                "description": f"{req.request_type} petition submitted by {req.institution.name if req.institution else 'Institution'}.",
                "date": created_d.isoformat(),
                "fdr_id": req.fdr_id,
                "fdr_number": fdr_rec.fdr_number if fdr_rec else None,
                "request_id": req.id,
                "request_formatted_id": f"REQ-{req.id:04d}",
                "institution_id": req.institution_id,
                "institution_name": req.institution.name if req.institution else None,
                "status": req.status,
                "stage": req.stage,
                "priority": req.priority or "MEDIUM",
                "action_required": req.status in ("Submitted", "Under Review"),
            })

        # B. Review Target / Scrutiny Deadline (7 days from submission)
        if req.status in ("Submitted", "Under Review"):
            review_deadline = created_d + timedelta(days=7)
            if start_date <= review_deadline <= end_date:
                is_overdue = today > review_deadline
                events.append({
                    "id": f"req-deadline-{req.id}",
                    "type": "PETITION_REVIEW_DEADLINE",
                    "category": "DEADLINE",
                    "title": f"Review Deadline: REQ-{req.id:04d}",
                    "description": f"Target scrutiny date for {req.request_type} petition (APH 7-Day Turnaround).",
                    "date": review_deadline.isoformat(),
                    "fdr_id": req.fdr_id,
                    "fdr_number": fdr_rec.fdr_number if fdr_rec else None,
                    "request_id": req.id,
                    "request_formatted_id": f"REQ-{req.id:04d}",
                    "institution_id": req.institution_id,
                    "institution_name": req.institution.name if req.institution else None,
                    "status": req.status,
                    "priority": "URGENT" if is_overdue else "HIGH",
                    "action_required": True,
                })

        # C. Approved Renewal — Awaiting Receipt Submission
        if req.request_type == "Renewal" and req.status == "Approved" and not req.renewal_submitted_at:
            appr_d = req.updated_at.date() if req.updated_at else created_d
            if start_date <= appr_d <= end_date:
                events.append({
                    "id": f"req-awaiting-receipt-{req.id}",
                    "type": "RENEWAL_APPROVED_AWAITING_RECEIPT",
                    "category": "RENEWAL",
                    "title": f"Renewal Approved — Receipt Due: REQ-{req.id:04d}",
                    "description": "Petition approved. Institution must upload renewed deposit receipt from commercial bank.",
                    "date": appr_d.isoformat(),
                    "fdr_id": req.fdr_id,
                    "fdr_number": fdr_rec.fdr_number if fdr_rec else None,
                    "request_id": req.id,
                    "request_formatted_id": f"REQ-{req.id:04d}",
                    "institution_id": req.institution_id,
                    "institution_name": req.institution.name if req.institution else None,
                    "status": "Approved — Awaiting Renewed Deposit Receipt",
                    "priority": "HIGH",
                    "action_required": is_institution,
                })

        # D. Renewed Receipt Uploaded — Pending Officer Verification
        if req.request_type == "Renewal" and (req.status == "Pending Verification" or req.renewal_submitted_at) and req.status != "Closed":
            sub_d = req.renewal_submitted_at.date() if req.renewal_submitted_at else (req.updated_at.date() if req.updated_at else created_d)
            if start_date <= sub_d <= end_date:
                events.append({
                    "id": f"req-verify-pending-{req.id}",
                    "type": "RENEWAL_PENDING_VERIFICATION",
                    "category": "VERIFICATION",
                    "title": f"Renewal Verification Pending: REQ-{req.id:04d}",
                    "description": f"Renewed FDR receipt submitted with proposed maturity {req.renewal_maturity_date.isoformat() if req.renewal_maturity_date else 'provisional'}. Officer verification required.",
                    "date": sub_d.isoformat(),
                    "fdr_id": req.fdr_id,
                    "fdr_number": fdr_rec.fdr_number if fdr_rec else None,
                    "provisional_fdr_number": req.renewal_fdr_number,
                    "provisional_maturity_date": req.renewal_maturity_date.isoformat() if req.renewal_maturity_date else None,
                    "provisional_amount": float(req.renewal_amount) if req.renewal_amount else None,
                    "request_id": req.id,
                    "request_formatted_id": f"REQ-{req.id:04d}",
                    "institution_id": req.institution_id,
                    "institution_name": req.institution.name if req.institution else None,
                    "status": "Pending Verification",
                    "priority": "URGENT",
                    "action_required": is_officer or is_admin,
                })

        # E. Verified FDR Renewal Endorsement
        if req.request_type == "Renewal" and req.status == "Closed" and req.renewal_verified_at:
            ver_d = req.renewal_verified_at.date()
            if start_date <= ver_d <= end_date:
                events.append({
                    "id": f"req-verified-{req.id}",
                    "type": "RENEWAL_VERIFIED",
                    "category": "RENEWAL",
                    "title": f"Renewal Verified & Endorsed: FDR {fdr_rec.fdr_number if fdr_rec else ''}",
                    "description": f"AICTE verified commercial bank receipt and endorsed term extension to {fdr_rec.maturity_date.isoformat() if fdr_rec else ''}.",
                    "date": ver_d.isoformat(),
                    "fdr_id": req.fdr_id,
                    "fdr_number": fdr_rec.fdr_number if fdr_rec else None,
                    "request_id": req.id,
                    "request_formatted_id": f"REQ-{req.id:04d}",
                    "institution_id": req.institution_id,
                    "institution_name": req.institution.name if req.institution else None,
                    "status": "Closed",
                    "priority": "LOW",
                    "action_required": False,
                })

        # F. Deficiency / Documents Required Correction Due
        if req.status == "Documents Required":
            cor_d = req.updated_at.date() if req.updated_at else created_d
            if start_date <= cor_d <= end_date:
                events.append({
                    "id": f"req-deficiency-{req.id}",
                    "type": "DOCUMENTS_REQUIRED",
                    "category": "DEFICIENCY",
                    "title": f"Corrections Mandate: REQ-{req.id:04d}",
                    "description": f"Deficiencies issued by AICTE Scrutiny Officer: {req.remarks or 'Missing documentation'}.",
                    "date": cor_d.isoformat(),
                    "fdr_id": req.fdr_id,
                    "fdr_number": fdr_rec.fdr_number if fdr_rec else None,
                    "request_id": req.id,
                    "request_formatted_id": f"REQ-{req.id:04d}",
                    "institution_id": req.institution_id,
                    "institution_name": req.institution.name if req.institution else None,
                    "status": "Documents Required",
                    "priority": "URGENT",
                    "action_required": is_institution,
                })

    # -------------------------------------------------------------
    # 3. Apply Optional Query Filters
    # -------------------------------------------------------------
    filtered = events

    if event_type and event_type != "ALL":
        filtered = [e for e in filtered if e["type"] == event_type or e["category"] == event_type]

    if status_filter and status_filter != "ALL":
        clean_st = status_filter.lower().strip()
        filtered = [e for e in filtered if clean_st in str(e.get("status", "")).lower()]

    if priority_filter and priority_filter != "ALL":
        clean_pr = priority_filter.upper().strip()
        filtered = [e for e in filtered if e.get("priority", "").upper() == clean_pr]

    # Sort chronologically by date ascending, then priority
    priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    filtered.sort(key=lambda x: (x["date"], priority_order.get(x.get("priority", "MEDIUM"), 2)))

    return filtered
