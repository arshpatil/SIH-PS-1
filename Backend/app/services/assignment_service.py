import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import or_, func

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import NotificationType, UserRole
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest, PetitionAssignmentHistory
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)

ACTIVE_PETITION_STATUSES = [
    "Submitted",
    "Under Review",
    "Documents Required",
    "Resubmitted / Awaiting Review",
]

COMPLETED_PETITION_STATUSES = [
    "Approved",
    "Rejected",
    "Closed",
]


def get_eligible_officers() -> list[User]:
    """
    Return all active scrutiny officers eligible for petition assignment.
    Prefers AICTE_OFFICER accounts; falls back to active ADMIN accounts if no officers exist.
    """
    officers = (
        User.query.filter(
            User.role == UserRole.AICTE_OFFICER.value,
            User.is_active.is_(True),
        )
        .order_by(User.id.asc())
        .all()
    )

    if not officers:
        # Fallback to active administrators if no dedicated scrutiny officers exist
        officers = (
            User.query.filter(
                User.role.in_([UserRole.ADMIN.value, UserRole.AICTE_ADMIN.value, UserRole.SYSTEM_ADMIN.value]),
                User.is_active.is_(True),
            )
            .order_by(User.id.asc())
            .all()
        )

    return officers


def get_officer_active_workload(officer_id: int) -> int:
    """Return the number of unresolved active petitions currently assigned to an officer."""
    return (
        FDRRequest.query.filter(
            FDRRequest.assigned_to == officer_id,
            FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
        ).count()
    )


def select_best_officer_for_assignment(
    exclude_officer_id: Optional[int] = None,
) -> Optional[User]:
    """
    Select the optimal officer using workload-based distribution:
    1. Filter eligible active officers (excluding `exclude_officer_id` if provided).
    2. Identify officers with the minimum current pending workload.
    3. If multiple officers have the same lowest workload (tie-break):
       - Select the officer who was least recently assigned a petition (LRU).
       - If still tied, pick lowest user ID for deterministic balancing.
    """
    eligible = get_eligible_officers()
    if exclude_officer_id:
        eligible = [o for o in eligible if o.id != exclude_officer_id]

    if not eligible:
        return None

    # Calculate current workload for each eligible officer
    workload_map = {o.id: get_officer_active_workload(o.id) for o in eligible}
    min_workload = min(workload_map.values())
    candidates = [o for o in eligible if workload_map[o.id] == min_workload]

    if len(candidates) == 1:
        return candidates[0]

    # Tie-breaker: Find least recently assigned officer
    best_candidate = None
    oldest_assigned_time = None

    for candidate in candidates:
        last_assignment = (
            PetitionAssignmentHistory.query.filter(
                PetitionAssignmentHistory.new_officer_id == candidate.id
            )
            .order_by(PetitionAssignmentHistory.created_at.desc())
            .first()
        )

        if not last_assignment:
            # Never assigned before -> highest priority
            return candidate

        last_time = last_assignment.created_at
        if oldest_assigned_time is None or last_time < oldest_assigned_time:
            oldest_assigned_time = last_time
            best_candidate = candidate

    return best_candidate or candidates[0]


