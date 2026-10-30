"""
Automated Statutory Email Notification Service for AICTE Security Deposit & FDR Management Portal.

Features:
- Pure Python smtplib implementation (compatible with Gmail SMTP port 587 TLS).
- Multi-part MIME messages (HTML + Plaintext fallback).
- Strictly prevents duplicate emails for the same FDR and reminder interval.
- Idempotent and transaction-safe (invoked after DB commits).
- Handles missing or invalid recipient addresses gracefully.
- Secure logging: credentials and passwords are never logged or exposed.
- Respects testing and suppression flags (MAIL_SUPPRESS_SEND / TESTING).
"""

from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import re
import smtplib
from typing import Any, Optional

from flask import current_app

from app.extensions import db
from app.models.email_log import EmailNotificationLog
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution

logger = logging.getLogger(__name__)

# Basic RFC-5322 compatible email validation pattern
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email_str: Optional[str]) -> bool:
    """Validate email format without raising exceptions."""
    if not email_str or not isinstance(email_str, str):
        return False
    return bool(EMAIL_REGEX.match(email_str.strip()))


def get_institution_emails(institution: Optional[Institution]) -> list[str]:
    """Retrieve unique verified recipient emails for an institution."""
    if not institution:
        return []

    recipients: set[str] = set()

    # Primary institutional contact email
    if is_valid_email(institution.contact_email):
        recipients.add(institution.contact_email.strip().lower())

    # Active institutional user logins linked to this college
    if hasattr(institution, "users"):
        for user in institution.users:
            if getattr(user, "is_active", True) and is_valid_email(user.email):
                recipients.add(user.email.strip().lower())

    return sorted(list(recipients))


def is_fdr_reminder_already_sent(fdr_id: int, reminder_interval_days: int) -> bool:
    """Check if an FDR maturity reminder for this specific interval was already delivered."""
    existing = EmailNotificationLog.query.filter_by(
        fdr_id=fdr_id,
        email_type="FDR_MATURITY_REMINDER",
        reminder_interval_days=reminder_interval_days,
        status="SENT",
    ).first()
    return existing is not None


def is_receipt_reminder_already_sent(request_id: int, milestone: str) -> bool:
    """Check if a renewal receipt reminder for this milestone was already delivered."""
    existing = EmailNotificationLog.query.filter_by(
        request_id=request_id,
        email_type=f"RENEWAL_RECEIPT_REMINDER_{milestone}",
        status="SENT",
    ).first()
    return existing is not None


def _build_html_template(
    title: str,
    preheader: str,
    institution_name: str,
    key_details: list[tuple[str, str]],
    message_paragraphs: list[str],
    action_button: Optional[tuple[str, str]] = None,
) -> str:
    """Render a clean, professional AICTE-branded HTML email."""
    details_html = "".join(
        f"""
        <tr>
            <td style="padding: 8px 12px; font-weight: 600; color: #475569; width: 35%; border-bottom: 1px solid #E2E8F0; font-size: 13px;">{label}</td>
            <td style="padding: 8px 12px; color: #0F172A; border-bottom: 1px solid #E2E8F0; font-size: 13px;">{value}</td>
        </tr>
        """
        for label, value in key_details
    )

    paragraphs_html = "".join(
        f'<p style="margin: 0 0 14px; font-size: 14px; line-height: 1.6; color: #334155;">{p}</p>'
        for p in message_paragraphs
    )

    action_btn_html = ""
    if action_button:
        btn_label, btn_url = action_button
        action_btn_html = f"""
        <div style="margin: 24px 0 16px; text-align: center;">
            <a href="{btn_url}" style="background-color: #142B4A; color: #FFFFFF; font-weight: bold; font-size: 13px; text-decoration: none; padding: 12px 24px; border-radius: 6px; display: inline-block;">
                {btn_label}
            </a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 24px 12px;">
        <div style="max-width: 620px; margin: 0 auto; background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <!-- Header -->
            <div style="background-color: #142B4A; padding: 24px; text-align: left; border-bottom: 3px solid #F59E0B;">
                <div style="display: inline-block; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; color: #F59E0B; margin-bottom: 4px;">
                    All India Council for Technical Education
                </div>
                <h1 style="color: #FFFFFF; margin: 0; font-size: 18px; font-weight: 700; line-height: 1.3;">
                    Security Deposit & FDR Monitoring Cell
                </h1>
                <p style="color: #94A3B8; font-size: 12px; margin: 4px 0 0;">
                    Official Statutory Advisory & Workflow Communication
                </p>
            </div>

            <!-- Content Area -->
            <div style="padding: 24px;">
                <div style="font-size: 14px; font-weight: 600; color: #0F172A; margin-bottom: 12px;">
                    Dear Principal / Authorized Representative,<br>
                    <span style="color: #1E3A8A;">{institution_name}</span>
                </div>

                <div style="background-color: #FEF3C7; border-left: 4px solid #D97706; padding: 10px 14px; margin-bottom: 18px; border-radius: 0 4px 4px 0;">
                    <strong style="color: #92400E; font-size: 13px;">Notice: {title}</strong>
                    <div style="color: #B45309; font-size: 12px; margin-top: 2px;">{preheader}</div>
                </div>

                {paragraphs_html}

                {f'''
                <!-- Key Details Table -->
                <table style="width: 100%; border-collapse: collapse; margin: 18px 0; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; overflow: hidden;">
                    {details_html}
                </table>
                ''' if key_details else ''}

                {action_btn_html}

                <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #E2E8F0; font-size: 12px; color: #64748B; line-height: 1.5;">
                    <p style="margin: 0 0 6px;">
                        <strong>Compliance Note:</strong> Security Deposit Fixed Deposit Receipts pledged to AICTE must remain actively renewed in commercial/nationalized banks throughout the institutional affiliation term.
                    </p>
                    <p style="margin: 0;">
                        For questions regarding this communication, log in to the official AICTE FDR Management Portal.
                    </p>
                </div>
            </div>

            <!-- Footer -->
            <div style="background-color: #F1F5F9; padding: 16px 24px; text-align: center; border-top: 1px solid #E2E8F0; font-size: 11px; color: #64748B;">
                <p style="margin: 0 0 4px;">Nelson Mandela Marg, Vasant Kunj, New Delhi - 110070</p>
                <p style="margin: 0;">This is an automated administrative notification. Please do not reply directly to this email address.</p>
            </div>
        </div>
    </body>
    </html>
    """


