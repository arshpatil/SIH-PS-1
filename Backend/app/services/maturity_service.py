from datetime import date, datetime, timezone
import os
from flask import current_app

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import NotificationType, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.notification import Notification
from app.models.user import User


def get_business_date(as_of_date: date | None = None) -> date:
    """Return the reference business date (UTC by default, or injected date)."""
    if as_of_date is not None:
        if isinstance(as_of_date, datetime):
            return as_of_date.date()
        return as_of_date
    return datetime.now(timezone.utc).date()


def classify_validity_status(
    maturity_date: date,
    as_of_date: date | None = None,
    expiring_soon_days: int = 30,
    overdue_action_days: int = 30,
) -> ValidityStatus:
    """Calculate the FDR validity status based on business date and configurable thresholds."""
    ref_date = get_business_date(as_of_date)
    days_remaining = (maturity_date - ref_date).days

    if days_remaining > expiring_soon_days:
        return ValidityStatus.ACTIVE

    if 0 < days_remaining <= expiring_soon_days:
        return ValidityStatus.EXPIRING_SOON

    if 0 >= days_remaining > -overdue_action_days:
        return ValidityStatus.MATURED

    # days_remaining <= -overdue_action_days
    return ValidityStatus.OVERDUE_ACTION


def get_maturity_category(maturity_date: date, as_of_date: date | None = None) -> str:
    """Return precise non-overlapping maturity brackets for dashboards and filtering."""
    ref_date = get_business_date(as_of_date)
    days_remaining = (maturity_date - ref_date).days

    if days_remaining > 90:
        return "FUTURE"
    if 60 < days_remaining <= 90:
        return "MATURING_90_DAYS"
    if 30 < days_remaining <= 60:
        return "MATURING_60_DAYS"
    if 7 < days_remaining <= 30:
        return "MATURING_30_DAYS"
    if 0 <= days_remaining <= 7:
        return "MATURING_7_DAYS"
    if -30 < days_remaining < 0:
        return "MATURED"
    return "OVERDUE_ACTION"