def auto_assign_petition(
    fdr_request: FDRRequest, commit: bool = True
) -> tuple[bool, str, Optional[User]]:
    """
    Automatically assign an unassigned petition to the optimal officer based on workload.
    Guarantees:
    - Never silently overwrites an existing assignment.
    - Records an immutable PetitionAssignmentHistory audit entry.
    - Emits in-app and email notifications safely.
    """
    if fdr_request.assigned_to is not None:
        return (
            False,
            f"Petition REQ-{fdr_request.id:04d} already has an assigned officer.",
            fdr_request.assigned_officer,
        )

    if fdr_request.status in COMPLETED_PETITION_STATUSES:
        return False, "Cannot assign a finalized petition.", None

    officer = select_best_officer_for_assignment()
    if not officer:
        return False, "No active scrutiny officers currently available.", None

    workload_before = get_officer_active_workload(officer.id)
    fdr_request.assigned_to = officer.id

    # Record immutable assignment history
    history = PetitionAssignmentHistory(
        request_id=fdr_request.id,
        previous_officer_id=None,
        new_officer_id=officer.id,
        assigned_by_id=None,  # System auto-assignment
        assignment_type="AUTO_ASSIGNMENT",
        reason=f"Smart workload-based auto-distribution (Officer pending queue: {workload_before} cases).",
    )
    db.session.add(history)

    # Record AuditLog
    audit = AuditLog(
        user_id=None,
        action="PETITION_AUTO_ASSIGNED",
        entity_type="FDRRequest",
        entity_id=fdr_request.id,
        details=(
            f"Auto-assigned petition REQ-{fdr_request.id:04d} to "
            f"{officer.full_name} ({officer.email}) [Workload: {workload_before}]."
        ),
    )
    db.session.add(audit)

    # In-app notification for assigned officer
    notif = Notification(
        user_id=officer.id,
        title=f"New Petition Assigned: REQ-{fdr_request.id:04d}",
        message=(
            f"You have been assigned to scrutinize {fdr_request.request_type} petition "
            f"REQ-{fdr_request.id:04d} for {fdr_request.institution.name if fdr_request.institution else 'Institution'}. "
            f"Priority: {fdr_request.priority}."
        ),
        notification_type=NotificationType.ACTION_REQUIRED.value
        if fdr_request.priority in ("CRITICAL", "HIGH")
        else NotificationType.INFO.value,
        is_read=False,
    )
    db.session.add(notif)

    if commit:
        try:
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            logger.error("Failed to persist auto-assignment for REQ-%04d: %s", fdr_request.id, ex)
            return False, f"Database error during assignment: {str(ex)}", None

    # Trigger statutory email notification safely
    try:
        from app.services.email_service import send_petition_assignment_email
        send_petition_assignment_email(fdr_request, officer, is_reassignment=False)
    except Exception as email_err:
        logger.error(
            "Non-fatal error delivering assignment email for REQ-%04d to %s: %s",
            fdr_request.id,
            officer.email,
            email_err,
        )

    return (
        True,
        f"Petition REQ-{fdr_request.id:04d} automatically assigned to {officer.full_name}.",
        officer,
    )


def reassign_petition(
    fdr_request: FDRRequest,
    new_officer_id: int,
    assigned_by_user: User,
    reason: str = "",
    commit: bool = True,
) -> tuple[bool, str, Optional[User]]:
    """
    Manually assign or reassign a petition to a specific officer.
    Guarantees:
    - Target officer must exist and be active with AICTE_OFFICER or ADMIN role.
    - Prevents redundant self-assignment if already assigned to that exact officer.
    - Records an immutable PetitionAssignmentHistory record with explicit admin reason.
    - Notifies the new officer and the former officer.
    """
    target_officer = db.session.get(User, new_officer_id)
    if not target_officer or not target_officer.is_active:
        return False, f"Officer with ID {new_officer_id} not found or inactive.", None

    role_cat = UserRole.normalize_category(target_officer.role)
    if role_cat not in ("AICTE_OFFICER", "ADMIN"):
        return False, "Target user is not authorized for petition scrutiny.", None

    if fdr_request.assigned_to == new_officer_id:
        return (
            False,
            f"Petition REQ-{fdr_request.id:04d} is already assigned to {target_officer.full_name}.",
            target_officer,
        )

    prev_officer_id = fdr_request.assigned_to
    prev_officer = fdr_request.assigned_officer
    is_reassignment = prev_officer_id is not None

    clean_reason = reason.strip() if reason and reason.strip() else (
        "Administrative workload rebalancing" if is_reassignment else "Administrative manual assignment"
    )

    fdr_request.assigned_to = new_officer_id

    # Record immutable assignment history
    history = PetitionAssignmentHistory(
        request_id=fdr_request.id,
        previous_officer_id=prev_officer_id,
        new_officer_id=new_officer_id,
        assigned_by_id=assigned_by_user.id,
        assignment_type="REASSIGNMENT" if is_reassignment else "MANUAL_ASSIGNMENT",
        reason=clean_reason,
    )
    db.session.add(history)

    # Record AuditLog
    audit_action = "PETITION_REASSIGNED" if is_reassignment else "PETITION_MANUALLY_ASSIGNED"
    audit = AuditLog(
        user_id=assigned_by_user.id,
        action=audit_action,
        entity_type="FDRRequest",
        entity_id=fdr_request.id,
        details=(
            f"Petition REQ-{fdr_request.id:04d} assigned to {target_officer.full_name} "
            f"(Previous: {prev_officer.full_name if prev_officer else 'Unassigned'}). "
            f"Reason: {clean_reason}"
        ),
    )
    db.session.add(audit)

    # Notify newly assigned officer
    notif_new = Notification(
        user_id=target_officer.id,
        title=f"Petition {'Reassigned' if is_reassignment else 'Assigned'}: REQ-{fdr_request.id:04d}",
        message=(
            f"You have been assigned to review {fdr_request.request_type} petition REQ-{fdr_request.id:04d}. "
            f"Assigned by: {assigned_by_user.full_name}. Reason: {clean_reason}."
        ),
        notification_type=NotificationType.ACTION_REQUIRED.value
        if fdr_request.priority in ("CRITICAL", "HIGH")
        else NotificationType.INFO.value,
        is_read=False,
    )
    db.session.add(notif_new)

    # Notify former officer if reassigned
    if prev_officer and prev_officer.id != assigned_by_user.id:
        notif_old = Notification(
            user_id=prev_officer.id,
            title=f"Petition Reassigned: REQ-{fdr_request.id:04d}",
            message=(
                f"Petition REQ-{fdr_request.id:04d} previously assigned to you has been reassigned to "
                f"{target_officer.full_name} by {assigned_by_user.full_name}."
            ),
            notification_type=NotificationType.INFO.value,
            is_read=False,
        )
        db.session.add(notif_old)

    if commit:
        try:
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            logger.error("Failed to commit reassignment for REQ-%04d: %s", fdr_request.id, ex)
            return False, f"Database error during reassignment: {str(ex)}", None

    # Deliver emails safely
    try:
        from app.services.email_service import send_petition_assignment_email
        send_petition_assignment_email(
            fdr_request,
            target_officer,
            is_reassignment=is_reassignment,
            reason=clean_reason,
            previous_officer=prev_officer,
        )
    except Exception as email_err:
        logger.error(
            "Non-fatal error delivering reassignment email for REQ-%04d: %s",
            fdr_request.id,
            email_err,
        )

    return (
        True,
        f"Petition REQ-{fdr_request.id:04d} successfully assigned to {target_officer.full_name}.",
        target_officer,
    )