def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    email_type: str = "GENERAL",
    fdr_id: Optional[int] = None,
    request_id: Optional[int] = None,
    institution_id: Optional[int] = None,
    reminder_interval_days: Optional[int] = None,
) -> bool:
    """
    Deliver a single statutory email notification via configured SMTP gateway.

    Guarantees:
    - Never throws uncaught exceptions to caller.
    - Records audit log entry with delivery status (SENT or FAILED).
    - Never logs passwords or sensitive credentials.
    - Suppressed safely during tests or when MAIL_SUPPRESS_SEND is active.
    """
    clean_to = str(to_email or "").strip().lower()

    if not is_valid_email(clean_to):
        logger.warning(
            "Skipping email delivery: invalid recipient address '%s' for type '%s'",
            to_email,
            email_type,
        )
        return False

    app = current_app._get_current_object()  # type: ignore[attr-defined]
    config = app.config

    server_host = config.get("MAIL_SERVER", "smtp.gmail.com")
    server_port = int(config.get("MAIL_PORT", 587))
    use_tls = bool(config.get("MAIL_USE_TLS", True))
    use_ssl = bool(config.get("MAIL_USE_SSL", False))
    username = config.get("MAIL_USERNAME", "")
    password = config.get("MAIL_PASSWORD", "")
    default_sender = config.get("MAIL_DEFAULT_SENDER", username or "AICTE FDR Portal <noreply@aicte.gov.in>")

    is_testing = bool(config.get("TESTING", False))
    is_suppressed = bool(config.get("MAIL_SUPPRESS_SEND", False))

    # Construct standard multi-part email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = default_sender
    msg["To"] = clean_to

    # Plain text fallback
    part_text = MIMEText(body_text, "plain", "utf-8")
    msg.attach(part_text)

    # Rich HTML part if provided
    if body_html:
        part_html = MIMEText(body_html, "html", "utf-8")
        msg.attach(part_html)

    # 1. Delivery Stage (Mock or Live SMTP)
    smtp_success = False
    smtp_error = None

    if is_testing or is_suppressed:
        logger.info(
            "[MOCK EMAIL] Suppressed delivery to %s | Type: %s | Subject: %s",
            clean_to,
            email_type,
            subject,
        )
        smtp_success = True
    else:
        try:
            if use_ssl:
                smtp_client = smtplib.SMTP_SSL(server_host, server_port, timeout=12)
            else:
                smtp_client = smtplib.SMTP(server_host, server_port, timeout=12)

            with smtp_client:
                smtp_client.ehlo()
                if use_tls and not use_ssl:
                    smtp_client.starttls()
                    smtp_client.ehlo()

                if username and password:
                    smtp_client.login(username, password)

                smtp_client.send_message(msg)

            smtp_success = True
            logger.info(
                "Successfully dispatched statutory email to %s | Type: %s",
                clean_to,
                email_type,
            )
        except Exception as exc:
            smtp_success = False
            smtp_error = str(exc)
            logger.error(
                "SMTP delivery failed to %s [type=%s]: %s",
                clean_to,
                email_type,
                smtp_error,
            )

    # 2. Database Audit Logging Stage (Isolated Transaction)
    try:
        log_entry = EmailNotificationLog(
            recipient_email=clean_to,
            institution_id=institution_id,
            subject=subject,
            email_type=email_type,
            fdr_id=fdr_id,
            request_id=request_id,
            reminder_interval_days=reminder_interval_days,
            status="SENT" if smtp_success else "FAILED",
            error_message=None if smtp_success else (smtp_error[:500] if smtp_error else None),
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as db_exc:
        db.session.rollback()
        logger.warning(
            "Email %s for %s, but failed to record audit log: %s",
            "delivered via SMTP" if smtp_success else "failed via SMTP",
            clean_to,
            db_exc,
        )

    return smtp_success


# =========================================================================
# High-Level Workflow Email Notifications
# =========================================================================


def _resolve_request_context(fdr_request: Optional[FDRRequest]) -> tuple[Optional[Institution], Optional[FDRRecord]]:
    """Safely resolve Institution and FDRRecord from an FDRRequest instance."""
    if not fdr_request:
        return None, None

    inst = getattr(fdr_request, "institution", None)
    if not inst and getattr(fdr_request, "institution_id", None):
        inst = db.session.get(Institution, fdr_request.institution_id)

    fdr = getattr(fdr_request, "fdr", None)
    if not fdr and getattr(fdr_request, "fdr_id", None):
        fdr = db.session.get(FDRRecord, fdr_request.fdr_id)

    if not inst and fdr:
        inst = getattr(fdr, "institution", None)
        if not inst and getattr(fdr, "institution_id", None):
            inst = db.session.get(Institution, fdr.institution_id)

    return inst, fdr


def send_fdr_maturity_email(
    fdr: FDRRecord,
    days_remaining: int,
    as_of_date: Optional[Any] = None,
) -> int:
    """
    Send statutory FDR maturity notice to registered institution email addresses.
    Strictly checks that an email for this (fdr.id, days_remaining) was not already sent.
    Returns number of emails delivered.
    """
    if not fdr:
        return 0

    inst = getattr(fdr, "institution", None)
    if not inst and getattr(fdr, "institution_id", None):
        inst = db.session.get(Institution, fdr.institution_id)
    if not inst:
        return 0

    if is_fdr_reminder_already_sent(fdr.id, days_remaining):
        logger.info(
            "FDR %s reminder for %d days remaining already sent. Skipping duplicate.",
            fdr.fdr_number,
            days_remaining,
        )
        return 0

    inst = fdr.institution
    recipients = get_institution_emails(inst)
    if not recipients:
        logger.warning("No valid recipient email addresses for institution %s", inst.name)
        return 0

    urgency_tag = "URGENT" if days_remaining <= 7 else "Notice"
    subject = f"[{urgency_tag}] AICTE Security Deposit Maturity Reminder: FDR {fdr.fdr_number} ({days_remaining} Days Remaining)"
    if days_remaining == 0:
        subject = f"[ACTION REQUIRED] AICTE Security Deposit Matured Today: FDR {fdr.fdr_number}"

    preheader = (
        f"FDR deposit reaches term TODAY ({fdr.maturity_date.isoformat()}). Immediate action required."
        if days_remaining == 0
        else f"FDR deposit reaches term on {fdr.maturity_date.isoformat()}. Action required."
    )

    key_details = [
        ("Institution Code", inst.institution_code),
        ("FDR Number", fdr.fdr_number),
        ("Issuing Commercial Bank", f"{fdr.bank_name} ({fdr.branch_name or 'Main Branch'})"),
        ("Deposit Amount", f"INR {float(fdr.amount):,.2f}"),
        ("Official Maturity Date", fdr.maturity_date.isoformat()),
        ("Days Remaining", "0 Day(s) — Matures Today" if days_remaining == 0 else f"{days_remaining} Day(s)"),
        ("Current Status", fdr.validity_status),
    ]

    maturity_notice_lead = (
        f"This is an automated statutory notice regarding Fixed Deposit Receipt {fdr.fdr_number} "
        f"held as AICTE Security Deposit with {fdr.bank_name}. The deposit reaches maturity "
        f"<strong>TODAY ({fdr.maturity_date.isoformat()})</strong>."
        if days_remaining == 0
        else f"This is an automated statutory notice regarding Fixed Deposit Receipt {fdr.fdr_number} "
        f"held as AICTE Security Deposit with {fdr.bank_name}. The deposit will reach maturity in "
        f"<strong>{days_remaining} day(s)</strong> on <strong>{fdr.maturity_date.isoformat()}</strong>."
    )

    paragraphs = [
        maturity_notice_lead,
        (
            "Under AICTE Approval Process Handbook (APH) regulations, institutional security deposits "
            "must remain continuously renewed or settled via authorized AICTE release petitions."
        ),
        (
            "Please log in to the portal and submit a renewal petition along with confirmation of your intent "
            "to renew with the issuing commercial bank."
        ),
    ]

    body_html = _build_html_template(
        title="Security Deposit Matured Today — Action Required" if days_remaining == 0 else f"Security Deposit Maturity Notice — {days_remaining} Days Remaining",
        preheader=preheader,
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
    )

    body_text = (
        f"AICTE Security Deposit Maturity Reminder\n\n"
        f"Institution: {inst.name} ({inst.institution_code})\n"
        f"FDR Number: {fdr.fdr_number}\n"
        f"Bank: {fdr.bank_name}\n"
        f"Amount: INR {float(fdr.amount):,.2f}\n"
        f"Maturity Date: {fdr.maturity_date.isoformat()}\n"
        f"Days Remaining: {'0 (Matures Today)' if days_remaining == 0 else str(days_remaining)}\n\n"
        f"Please log in to the AICTE FDR Portal to submit your statutory renewal petition."
    )

    sent_count = 0
    for email_addr in recipients:
        success = send_email(
            to_email=email_addr,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type="FDR_MATURITY_REMINDER",
            fdr_id=fdr.id,
            institution_id=inst.id,
            reminder_interval_days=days_remaining,
        )
        if success:
            sent_count += 1

    return sent_count


def send_petition_status_email(
    fdr_request: FDRRequest,
    new_status: str,
    remarks: Optional[str] = None,
) -> int:
    """
    Send email when petition status changes:
    - Submitted
    - Approved
    - Rejected
    - Under Review
    - Documents Required
    - Resubmitted / Awaiting Review
    """
    inst, fdr = _resolve_request_context(fdr_request)
    if not inst:
        return 0

    fdr_num = fdr.fdr_number if fdr else "N/A"
    req_formatted = f"REQ-{fdr_request.id:04d}"

    recipients = get_institution_emails(inst)
    if not recipients:
        return 0

    status_tag = new_status.upper()
    subject = f"AICTE Petition Update: {req_formatted} Status Changed to '{new_status}' (FDR {fdr_num})"

    key_details = [
        ("Petition ID", req_formatted),
        ("Petition Type", fdr_request.request_type),
        ("FDR Number", fdr_num),
        ("Updated Status", new_status),
        ("AICTE Officer Remarks", remarks or "None recorded"),
        ("Submission Date", fdr_request.created_at.strftime("%Y-%m-%d") if fdr_request.created_at else "N/A"),
    ]

    status_instructions = {
        "Submitted": (
            f"Your {fdr_request.request_type} petition has been successfully registered and queued for AICTE desk scrutiny. "
            "An AICTE Scrutiny Officer will review your submission."
        ),
        "Approved": (
            "Your renewal petition has been reviewed and <strong>Approved</strong> by the AICTE Scrutiny Bureau. "
            "Please proceed with the bank renewal and upload the verified renewed FDR receipt."
        ),
        "Under Review": (
            "Your petition is currently <strong>Under Review</strong> by an assigned AICTE Scrutiny Officer. "
            "You will be notified once a formal decision is reached."
        ),
        "Documents Required": (
            "The AICTE Scrutiny Officer has issued a deficiency notice requiring additional documentation. "
            "Please inspect the officer remarks and resubmit the requested documentation promptly."
        ),
        "Resubmitted / Awaiting Review": (
            "Your resubmission with additional documentation has been received and queued for officer re-evaluation."
        ),
        "Rejected": (
            "Your petition has been <strong>Rejected</strong> following administrative review. "
            "Please review the stated remarks."
        ),
    }

    instruction_text = status_instructions.get(
        new_status,
        f"The status of your {fdr_request.request_type} petition has transitioned to '{new_status}'.",
    )

    paragraphs = [
        (
            f"This is an official administrative update regarding {fdr_request.request_type} petition "
            f"<strong>{req_formatted}</strong> for Fixed Deposit Receipt <strong>{fdr_num}</strong>."
        ),
        instruction_text,
    ]

    if remarks:
        paragraphs.append(f"<strong>Officer Remarks:</strong> {remarks}")

    body_html = _build_html_template(
        title=f"Petition Status Update: {new_status}",
        preheader=f"Petition {req_formatted} status changed to {new_status}.",
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
    )

    body_text = (
        f"AICTE Petition Status Update\n\n"
        f"Institution: {inst.name}\n"
        f"Petition: {req_formatted} ({fdr_request.request_type})\n"
        f"FDR Number: {fdr_num}\n"
        f"Status: {new_status}\n"
        f"Remarks: {remarks or 'None'}\n\n"
        f"Log in to the AICTE portal to view details and required actions."
    )

    sent = 0
    for r in recipients:
        if send_email(
            to_email=r,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type="PETITION_STATUS_CHANGED",
            fdr_id=fdr_request.fdr_id,
            request_id=fdr_request.id,
            institution_id=inst.id,
        ):
            sent += 1
    return sent


def send_renewal_receipt_required_email(fdr_request: FDRRequest) -> int:
    """
    Notify the institution that their renewal petition was approved and they must
    now upload the renewed FDR receipt from their commercial bank.
    """
    inst, fdr = _resolve_request_context(fdr_request)
    if not inst:
        return 0

    fdr_num = fdr.fdr_number if fdr else "N/A"
    req_formatted = f"REQ-{fdr_request.id:04d}"

    recipients = get_institution_emails(inst)
    if not recipients:
        return 0

    subject = f"[ACTION REQUIRED] Upload Renewed FDR Receipt: {fdr_num} (Petition {req_formatted})"
    preheader = "Renewal petition approved. Submission of renewed bank deposit receipt required."

    key_details = [
        ("Petition ID", req_formatted),
        ("FDR Number", fdr_num),
        ("Issuing Commercial Bank", fdr.bank_name if fdr else "N/A"),
        ("Official Maturity Date", fdr.maturity_date.isoformat() if fdr else "N/A"),
        ("Current Step", "Awaiting Renewed Deposit Receipt"),
    ]

    paragraphs = [
        (
            f"Your renewal petition for FDR <strong>{fdr_num}</strong> has been approved by AICTE. "
            "To complete the renewal workflow and officially extend the security deposit maturity date, "
            "you must provide proof of deposit renewal from your issuing commercial bank."
        ),
        (
            "Please upload the renewed Fixed Deposit Receipt / Certificate containing the new FDR number, "
            "renewed issue date, new extended maturity date, and renewed deposit amount."
        ),
        (
            "<strong>Important Statutory Rule:</strong> The official FDR maturity date in the AICTE registry "
            "remains unchanged until an authorized scrutiny officer verifies your renewed receipt."
        ),
    ]

    body_html = _build_html_template(
        title="Renewed FDR Receipt Required",
        preheader=preheader,
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
    )

    body_text = (
        f"ACTION REQUIRED: Upload Renewed FDR Receipt\n\n"
        f"Institution: {inst.name}\n"
        f"Petition: {req_formatted}\n"
        f"FDR Number: {fdr_num}\n\n"
        f"Your renewal petition is approved. Please renew the deposit with your commercial bank "
        f"and upload the renewed FDR certificate on the AICTE portal."
    )

    sent = 0
    for r in recipients:
        if send_email(
            to_email=r,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type="RENEWAL_RECEIPT_REQUIRED",
            fdr_id=fdr_request.fdr_id,
            request_id=fdr_request.id,
            institution_id=inst.id,
        ):
            sent += 1
    return sent


def send_renewal_receipt_reminder_email(
    fdr_request: FDRRequest,
    milestone_days: int = 7,
) -> int:
    """
    Follow-up reminder to institution when approved renewal receipt has not been uploaded
    and submission deadline is approaching.
    """
    inst, fdr = _resolve_request_context(fdr_request)
    if not inst:
        return 0

    milestone_key = f"{milestone_days}D"
    if is_receipt_reminder_already_sent(fdr_request.id, milestone_key):
        return 0

    fdr_num = fdr.fdr_number if fdr else "N/A"
    req_formatted = f"REQ-{fdr_request.id:04d}"

    recipients = get_institution_emails(inst)
    if not recipients:
        return 0

    subject = f"[REMINDER] Pending Renewed FDR Receipt Submission: {fdr_num} ({req_formatted})"
    preheader = f"It has been {milestone_days} days since petition approval. Bank receipt upload is due."

    key_details = [
        ("Petition ID", req_formatted),
        ("FDR Number", fdr_num),
        ("Issuing Commercial Bank", fdr.bank_name if fdr else "N/A"),
        ("Current Step", "Awaiting Renewed Deposit Receipt"),
        ("Elapsed Time", f"{milestone_days} days since approval"),
    ]

    paragraphs = [
        (
            f"This is a follow-up reminder that your renewal petition for FDR <strong>{fdr_num}</strong> "
            "was approved, but the renewed deposit receipt has not yet been uploaded to the portal."
        ),
        (
            "Please ensure the deposit renewal has been executed with your issuing commercial bank and upload "
            "the renewed receipt to avoid statutory non-compliance or forfeiture actions."
        ),
    ]

    body_html = _build_html_template(
        title="Pending Renewal Receipt Reminder",
        preheader=preheader,
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
    )

    body_text = (
        f"REMINDER: Upload Renewed FDR Receipt\n\n"
        f"Institution: {inst.name}\n"
        f"Petition: {req_formatted}\n"
        f"FDR Number: {fdr_num}\n\n"
        f"It has been {milestone_days} days since petition approval. Please upload the renewed receipt."
    )

    sent = 0
    for r in recipients:
        if send_email(
            to_email=r,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type=f"RENEWAL_RECEIPT_REMINDER_{milestone_key}",
            fdr_id=fdr_request.fdr_id,
            request_id=fdr_request.id,
            institution_id=inst.id,
        ):
            sent += 1
    return sent


def scan_and_send_receipt_reminders(as_of_date: Optional[Any] = None) -> int:
    """
    Scan approved renewal petitions lacking receipt uploads and send 7-day and 14-day reminders.
    """
    from datetime import date
    today = as_of_date or date.today()
    if isinstance(today, datetime):
        today = today.date()

    approved_renewals = FDRRequest.query.filter(
        FDRRequest.request_type == "Renewal",
        FDRRequest.status == "Approved",
        FDRRequest.renewal_submitted_at == None,  # noqa: E711
    ).all()

    total_sent = 0
    for req in approved_renewals:
        # Determine days elapsed since approval (or creation)
        ref_dt = req.updated_at or req.created_at
        if not ref_dt:
            continue
        approval_date = ref_dt.date() if isinstance(ref_dt, datetime) else ref_dt
        days_elapsed = (today - approval_date).days

        if days_elapsed >= 14:
            total_sent += send_renewal_receipt_reminder_email(req, milestone_days=14)
        elif days_elapsed >= 7:
            total_sent += send_renewal_receipt_reminder_email(req, milestone_days=7)

    return total_sent


def send_receipt_verification_email(
    fdr_request: FDRRequest,
    decision: str,
    remarks: Optional[str] = None,
) -> int:
    """
    Notify the institution when its uploaded renewal receipt is verified, rejected,
    or returned for corrections.
    """
    inst, fdr = _resolve_request_context(fdr_request)
    if not inst:
        return 0

    fdr_num = fdr.fdr_number if fdr else "N/A"
    req_formatted = f"REQ-{fdr_request.id:04d}"

    recipients = get_institution_emails(inst)
    if not recipients:
        return 0

    clean_dec = decision.upper()
    if clean_dec == "VERIFIED":
        subject = f"[CONFIRMED] Renewed FDR Receipt Verified & Endorsed: {fdr_num} ({req_formatted})"
        title = "Renewal Receipt Verified & Endorsed"
        preheader = "AICTE scrutiny officer has verified and endorsed your renewed security deposit."
        email_type = "RENEWAL_RECEIPT_VERIFIED"
        paragraphs = [
            f"The renewed Fixed Deposit Receipt submitted under petition <strong>{req_formatted}</strong> "
            f"has been verified against AICTE statutory covenants and endorsed by the Scrutiny Officer.",
            "The official institutional registry has been updated with the verified renewed deposit parameters.",
        ]
    elif clean_dec == "RETURNED":
        subject = f"[CORRECTIONS REQUIRED] Renewed FDR Receipt Returned: {fdr_num} ({req_formatted})"
        title = "Renewed Receipt Returned for Corrections"
        preheader = "Deficiencies noted in uploaded renewed deposit certificate."
        email_type = "RENEWAL_RECEIPT_RETURNED"
        paragraphs = [
            f"The renewed Fixed Deposit Receipt submitted under petition <strong>{req_formatted}</strong> "
            "could not be endorsed due to documentation or term discrepancies.",
            f"<strong>Deficiency Remarks:</strong> {remarks or 'Please see portal annotations.'}",
            "Please review the remarks and upload a clear, corrected certificate from your bank.",
        ]
    else:  # REJECTED
        subject = f"[REJECTED] Renewed FDR Evidence Rejected: {fdr_num} ({req_formatted})"
        title = "Renewed Receipt Evidence Rejected"
        preheader = "Submitted renewal documentation was rejected by the scrutiny bureau."
        email_type = "RENEWAL_RECEIPT_REJECTED"
        paragraphs = [
            f"The renewal evidence submitted under petition <strong>{req_formatted}</strong> has been rejected.",
            f"<strong>Official Reason:</strong> {remarks or 'Non-compliant documentation.'}",
        ]

    key_details = [
        ("Petition ID", req_formatted),
        ("FDR Number", fdr_num),
        ("Verification Decision", clean_dec),
        ("Officer Remarks", remarks or "None"),
    ]

    body_html = _build_html_template(
        title=title,
        preheader=preheader,
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
    )

    body_text = (
        f"AICTE Renewal Receipt Verification: {clean_dec}\n\n"
        f"Institution: {inst.name}\n"
        f"Petition: {req_formatted}\n"
        f"FDR Number: {fdr_num}\n"
        f"Remarks: {remarks or 'None'}\n"
    )

    sent = 0
    for r in recipients:
        if send_email(
            to_email=r,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type=email_type,
            fdr_id=fdr_request.fdr_id,
            request_id=fdr_request.id,
            institution_id=inst.id,
        ):
            sent += 1
    return sent


def send_renewal_completed_email(
    fdr_request: FDRRequest,
    fdr: FDRRecord,
    old_mat_date: Optional[Any] = None,
    new_mat_date: Optional[Any] = None,
) -> int:
    """
    Send final confirmation when the renewal workflow is officially complete and
    the FDR record's maturity date has been extended in the authoritative registry.
    """
    if not fdr or not fdr.institution:
        return 0

    inst = fdr.institution
    recipients = get_institution_emails(inst)
    if not recipients:
        return 0

    req_formatted = f"REQ-{fdr_request.id:04d}" if fdr_request else "N/A"
    subject = f"[SUCCESS] FDR Renewal Completed: FDR {fdr.fdr_number} Officially Extended"
    preheader = f"Security deposit officially renewed to {fdr.maturity_date.isoformat()}."

    key_details = [
        ("FDR Number", fdr.fdr_number),
        ("Institution", f"{inst.name} ({inst.institution_code})"),
        ("Issuing Commercial Bank", f"{fdr.bank_name} ({fdr.branch_name or 'Main'})"),
        ("Deposit Amount", f"INR {float(fdr.amount):,.2f}"),
        ("Previous Maturity Date", str(old_mat_date or "N/A")),
        ("New Official Maturity Date", fdr.maturity_date.isoformat()),
        ("Statutory Validity Status", fdr.validity_status),
        ("Workflow Petition", req_formatted),
    ]

    paragraphs = [
        (
            f"The statutory renewal workflow for Fixed Deposit Receipt <strong>{fdr.fdr_number}</strong> "
            "has been successfully concluded."
        ),
        (
            f"The official maturity date has been formally extended in the central AICTE registry "
            f"to <strong>{fdr.maturity_date.isoformat()}</strong>. Your institutional compliance record "
            "has been updated."
        ),
        "Historical term records have been permanently archived in the institutional audit trail.",
    ]

    body_html = _build_html_template(
        title="FDR Renewal Workflow Completed",
        preheader=preheader,
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
    )

    body_text = (
        f"AICTE FDR Renewal Completed\n\n"
        f"Institution: {inst.name} ({inst.institution_code})\n"
        f"FDR Number: {fdr.fdr_number}\n"
        f"Bank: {fdr.bank_name}\n"
        f"New Official Maturity Date: {fdr.maturity_date.isoformat()}\n"
        f"Validity Status: {fdr.validity_status}\n\n"
        f"The official security deposit record has been successfully updated."
    )

    sent = 0
    for r in recipients:
        if send_email(
            to_email=r,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type="RENEWAL_COMPLETED",
            fdr_id=fdr.id,
            request_id=fdr_request.id if fdr_request else None,
            institution_id=inst.id,
        ):
            sent += 1
    return sent


class TestEmailResult(dict):
    """Result object supporting dict access, attribute access, and tuple unpacking: (success, message)."""

    def __iter__(self):
        yield self.get("success", False)
        yield self.get("message", "")

    def __getitem__(self, key):
        if isinstance(key, int):
            if key == 0:
                return self.get("success", False)
            elif key == 1:
                return self.get("message", "")
            raise IndexError("TestEmailResult index out of range")
        return super().__getitem__(key)

    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'TestEmailResult' object has no attribute '{key}'")


def send_test_email(recipient_email: str) -> TestEmailResult:
    """
    Diagnostic helper to verify SMTP credentials and server connectivity.
    Sends a safe test message to a specified single recipient.
    Separates SMTP server delivery from database audit logging status.
    """
    clean_to = str(recipient_email or "").strip().lower()
    if not is_valid_email(clean_to):
        return TestEmailResult({
            "success": False,
            "smtp_success": False,
            "db_logged": False,
            "message": f"Invalid test recipient address: '{recipient_email}'",
            "smtp_error": "INVALID_EMAIL",
            "db_error": None,
        })

    subject = "[TEST] AICTE FDR Management Portal SMTP Diagnostics"
    body_text = (
        "AICTE Security Deposit Portal - SMTP Diagnostic Verification\n\n"
        "This message confirms that your Gmail SMTP server configuration (smtp.gmail.com:587 TLS) "
        "is correctly configured and able to dispatch statutory administrative notices.\n\n"
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
    )

    paragraphs = [
        "This is an automated diagnostic test message generated by the AICTE FDR Management Portal.",
        "Your SMTP mail server configuration, credentials, and TLS encryption handshake were successfully validated.",
        f"<strong>Timestamp:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]

    body_html = _build_html_template(
        title="SMTP Diagnostics Test",
        preheader="Verification of automated email delivery capability.",
        institution_name="System Administrator / Test User",
        key_details=[
            ("Diagnostic Status", "SUCCESS"),
            ("SMTP Gateway", "Gmail SMTP (Port 587 TLS)"),
            ("Target Recipient", clean_to),
        ],
        message_paragraphs=paragraphs,
    )

    app = current_app._get_current_object()  # type: ignore[attr-defined]
    config = app.config

    server_host = config.get("MAIL_SERVER", "smtp.gmail.com")
    server_port = int(config.get("MAIL_PORT", 587))
    use_tls = bool(config.get("MAIL_USE_TLS", True))
    use_ssl = bool(config.get("MAIL_USE_SSL", False))
    username = config.get("MAIL_USERNAME", "")
    password = config.get("MAIL_PASSWORD", "")
    default_sender = config.get("MAIL_DEFAULT_SENDER", username or "AICTE FDR Portal <noreply@aicte.gov.in>")

    is_testing = bool(config.get("TESTING", False))
    is_suppressed = bool(config.get("MAIL_SUPPRESS_SEND", False))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = default_sender
    msg["To"] = clean_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # Stage 1: Live SMTP dispatch (or mock if testing/suppressed)
    smtp_success = False
    smtp_error = None

    if is_testing or is_suppressed:
        logger.info("[MOCK TEST EMAIL] Suppressed live SMTP dispatch for test to %s", clean_to)
        smtp_success = True
    else:
        try:
            if use_ssl:
                smtp_client = smtplib.SMTP_SSL(server_host, server_port, timeout=12)
            else:
                smtp_client = smtplib.SMTP(server_host, server_port, timeout=12)

            with smtp_client:
                smtp_client.ehlo()
                if use_tls and not use_ssl:
                    smtp_client.starttls()
                    smtp_client.ehlo()
                if username and password:
                    smtp_client.login(username, password)
                smtp_client.send_message(msg)

            smtp_success = True
            logger.info("Successfully delivered diagnostic test email to %s via SMTP", clean_to)
        except Exception as exc:
            smtp_success = False
            smtp_error = str(exc)
            logger.error("SMTP delivery failed for test email to %s: %s", clean_to, smtp_error)

    # Stage 2: Database audit logging (isolated transaction)
    db_logged = False
    db_error = None
    try:
        from app.services.migration_service import ensure_schema_updates
        ensure_schema_updates()

        log_entry = EmailNotificationLog(
            recipient_email=clean_to,
            institution_id=None,
            subject=subject,
            email_type="TEST_EMAIL",
            fdr_id=None,
            request_id=None,
            reminder_interval_days=None,
            status="SENT" if smtp_success else "FAILED",
            error_message=None if smtp_success else (smtp_error[:500] if smtp_error else None),
        )
        db.session.add(log_entry)
        db.session.commit()
        db_logged = True
    except Exception as exc:
        db.session.rollback()
        db_error = str(exc)
        logger.warning("Test email DB logging warning: %s", db_error)

    if smtp_success and db_logged:
        msg_str = f"Test email successfully dispatched to {clean_to} via SMTP and recorded in email_notification_logs."
    elif smtp_success and not db_logged:
        msg_str = f"Test email was successfully delivered to {clean_to} via SMTP, but database audit logging encountered a warning: {db_error}"
    else:
        msg_str = f"SMTP delivery failed to {clean_to}: {smtp_error}"

    return TestEmailResult({
        "success": smtp_success,
        "smtp_success": smtp_success,
        "db_logged": db_logged,
        "message": msg_str,
        "smtp_error": smtp_error,
        "db_error": db_error,
    })


def resolve_fdr_recipients(fdr: FDRRecord) -> tuple[Optional[Institution], list[str]]:
    """
    Resolve institution entity and all valid email recipients for an FDR:
    1. Primary institutional contact email.
    2. Active institutional user accounts linked to this institution.
    3. The specific user who created/submitted the FDR.
    Never uses hardcoded test email addresses.
    """
    inst = fdr.institution
    if not inst and fdr.institution_id:
        inst = db.session.get(Institution, fdr.institution_id)

    if not inst:
        return None, []

    recipients_set: set[str] = set()

    # 1. Primary institutional contact email
    if is_valid_email(inst.contact_email):
        recipients_set.add(inst.contact_email.strip().lower())

    # 2. Active institutional users linked to this college
    if hasattr(inst, "users") and inst.users:
        for u in inst.users:
            if getattr(u, "is_active", True) and is_valid_email(u.email):
                recipients_set.add(u.email.strip().lower())

    # 3. Creator of the FDR record if active user
    if fdr.creator and getattr(fdr.creator, "is_active", True) and is_valid_email(fdr.creator.email):
        recipients_set.add(fdr.creator.email.strip().lower())

    return inst, sorted(list(recipients_set))


def send_fdr_scrutiny_status_email(
    fdr: FDRRecord,
    new_status: str,
    previous_status: Optional[str] = None,
    remarks: Optional[str] = None,
    actor: Optional[Any] = None,
) -> int:
    """
    Send statutory notification email when an FDR's scrutiny status transitions:
    - RETURNED (Deficiency Notice - Officer requests corrections)
    - VERIFIED (FDR approved by AICTE Scrutiny Desk)
    - REJECTED (FDR submission rejected)
    - SUBMITTED (FDR submitted or resubmitted by institution)

    Guarantees:
    - Resolves recipient dynamically from the verified institution record.
    - Never hardcodes email addresses.
    - Accurately states status (e.g. clearly states corrections are required, never claims approval).
    - Email failure is non-blocking (does not roll back DB transaction).
    - Records audit log entry with status (SENT or FAILED).
    """
    inst, recipients = resolve_fdr_recipients(fdr)
    if not inst:
        logger.warning(
            "Cannot send scrutiny status email for FDR %s: Institution not found (inst_id=%s)",
            fdr.fdr_number,
            fdr.institution_id,
        )
        return 0

    if not recipients:
        logger.warning(
            "Cannot send scrutiny status email for FDR %s: No valid registered email addresses found for institution '%s' (ID %s)",
            fdr.fdr_number,
            inst.name,
            inst.id,
        )
        return 0

    fdr_num = fdr.fdr_number or "N/A"
    clean_remarks = (remarks or "").strip()
    actor_name = getattr(actor, "full_name", None) or "AICTE Scrutiny Desk"

    key_details = [
        ("FDR Reference Number", fdr_num),
        ("Issuing Commercial Bank", fdr.bank_name or "N/A"),
        ("Branch", fdr.branch_name or "N/A"),
        ("Deposit Principal Amount", f"INR {float(fdr.amount):,.2f}" if fdr.amount is not None else "N/A"),
        ("Official Maturity Date", fdr.maturity_date.isoformat() if fdr.maturity_date else "N/A"),
        ("Scrutiny Decision", new_status),
    ]

    action_url = "http://localhost:5173/fdrs"

    if new_status == "RETURNED":
        email_type = "FDR_DEFICIENCY_CORRECTION_REQUIRED"
        subject = f"Action Required: Corrections Needed for Your FDR Submission ({fdr_num})"
        title = "Deficiency Notice — Corrections Required for FDR Submission"
        preheader = f"AICTE Scrutiny Desk has returned FDR {fdr_num} for correction."

        key_details.append(("Deficiency Reason", clean_remarks if clean_remarks else "Deficiencies noted in uploaded document or deposit parameters."))
        key_details.append(("Reviewing Officer", actor_name))

        paragraphs = [
            (
                f"Your Fixed Deposit Receipt submission <strong>{fdr_num}</strong> has been scrutinized by the AICTE Scrutiny Desk and "
                "<strong>returned for correction</strong> due to deficiency items identified during verification."
            ),
            (
                f"<strong>Deficiency Remarks from Scrutiny Desk:</strong><br>"
                f"<span style='color: #B91C1C; font-weight: 600;'>{clean_remarks if clean_remarks else 'Uploaded supporting receipt is deficient, expired, or non-compliant.'}</span>"
            ),
            (
                "<strong>Important Compliance Notice:</strong> This FDR has <strong>NOT</strong> been approved or verified. "
                "The submission is currently in deficiency status and statutory compliance remains unresolved."
            ),
            (
                "<strong>Required Next Steps:</strong><br>"
                "1. Log in to the official AICTE Security Deposit Portal.<br>"
                f"2. Navigate to FDR details for <strong>{fdr_num}</strong>.<br>"
                "3. Review the detailed deficiency findings.<br>"
                "4. Upload the corrected, active, unexpired bank FDR receipt and resubmit for verification."
            ),
        ]
        action_button = ("Log In to Correct & Resubmit FDR", action_url)

    elif new_status == "VERIFIED":
        email_type = "FDR_SCRUTINY_VERIFIED"
        subject = f"AICTE Security Deposit Verified: FDR {fdr_num} Approved"
        title = "FDR Verified & Approved by AICTE"
        preheader = f"Fixed Deposit Receipt {fdr_num} has been verified and approved."

        if clean_remarks:
            key_details.append(("Officer Remarks", clean_remarks))
        key_details.append(("Endorsing Officer", actor_name))

        paragraphs = [
            (
                f"Your Fixed Deposit Receipt submission <strong>{fdr_num}</strong> has been officially "
                "<strong>verified and approved</strong> by the AICTE Scrutiny Bureau."
            ),
            (
                "All deposit terms, joint lien clauses, and commercial bank parameters have been confirmed "
                "against AICTE Approval Process Handbook guidelines."
            ),
            f"Officer Remarks: {clean_remarks}" if clean_remarks else "Official verification status is active.",
        ]
        action_button = ("View Verified FDR Details", action_url)

    elif new_status == "REJECTED":
        email_type = "FDR_SCRUTINY_REJECTED"
        subject = f"AICTE Security Deposit Notice: FDR {fdr_num} Rejected"
        title = "FDR Submission Rejected by AICTE"
        preheader = f"Fixed Deposit Receipt {fdr_num} has been rejected."

        key_details.append(("Rejection Reason", clean_remarks if clean_remarks else "Deposit terms or supporting documentation non-compliant."))
        key_details.append(("Decision Authority", actor_name))

        paragraphs = [
            (
                f"Your Fixed Deposit Receipt submission <strong>{fdr_num}</strong> has been "
                "<strong>rejected</strong> following administrative scrutiny by AICTE."
            ),
            (
                f"<strong>Stated Reason for Rejection:</strong><br>"
                f"<span style='color: #B91C1C;'>{clean_remarks if clean_remarks else 'Non-compliant with mandatory AICTE statutory terms.'}</span>"
            ),
            (
                "Please consult your regional AICTE bureau or legal advisor regarding regulatory next steps."
            ),
        ]
        action_button = ("Log In to Portal", action_url)

    elif new_status == "SUBMITTED":
        action_verb = "Resubmitted" if previous_status == "RETURNED" else "Submitted"
        email_type = "FDR_SCRUTINY_RESUBMITTED" if previous_status == "RETURNED" else "FDR_SCRUTINY_SUBMITTED"
        subject = f"FDR {action_verb} for AICTE Scrutiny: {fdr_num}"
        title = f"FDR Successfully {action_verb} for Scrutiny"
        preheader = f"Fixed Deposit Receipt {fdr_num} is queued for scrutiny."

        paragraphs = [
            (
                f"Your Fixed Deposit Receipt <strong>{fdr_num}</strong> of <strong>{fdr.bank_name or 'Commercial Bank'}</strong> "
                f"has been successfully {action_verb.lower()} and queued for official scrutiny review by the AICTE Scrutiny Cell."
            ),
            (
                "An assigned AICTE officer will evaluate your submission, verify the bank lien clause, "
                "and endorse the deposit in the statutory registry."
            ),
        ]
        action_button = ("Track Submission Status", action_url)

    else:
        # Generic fallback for other transitions (e.g. PENDING_VERIFICATION)
        email_type = f"FDR_SCRUTINY_{new_status}"
        subject = f"AICTE FDR Scrutiny Update: {fdr_num} Status is '{new_status}'"
        title = f"FDR Scrutiny Status: {new_status}"
        preheader = f"FDR {fdr_num} status changed to {new_status}."
        paragraphs = [
            f"The scrutiny review status of FDR <strong>{fdr_num}</strong> has transitioned to <strong>{new_status}</strong>.",
            f"Remarks: {clean_remarks}" if clean_remarks else "Official verification in progress.",
        ]
        action_button = ("View FDR Details", action_url)

    body_html = _build_html_template(
        title=title,
        preheader=preheader,
        institution_name=inst.name,
        key_details=key_details,
        message_paragraphs=paragraphs,
        action_button=action_button,
    )

    body_text_lines = [
        "AICTE Security Deposit & FDR Management Portal",
        f"Notice: {title}",
        "--------------------------------------------------",
        f"Institution: {inst.name} ({inst.institution_code})",
        f"FDR Number: {fdr_num}",
        f"Bank: {fdr.bank_name or 'N/A'}",
        f"Amount: INR {float(fdr.amount):,.2f}" if fdr.amount is not None else "Amount: N/A",
        f"Scrutiny Status: {new_status}",
    ]
    if clean_remarks:
        body_text_lines.append(f"Remarks / Deficiency Reason: {clean_remarks}")
    body_text_lines.append("")
    body_text_lines.append("Please log in to the portal to view details and required actions:")
    body_text_lines.append(action_url)
    body_text = "\n".join(body_text_lines)

    sent_count = 0
    for recipient in recipients:
        success = send_email(
            to_email=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type=email_type,
            fdr_id=fdr.id,
            institution_id=inst.id,
        )
        if success:
            sent_count += 1

    return sent_count


def retry_email_notification(log_id: int) -> tuple[bool, str]:
    """
    Safely retry a failed email notification by ID.
    Guarantees:
    - Never resends if status is already 'SENT' (prevents duplicate delivery).
    - Logs new attempt or updates log.
    - Safe error handling without crashing.
    """
    log = db.session.get(EmailNotificationLog, log_id)
    if not log:
        return False, "Email notification log entry not found."

    if log.status == "SENT":
        return True, "Notification was already successfully delivered previously (duplicate delivery skipped)."

    fdr = log.fdr
    req = log.request

    if fdr:
        if "DEFICIENCY" in log.email_type or "RETURNED" in log.email_type:
            remarks = "Deficiency correction required."
            from app.models.workflow_history import FDRWorkflowHistory
            last_hist = FDRWorkflowHistory.query.filter_by(fdr_id=fdr.id, to_status="RETURNED").order_by(FDRWorkflowHistory.id.desc()).first()
            if last_hist and last_hist.remarks:
                remarks = last_hist.remarks
            sent = send_fdr_scrutiny_status_email(fdr, "RETURNED", remarks=remarks)
            return (sent > 0), f"Resent deficiency notice to {sent} recipient(s)." if sent > 0 else "Failed to redeliver email."
        elif "MATURITY" in log.email_type:
            sent = send_fdr_maturity_email(fdr, log.reminder_interval_days or 0)
            return (sent > 0), f"Resent maturity reminder to {sent} recipient(s)." if sent > 0 else "Failed to redeliver email."
        elif "VERIFIED" in log.email_type:
            sent = send_fdr_scrutiny_status_email(fdr, "VERIFIED")
            return (sent > 0), f"Resent verification notice to {sent} recipient(s)." if sent > 0 else "Failed to redeliver email."

    if req:
        sent = send_petition_status_email(req, req.status, remarks=req.remarks)
        return (sent > 0), f"Resent petition update to {sent} recipient(s)." if sent > 0 else "Failed to redeliver email."

    # Direct re-dispatch
    success = send_email(
        to_email=log.recipient_email,
        subject=log.subject,
        body_text=f"AICTE Portal Statutory Notification: {log.subject}",
        email_type=log.email_type,
        fdr_id=log.fdr_id,
        request_id=log.request_id,
        institution_id=log.institution_id,
        reminder_interval_days=log.reminder_interval_days,
    )
    return success, "Email delivered successfully via SMTP." if success else "SMTP retry failed."