def scan_and_update_maturities(
    as_of_date: date | None = None,
    reminder_intervals: list[int] | None = None,
) -> dict:
    """Scan all FDR records, update validity status, and generate idempotent notifications."""
    ref_date = get_business_date(as_of_date)

    expiring_soon_days = current_app.config.get("EXPIRING_SOON_DAYS", 30)
    overdue_action_days = current_app.config.get("OVERDUE_ACTION_DAYS", 30)
    if reminder_intervals is None:
        reminder_intervals = current_app.config.get(
            "REMINDER_INTERVAL_DAYS", [90, 60, 30, 15, 7, 0]
        )

    fdrs = FDRRecord.query.all()
    scanned_count = len(fdrs)
    updated_count = 0
    notifications_created = 0

    # Cache AICTE officers/admins for escalation reminders
    officers = User.query.filter(
        User.role.in_(
            [
                UserRole.AICTE_OFFICER.value,
                UserRole.ADMIN.value,
                UserRole.AICTE_ADMIN.value,
                UserRole.SYSTEM_ADMIN.value,
            ]
        ),
        User.is_active.is_(True),
    ).all()

    fdr_emails_to_send = []

    for fdr in fdrs:
        # Respect current status: Skip rejected FDRs
        if fdr.scrutiny_status == ScrutinyStatus.REJECTED.value:
            continue

        # 1. Update validity status (preserving officer scrutiny status and unrelated fields)
        calculated_status = classify_validity_status(
            fdr.maturity_date,
            as_of_date=ref_date,
            expiring_soon_days=expiring_soon_days,
            overdue_action_days=overdue_action_days,
        )

        if fdr.validity_status != calculated_status.value:
            fdr.validity_status = calculated_status.value
            updated_count += 1

        # 2. Check for reminder interval triggers
        days_remaining = (fdr.maturity_date - ref_date).days

        title = None
        message = None
        notif_type = NotificationType.INFO
        is_escalation = False

        if days_remaining in reminder_intervals:
            fdr_emails_to_send.append((fdr, days_remaining))
            if days_remaining == 90:
                title = f"FDR Maturity Advisory: {fdr.fdr_number} (90 Days Remaining)"
                message = (
                    f"Advance Advisory: Fixed Deposit Receipt {fdr.fdr_number} of {fdr.bank_name} "
                    f"(INR {fdr.amount}) will mature on {fdr.maturity_date} (in 90 days). "
                    "Please initiate timely renewal or AICTE lien release procedures."
                )
                notif_type = NotificationType.INFO

            elif days_remaining == 60:
                title = f"FDR Maturity Notice: {fdr.fdr_number} (60 Days Remaining)"
                message = (
                    f"Fixed Deposit Receipt {fdr.fdr_number} of {fdr.bank_name} "
                    f"will mature in 60 days on {fdr.maturity_date}. Please prepare renewal documentation."
                )
                notif_type = NotificationType.INFO

            elif days_remaining == 30:
                title = f"FDR Maturity Reminder: {fdr.fdr_number} (30 Days Remaining)"
                message = (
                    f"Fixed Deposit Receipt {fdr.fdr_number} of {fdr.bank_name} "
                    f"(INR {fdr.amount}) will mature on {fdr.maturity_date} (in 30 days). "
                    "Please initiate timely renewal or lien release procedures."
                )
                notif_type = NotificationType.WARNING

            elif days_remaining == 15:
                title = f"FDR Maturity Reminder: {fdr.fdr_number} (15 Days Remaining)"
                message = (
                    f"Fixed Deposit Receipt {fdr.fdr_number} of {fdr.bank_name} "
                    f"will mature in 15 days on {fdr.maturity_date}. Action is required to ensure compliance."
                )
                notif_type = NotificationType.WARNING

            elif days_remaining == 7:
                title = f"Urgent: FDR {fdr.fdr_number} Matures in 7 Days"
                message = (
                    f"URGENT: Fixed Deposit Receipt {fdr.fdr_number} matures on {fdr.maturity_date} "
                    "(7 days remaining). Please submit renewed FDR or AICTE lien release request."
                )
                notif_type = NotificationType.ACTION_REQUIRED
                is_escalation = True

            elif days_remaining == 0:
                title = f"FDR Matured Today: {fdr.fdr_number}"
                message = (
                    f"Fixed Deposit Receipt {fdr.fdr_number} has matured today ({fdr.maturity_date}). "
                    "Immediate renewal certificate or lien release documentation is required."
                )
                notif_type = NotificationType.ALERT
                is_escalation = True

        elif days_remaining <= -overdue_action_days:
            # Overdue action notification (deterministic title prevents duplicate notifications on successive days)
            days_overdue = abs(days_remaining)
            title = f"Action Overdue: FDR {fdr.fdr_number} Matured on {fdr.maturity_date}"
            message = (
                f"OVERDUE NOTICE: Fixed Deposit Receipt {fdr.fdr_number} matured on {fdr.maturity_date} "
                f"and is {days_overdue} days past maturity. Mandatory AICTE action is required."
            )
            notif_type = NotificationType.ALERT
            is_escalation = True

        if not title:
            continue

        # 3. Determine recipients
        recipients = User.query.filter_by(
            institution_id=fdr.institution_id, is_active=True
        ).all()

        if is_escalation:
            recipients = list(set(recipients + officers))

        # 4. Idempotently generate notifications
        for recipient in recipients:
            already_sent = Notification.query.filter_by(
                user_id=recipient.id, title=title
            ).first()

            if not already_sent:
                notif = Notification(
                    user_id=recipient.id,
                    title=title,
                    message=message,
                    notification_type=notif_type.value,
                    is_read=False,
                )
                db.session.add(notif)
                notifications_created += 1

    # Record system audit trail entry
    audit = AuditLog(
        user_id=None,
        action="MATURITY_SCAN_COMPLETED",
        entity_type="SystemJob",
        entity_id=None,
        details=(
            f"Maturity scan executed as of {ref_date}. Scanned {scanned_count} FDRs; "
            f"updated {updated_count} validity statuses; generated {notifications_created} notifications."
        ),
    )
    db.session.add(audit)
    db.session.commit()

    # 5. Dispatch automated email notifications post-commit (strictly idempotent)
    emails_sent_count = 0
    from app.services.email_service import send_fdr_maturity_email

    for fdr_item, rem_days in fdr_emails_to_send:
        try:
            sent_now = send_fdr_maturity_email(fdr_item, rem_days, as_of_date=ref_date)
            emails_sent_count += sent_now
        except Exception as email_err:
            current_app.logger.error(
                f"Non-fatal error delivering maturity reminder email for FDR {fdr_item.fdr_number}: {email_err}"
            )

    return {
        "as_of_date": ref_date.isoformat(),
        "scanned_count": scanned_count,
        "updated_count": updated_count,
        "notifications_created": notifications_created,
        "emails_sent_count": emails_sent_count,
    }