def auto_assign_all_unassigned_petitions(
    admin_user: Optional[User] = None,
) -> dict:
    """
    Batch distribute all active unassigned petitions across eligible officers.
    """
    unassigned = (
        FDRRequest.query.filter(
            FDRRequest.assigned_to.is_(None),
            FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
        )
        .order_by(FDRRequest.created_at.asc())
        .all()
    )

    assigned_count = 0
    failures = []

    for req in unassigned:
        success, msg, officer = auto_assign_petition(req, commit=False)
        if success:
            assigned_count += 1
        else:
            failures.append({"id": f"REQ-{req.id:04d}", "error": msg})

    if assigned_count > 0:
        db.session.commit()

    return {
        "success": True,
        "total_unassigned_found": len(unassigned),
        "successfully_assigned": assigned_count,
        "failed_count": len(failures),
        "failures": failures,
    }


def calculate_admin_workload_metrics() -> dict:
    """
    Compute comprehensive workload, SLA adherence, and average processing time metrics
    for the Central Admin Workload Dashboard.
    """
    now_utc = datetime.now(timezone.utc)
    cutoff_overdue = now_utc - timedelta(days=14)

    officers = (
        User.query.filter(
            User.role.in_([UserRole.AICTE_OFFICER.value, UserRole.ADMIN.value]),
        )
        .order_by(User.full_name.asc())
        .all()
    )

    total_active_officers = sum(1 for o in officers if o.is_active)
    officer_metrics = []
    all_completed_durations_hours = []

    total_system_active_cases = 0

    for off in officers:
        assigned_active_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
        ).count()
        total_system_active_cases += assigned_active_count

        resolved_reqs = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(COMPLETED_PETITION_STATUSES),
        ).all()
        resolved_count = len(resolved_reqs)

        overdue_count = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
            FDRRequest.created_at <= cutoff_overdue,
        ).count()

        # Compute average processing turnaround for this officer
        officer_durations = []
        for r in resolved_reqs:
            if r.created_at and r.updated_at:
                c_dt = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
                u_dt = r.updated_at if r.updated_at.tzinfo else r.updated_at.replace(tzinfo=timezone.utc)
                diff_hours = (u_dt - c_dt).total_seconds() / 3600.0
                if diff_hours >= 0:
                    officer_durations.append(diff_hours)
                    all_completed_durations_hours.append(diff_hours)

        avg_hours = round(sum(officer_durations) / len(officer_durations), 1) if officer_durations else None
        avg_days = round(avg_hours / 24.0, 1) if avg_hours is not None else None

        # Critical petitions assigned to officer
        critical_count = 0
        active_officer_reqs = FDRRequest.query.filter(
            FDRRequest.assigned_to == off.id,
            FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
        ).all()
        for r in active_officer_reqs:
            if r.priority == "CRITICAL":
                critical_count += 1

        officer_metrics.append({
            "officer_id": off.id,
            "officer_name": off.full_name,
            "officer_email": off.email,
            "is_active": off.is_active,
            "role": off.role,
            "active_assigned_cases": assigned_active_count,
            "resolved_cases": resolved_count,
            "overdue_cases": overdue_count,
            "critical_cases": critical_count,
            "avg_processing_time_hours": avg_hours,
            "avg_processing_time_days": avg_days,
            "workload_share_pct": 0.0,  # Computed below
        })

    # Compute percentage workload distribution
    for om in officer_metrics:
        if total_system_active_cases > 0 and om["is_active"]:
            om["workload_share_pct"] = round(
                (om["active_assigned_cases"] / total_system_active_cases) * 100.0, 1
            )
        else:
            om["workload_share_pct"] = 0.0

    system_avg_hours = (
        round(sum(all_completed_durations_hours) / len(all_completed_durations_hours), 1)
        if all_completed_durations_hours
        else None
    )
    system_avg_days = round(system_avg_hours / 24.0, 1) if system_avg_hours is not None else None

    # Count system-wide critical and unassigned cases
    unassigned_count = FDRRequest.query.filter(
        FDRRequest.assigned_to.is_(None),
        FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
    ).count()

    system_overdue_count = FDRRequest.query.filter(
        FDRRequest.status.in_(ACTIVE_PETITION_STATUSES),
        FDRRequest.created_at <= cutoff_overdue,
    ).count()

    all_active_petitions = FDRRequest.query.filter(
        FDRRequest.status.in_(ACTIVE_PETITION_STATUSES)
    ).all()
    system_critical_count = sum(1 for p in all_active_petitions if p.priority == "CRITICAL")

    return {
        "total_active_officers": total_active_officers,
        "total_system_active_cases": total_system_active_cases,
        "unassigned_cases_count": unassigned_count,
        "system_overdue_cases": system_overdue_count,
        "system_critical_cases": system_critical_count,
        "system_avg_processing_time_hours": system_avg_hours,
        "system_avg_processing_time_days": system_avg_days,
        "officers_workload": officer_metrics,
    }


def scan_and_alert_critical_and_overdue_petitions() -> dict:
    """
    Automated watchdog scanner:
    - Alerts officers about assigned petitions that are CRITICAL (maturity <= 7 days).
    - Alerts officers about assigned petitions that are OVERDUE (> 14 days pending).
    - Alerts central administrators about unattended / unassigned CRITICAL petitions.
    Guarantees idempotence / deduplication via EmailNotificationLog.
    """
    from app.services.email_service import (
        send_petition_critical_escalation_alert,
        send_petition_overdue_escalation_alert,
        send_admin_unattended_critical_alert,
    )

    active_petitions = FDRRequest.query.filter(
        FDRRequest.status.in_(ACTIVE_PETITION_STATUSES)
    ).all()

    critical_alerts_sent = 0
    overdue_alerts_sent = 0
    admin_alerts_sent = 0

    admin_users = User.query.filter(
        User.role.in_([UserRole.ADMIN.value, UserRole.AICTE_ADMIN.value, UserRole.SYSTEM_ADMIN.value]),
        User.is_active.is_(True),
    ).all()

    for req in active_petitions:
        # 1. Critical Alert for Assigned Officer
        if req.priority == "CRITICAL":
            if req.assigned_officer and req.assigned_officer.is_active:
                sent = send_petition_critical_escalation_alert(req, req.assigned_officer)
                if sent:
                    critical_alerts_sent += 1
            elif not req.assigned_to:
                # Unattended critical petition -> notify admins
                sent = send_admin_unattended_critical_alert(req, admin_users)
                if sent:
                    admin_alerts_sent += 1

        # 2. Overdue Alert for Assigned Officer
        if req.is_overdue and req.assigned_officer and req.assigned_officer.is_active:
            sent = send_petition_overdue_escalation_alert(req, req.assigned_officer)
            if sent:
                overdue_alerts_sent += 1

    return {
        "success": True,
        "scanned_active_count": len(active_petitions),
        "critical_alerts_sent": critical_alerts_sent,
        "overdue_alerts_sent": overdue_alerts_sent,
        "admin_unattended_alerts_sent": admin_alerts_sent,
    }

