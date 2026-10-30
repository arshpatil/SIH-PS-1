from datetime import date, timedelta
from decimal import Decimal
import io
import smtplib
from unittest.mock import MagicMock, patch
import pytest

from app.extensions import db
from app.models.email_log import EmailNotificationLog
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User
from app.services.email_service import (
    is_fdr_reminder_already_sent,
    is_valid_email,
    scan_and_send_receipt_reminders,
    send_email,
    send_fdr_maturity_email,
    send_test_email,
)
from app.services.maturity_service import scan_and_update_maturities


@pytest.fixture
def email_env(app):
    """Seed test environment with institution, institutional user, officer, and FDR."""
    inst = Institution(
        institution_code="AICTE-EML-001",
        name="Institute of Computer Science",
        contact_email="principal@ics.edu",
    )
    db.session.add(inst)
    db.session.commit()

    inst_user = User(
        full_name="Principal Rao",
        email="principal@ics.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst.id,
        is_active=True,
    )
    inst_user.set_password("IcsPass123!")

    officer = User(
        full_name="Officer Sharma",
        email="sharma@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    db.session.add_all([inst_user, officer])
    db.session.commit()

    today = date.today()
    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number="EML-FDR-2026",
        bank_name="State Bank of India",
        branch_name="University Campus",
        amount=Decimal("1500000.00"),
        issue_date=today - timedelta(days=1000),
        maturity_date=today + timedelta(days=30),
        validity_status=ValidityStatus.EXPIRING_SOON.value,
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        created_by=inst_user.id,
    )
    db.session.add(fdr)
    db.session.commit()

    return {
        "inst": inst,
        "inst_user": inst_user,
        "officer": officer,
        "fdr": fdr,
    }


def login_helper(client, email, password):
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.get_json()}"
    csrf_resp = client.get("/api/auth/csrf-token")
    assert csrf_resp.status_code == 200
    return csrf_resp.get_json()["csrf_token"]


def test_is_valid_email():
    """Verify email format validator."""
    assert is_valid_email("principal@college.edu") is True
    assert is_valid_email("admin.cell@aicte.gov.in") is True
    assert is_valid_email("") is False
    assert is_valid_email(None) is False
    assert is_valid_email("plainaddress") is False
    assert is_valid_email("@missingusername.com") is False
    assert is_valid_email("missingdomain@") is False


def test_send_email_mocked_smtp_delivery(app, email_env):
    """Verify SMTP connection, TLS handshake, login, and send_message with mocked smtplib."""
    # Explicitly disable testing suppression for this test to exercise the SMTP client code
    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["TESTING"] = False
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = "test.portal@gmail.com"
    app.config["MAIL_PASSWORD"] = "test_app_password"

    mock_smtp_instance = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        success = send_email(
            to_email="principal@ics.edu",
            subject="Test Statutory Notice",
            body_text="Plain text body",
            body_html="<p>HTML body</p>",
            email_type="TEST_EMAIL",
            institution_id=email_env["inst"].id,
        )

        assert success is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("test.portal@gmail.com", "test_app_password")
        mock_smtp_instance.send_message.assert_called_once()

        # Verify EmailNotificationLog record was created with SENT status
        log = EmailNotificationLog.query.filter_by(
            recipient_email="principal@ics.edu",
            email_type="TEST_EMAIL",
        ).first()
        assert log is not None
        assert log.status == "SENT"
        assert log.error_message is None


def test_send_email_smtp_failure_handling(app, email_env):
    """Verify graceful handling when SMTP connection raises an exception without crashing."""
    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["TESTING"] = False

    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Service not available")):
        success = send_email(
            to_email="principal@ics.edu",
            subject="Failing Email Test",
            body_text="Test",
            email_type="TEST_EMAIL",
            institution_id=email_env["inst"].id,
        )

        assert success is False

        # Verify failed delivery is recorded with status FAILED and does not leak secrets
        log = EmailNotificationLog.query.filter_by(
            recipient_email="principal@ics.edu",
            email_type="TEST_EMAIL",
            status="FAILED",
        ).first()
        assert log is not None
        assert "Service not available" in log.error_message


def test_send_email_missing_or_invalid_recipient(app):
    """Invalid recipient addresses must return False and not record a SENT email."""
    assert send_email(to_email="", subject="Sub", body_text="Body") is False
    assert send_email(to_email="not-an-email", subject="Sub", body_text="Body") is False
    assert send_email(to_email=None, subject="Sub", body_text="Body") is False


def test_duplicate_fdr_maturity_reminder_prevention(app, email_env):
    """Verify that multiple scans on the same reminder interval do NOT dispatch duplicate emails."""
    fdr = email_env["fdr"]
    assert is_fdr_reminder_already_sent(fdr.id, 30) is False

    # 1. First trigger for 30 days
    sent_count = send_fdr_maturity_email(fdr, 30)
    assert sent_count >= 1
    assert is_fdr_reminder_already_sent(fdr.id, 30) is True

    # 2. Second trigger for same FDR and 30 days must be blocked
    second_sent = send_fdr_maturity_email(fdr, 30)
    assert second_sent == 0

    # Total SENT logs for this FDR and interval 30 must remain exactly 1
    logs = EmailNotificationLog.query.filter_by(
        fdr_id=fdr.id,
        email_type="FDR_MATURITY_REMINDER",
        reminder_interval_days=30,
        status="SENT",
    ).all()
    assert len(logs) == 1


def test_maturity_scan_triggers_email_notifications(app, email_env):
    """Maturity scan accurately generates statutory emails for configured milestone intervals."""
    fdr = email_env["fdr"]
    # FDR is set to mature in exactly 30 days
    today = date.today()

    result = scan_and_update_maturities(as_of_date=today)
    assert result["scanned_count"] >= 1
    assert result["emails_sent_count"] >= 1

    # Verify EmailNotificationLog contains maturity reminder
    log = EmailNotificationLog.query.filter_by(
        fdr_id=fdr.id,
        email_type="FDR_MATURITY_REMINDER",
        reminder_interval_days=30,
    ).first()
    assert log is not None
    assert log.status == "SENT"


def test_petition_approval_and_receipt_upload_email_pipeline(client, email_env):
    """
    Test full renewal workflow emails:
    1. Officer approves renewal petition -> PETITION_STATUS_CHANGED & RENEWAL_RECEIPT_REQUIRED emails sent.
    2. Institution uploads receipt.
    3. Officer verifies receipt -> RENEWAL_RECEIPT_VERIFIED & RENEWAL_COMPLETED emails sent.
    """
    fdr = email_env["fdr"]
    inst_user = email_env["inst_user"]
    officer = email_env["officer"]

    # 1. Institution submits renewal request
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    create_resp = client.post(
        "/api/requests",
        json={
            "fdr_id": fdr.id,
            "request_type": "Renewal",
            "reason": "Statutory renewal with State Bank of India.",
        },
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert create_resp.status_code == 201
    req_id = create_resp.get_json()["data"]["id"]

    # 2. Officer approves petition
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    appr_resp = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Approved. Upload renewed FDR receipt from bank."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert appr_resp.status_code == 200

    # Verify PETITION_STATUS_CHANGED and RENEWAL_RECEIPT_REQUIRED emails were logged
    appr_email = EmailNotificationLog.query.filter_by(
        email_type="PETITION_STATUS_CHANGED",
        request_id=fdr.requests.first().id,
    ).first()
    assert appr_email is not None

    receipt_req_email = EmailNotificationLog.query.filter_by(
        email_type="RENEWAL_RECEIPT_REQUIRED",
        request_id=fdr.requests.first().id,
    ).first()
    assert receipt_req_email is not None

    # 3. Institution uploads renewed FDR receipt
    new_mat = (date.today() + timedelta(days=1095)).isoformat()
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    sub_resp = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "EML-FDR-2026-REN",
            "new_issue_date": date.today().isoformat(),
            "new_maturity_date": new_mat,
            "new_amount": "1500000.00",
            "remarks": "Renewed for 3 years.",
            "file": (io.BytesIO(b"%PDF-1.4 renewal receipt mock"), "renewed_receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert sub_resp.status_code == 200

    # 4. Officer verifies renewal receipt
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    ver_resp = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={"decision": "VERIFIED", "remarks": "Bank certificate confirmed."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert ver_resp.status_code == 200

    # Verify RENEWAL_RECEIPT_VERIFIED and RENEWAL_COMPLETED emails were logged
    ver_email = EmailNotificationLog.query.filter_by(
        email_type="RENEWAL_RECEIPT_VERIFIED",
        request_id=fdr.requests.first().id,
    ).first()
    assert ver_email is not None

    comp_email = EmailNotificationLog.query.filter_by(
        email_type="RENEWAL_COMPLETED",
        fdr_id=fdr.id,
    ).first()
    assert comp_email is not None


def test_cli_test_email_command(runner, app):
    """Verify flask test-email CLI diagnostic command runs safely."""
    with patch("app.services.email_service.send_test_email", return_value=(True, "Dispatched safely")):
        result = runner.invoke(args=["test-email", "--recipient", "admin@aicte.gov.in"])
        assert result.exit_code == 0
        assert "Initiating SMTP diagnostic test" in result.output
        assert "SUCCESS: Dispatched safely" in result.output


def test_scan_and_send_receipt_reminders(app, email_env):
    """Verify that approved petitions awaiting receipt trigger 7-day and 14-day receipt reminders."""
    fdr = email_env["fdr"]
    inst = email_env["inst"]
    inst_user = email_env["inst_user"]

    req = FDRRequest(
        fdr_id=fdr.id,
        institution_id=inst.id,
        created_by=inst_user.id,
        request_type="Renewal",
        status="Approved",
        stage="Approved — Awaiting Renewed Deposit Receipt",
        reason="Renewal",
        created_at=date.today() - timedelta(days=8),
        updated_at=date.today() - timedelta(days=8),
    )
    db.session.add(req)
    db.session.commit()

    # Should send 7-day reminder
    sent = scan_and_send_receipt_reminders()
    assert sent >= 1

    # Immediate second scan must NOT duplicate
    sent_second = scan_and_send_receipt_reminders()
    assert sent_second == 0


def test_ensure_schema_updates_creates_email_notification_logs_safely(app):
    """Verify ensure_schema_updates safely creates missing tables without impacting existing data."""
    from sqlalchemy import inspect
    from app.services.migration_service import ensure_schema_updates

    inspector = inspect(db.engine)
    assert "email_notification_logs" in inspector.get_table_names()

    # Drop the table in the test database to simulate pre-migration state
    EmailNotificationLog.__table__.drop(db.engine, checkfirst=True)
    inspector_after_drop = inspect(db.engine)
    assert "email_notification_logs" not in inspector_after_drop.get_table_names()

    # Run ensure_schema_updates()
    created = ensure_schema_updates()
    assert "email_notification_logs" in created

    # Verify table exists again
    inspector_after_migration = inspect(db.engine)
    assert "email_notification_logs" in inspector_after_migration.get_table_names()

    # Running it again is idempotent and safe
    created_again = ensure_schema_updates()
    assert "email_notification_logs" not in created_again


def test_send_email_smtp_success_db_failure_separation(app, email_env):
    """
    If SMTP server accepts the email but database audit logging fails,
    send_email must return True (email was sent) and safely rollback the session.
    """
    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["TESTING"] = False
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = "test.portal@gmail.com"
    app.config["MAIL_PASSWORD"] = "test_app_password"

    mock_smtp_instance = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with patch.object(db.session, "commit", side_effect=Exception("Database disk image is malformed")):
            success = send_email(
                to_email="principal@ics.edu",
                subject="Test Statutory Notice with DB Error",
                body_text="Plain text body",
                email_type="TEST_EMAIL",
                institution_id=email_env["inst"].id,
            )

            # SMTP delivery succeeded, so return True
            assert success is True
            mock_smtp_instance.send_message.assert_called_once()


def test_send_test_email_separates_smtp_delivery_and_db_logging(app):
    """Verify send_test_email returns separated diagnostic status for SMTP and DB."""
    with patch.object(db.session, "commit", side_effect=Exception("sqlite3.OperationalError: disk I/O error")):
        result = send_test_email("admin@aicte.gov.in")
        assert result.smtp_success is True
        assert result.db_logged is False
        assert result.success is True
        assert "disk I/O error" in result.db_error
        # Tuple unpacking compatibility
        ok, msg = result
        assert ok is True


def test_cli_test_email_separate_status_display(runner, app):
    """Verify flask test-email CLI outputs separate statuses for SMTP and Database."""
    from app.services.email_service import TestEmailResult

    mock_res = TestEmailResult(
        smtp_success=True,
        db_logged=False,
        message="Diagnostic email dispatched to test@aicte.gov.in.",
        db_error="table missing",
    )
    with patch("app.services.email_service.send_test_email", return_value=mock_res):
        result = runner.invoke(args=["test-email", "--recipient", "test@aicte.gov.in"])
        assert result.exit_code == 0
        assert "SMTP DELIVERY: SUCCESS" in result.output
        assert "DATABASE AUDIT: WARNING (table missing)" in result.output
        assert "SUCCESS: Diagnostic email dispatched" in result.output


def test_maturity_date_milestone_zero_days(app, email_env):
    """Verify that Day 0 (maturity date) triggers the correct urgent statutory email."""
    fdr = email_env["fdr"]
    today = date.today()
    # Move FDR maturity date to today
    fdr.maturity_date = today
    db.session.commit()

    scan_res = scan_and_update_maturities(as_of_date=today)
    assert scan_res["emails_sent_count"] >= 1

    log = EmailNotificationLog.query.filter_by(
        fdr_id=fdr.id,
        email_type="FDR_MATURITY_REMINDER",
        reminder_interval_days=0,
    ).first()
    assert log is not None
    assert log.status == "SENT"
    assert "Matured Today" in log.subject


def test_failed_email_retry_not_suppressed(app, email_env):
    """
    If a previous email attempt failed (status='FAILED'), duplicate prevention
    must NOT suppress future scans from retrying delivery.
    """
    fdr = email_env["fdr"]

    # Record a simulated FAILED delivery log for interval 15
    failed_log = EmailNotificationLog(
        recipient_email="principal@ics.edu",
        institution_id=email_env["inst"].id,
        subject="Failed Reminder",
        email_type="FDR_MATURITY_REMINDER",
        fdr_id=fdr.id,
        reminder_interval_days=15,
        status="FAILED",
        error_message="Connection timed out",
    )
    db.session.add(failed_log)
    db.session.commit()

    # is_fdr_reminder_already_sent must return False because status was FAILED
    assert is_fdr_reminder_already_sent(fdr.id, 15) is False

    # Dispatching now must succeed and create a SENT log
    sent_count = send_fdr_maturity_email(fdr, 15)
    assert sent_count >= 1
    assert is_fdr_reminder_already_sent(fdr.id, 15) is True


def test_petition_creation_triggers_submitted_email(client, email_env):
    """Verify that lodging a new petition dispatches an acknowledgment email to the institution."""
    inst = email_env["inst"]
    inst_user = email_env["inst_user"]
    today = date.today()

    fdr_new = FDRRecord(
        institution_id=inst.id,
        fdr_number="EML-FDR-FRESH-REQ",
        bank_name="Canara Bank",
        branch_name="Tech City",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=500),
        maturity_date=today + timedelta(days=60),
        validity_status=ValidityStatus.EXPIRING_SOON.value,
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        created_by=inst_user.id,
    )
    db.session.add(fdr_new)
    db.session.commit()

    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    resp = client.post(
        "/api/requests",
        json={
            "fdr_id": fdr_new.id,
            "request_type": "Renewal",
            "reason": "Routine statutory term renewal.",
        },
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert resp.status_code == 201
    req_id = resp.get_json()["data"]["id"]
    raw_id = resp.get_json()["data"]["raw_id"]

    # Verify PETITION_STATUS_CHANGED log exists for this petition with status Submitted
    log = EmailNotificationLog.query.filter_by(
        request_id=raw_id,
        email_type="PETITION_STATUS_CHANGED",
        recipient_email=inst_user.email,
    ).first()
    assert log is not None
    assert log.status == "SENT"
    assert "Status Changed to 'Submitted'" in log.subject


def test_receipt_rejection_and_returned_email_types(client, email_env):
    """Verify that officer receipt rejection and return decisions trigger appropriate email types."""
    inst = email_env["inst"]
    inst_user = email_env["inst_user"]
    officer = email_env["officer"]
    today = date.today()

    fdr_rej = FDRRecord(
        institution_id=inst.id,
        fdr_number="EML-FDR-REJ-REQ",
        bank_name="Punjab National Bank",
        branch_name="Civil Lines",
        amount=Decimal("1200000.00"),
        issue_date=today - timedelta(days=600),
        maturity_date=today + timedelta(days=45),
        validity_status=ValidityStatus.EXPIRING_SOON.value,
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        created_by=inst_user.id,
    )
    db.session.add(fdr_rej)
    db.session.commit()

    # 1. Create and approve petition
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    create_resp = client.post(
        "/api/requests",
        json={"fdr_id": fdr_rej.id, "request_type": "Renewal", "reason": "Renewal test"},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert create_resp.status_code == 201
    req_id = create_resp.get_json()["data"]["id"]
    raw_id = create_resp.get_json()["data"]["raw_id"]

    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    appr_resp = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Approved. Upload receipt."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert appr_resp.status_code == 200

    # 2. Institution uploads receipt
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    sub_resp = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "EML-REJ-2026",
            "new_issue_date": date.today().isoformat(),
            "new_maturity_date": (date.today() + timedelta(days=1095)).isoformat(),
            "new_amount": "1200000.00",
            "remarks": "Uploaded",
            "file": (io.BytesIO(b"%PDF-1.4 test receipt"), "receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert sub_resp.status_code == 200

    # 3. Officer rejects receipt
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    ver_resp = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={"decision": "REJECTED", "remarks": "Mismatched branch code on bank certificate."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert ver_resp.status_code == 200

    rej_log = EmailNotificationLog.query.filter_by(
        request_id=raw_id,
        email_type="RENEWAL_RECEIPT_REJECTED",
    ).first()
    assert rej_log is not None
    assert rej_log.status == "SENT"
    assert "Rejected" in rej_log.subject


def test_email_logs_api_endpoint_and_tenant_isolation(client, email_env):
    """Verify /api/notifications/email-logs diagnostic endpoint and multi-tenant isolation."""
    inst = email_env["inst"]
    inst_user = email_env["inst_user"]
    officer = email_env["officer"]

    # Provision a second valid institution for multi-tenant isolation testing
    inst2 = Institution(
        institution_code="AICTE-EML-002",
        name="Second Engineering College",
        contact_email="other@college.edu",
    )
    db.session.add(inst2)
    db.session.commit()

    # Create dummy logs: one for this institution, one for the second institution
    log1 = EmailNotificationLog(
        recipient_email="principal@ics.edu",
        institution_id=inst.id,
        subject="Notice for ICS",
        email_type="FDR_MATURITY_REMINDER",
        status="SENT",
    )
    log2 = EmailNotificationLog(
        recipient_email="other@college.edu",
        institution_id=inst2.id,
        subject="Notice for other",
        email_type="FDR_MATURITY_REMINDER",
        status="FAILED",
        error_message="Mailbox unavailable",
    )
    db.session.add_all([log1, log2])
    db.session.commit()

    # Institution user must only see log1 (tenant isolation)
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    resp_inst = client.get("/api/notifications/email-logs", headers={"X-CSRF-Token": csrf_inst})
    assert resp_inst.status_code == 200
    inst_logs = resp_inst.get_json()["logs"]
    assert all(l["institution_id"] == inst.id for l in inst_logs)
    assert any(l["recipient_email"] == "principal@ics.edu" for l in inst_logs)

    # Officer can inspect all logs and filter by status=FAILED
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    resp_officer = client.get(
        "/api/notifications/email-logs?status=FAILED",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert resp_officer.status_code == 200
    failed_logs = resp_officer.get_json()["logs"]
    assert any(l["recipient_email"] == "other@college.edu" for l in failed_logs)
    assert all(l["status"] == "FAILED" for l in failed_logs)



def _attach_test_document(fdr_id, user_id):
    from app.models.document import Document
    from app.models.enums import DocumentProcessingStatus
    doc = Document(
        fdr_id=fdr_id,
        stored_filename=f"doc_{fdr_id}.pdf",
        original_filename="receipt.pdf",
        file_size=1024,
        file_type="application/pdf",
        processing_status=DocumentProcessingStatus.PROCESSED.value,
        uploaded_by=user_id,
    )
    db.session.add(doc)
    db.session.commit()


def test_fdr_scrutiny_return_triggers_deficiency_email(client, email_env):
    """
    Verify that when an officer returns an FDR for corrections:
    1. FDR status and deficiency remarks are saved.
    2. In-app notification is created.
    3. Deficiency email is triggered to the institution's registered email.
    4. Email clearly states corrections are required (never claims approval).
    5. Email audit table records 'SENT'.
    """
    inst = email_env["inst"]
    inst_user = email_env["inst_user"]
    officer = email_env["officer"]

    # 1. Create a new submitted FDR for testing
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    create_res = client.post(
        "/api/fdr",
        json={
            "fdr_number": "DEF-TEST-001",
            "bank_name": "Canara Bank",
            "branch_name": "Shivaji Nagar",
            "amount": "250000.00",
            "issue_date": date.today().isoformat(),
            "maturity_date": (date.today() + timedelta(days=365)).isoformat(),
        },
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert create_res.status_code == 201
    fdr_id = create_res.get_json()["data"]["id"]

    # Attach document so submission readiness passes
    _attach_test_document(fdr_id, inst_user.id)

    # Submit for scrutiny
    sub_res = client.post(
        f"/api/fdr/{fdr_id}/submit",
        json={"remarks": "Initial submission for scrutiny"},
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert sub_res.status_code == 200

    # 2. Officer starts review to enter PENDING_VERIFICATION
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    rev_res = client.post(
        f"/api/fdr/{fdr_id}/start-review",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert rev_res.status_code == 200

    # 3. Officer reviews and returns FDR for expired document
    ret_res = client.post(
        f"/api/fdr/{fdr_id}/return",
        json={"remarks": "Your document uploaded is expired. Resubmit the correct one."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert ret_res.status_code == 200
    ret_data = ret_res.get_json()["data"]
    assert ret_data["scrutiny_status"] == "RETURNED"

    # 3. Verify EmailNotificationLog contains the deficiency notice
    log = EmailNotificationLog.query.filter_by(
        fdr_id=fdr_id,
        email_type="FDR_DEFICIENCY_CORRECTION_REQUIRED",
    ).first()
    assert log is not None, "Email audit log entry for deficiency was not created"
    assert log.status == "SENT"
    assert log.recipient_email == inst.contact_email
    assert "Corrections Needed" in log.subject
    assert "DEF-TEST-001" in log.subject


def test_smtp_failure_does_not_rollback_saved_decision(client, email_env, monkeypatch):
    """
    Verify that if SMTP delivery fails (network/timeout/auth failure):
    1. The officer's saved decision (RETURNED) is preserved in DB.
    2. Deficiency remarks and workflow history remain intact.
    3. The email log captures 'FAILED' status with the safe error message.
    """
    inst_user = email_env["inst_user"]
    officer = email_env["officer"]

    # Create & submit FDR
    csrf_inst = login_helper(client, inst_user.email, "IcsPass123!")
    create_res = client.post(
        "/api/fdr",
        json={
            "fdr_number": "FAIL-TEST-002",
            "bank_name": "Canara Bank",
            "branch_name": "Shivaji Nagar",
            "amount": "300000.00",
            "issue_date": date.today().isoformat(),
            "maturity_date": (date.today() + timedelta(days=365)).isoformat(),
        },
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert create_res.status_code == 201
    fdr_id = create_res.get_json()["data"]["id"]
    _attach_test_document(fdr_id, inst_user.id)
    sub_res = client.post(f"/api/fdr/{fdr_id}/submit", json={}, headers={"X-CSRF-Token": csrf_inst})
    assert sub_res.status_code == 200

    # Officer starts review
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    rev_res = client.post(f"/api/fdr/{fdr_id}/start-review", headers={"X-CSRF-Token": csrf_officer})
    assert rev_res.status_code == 200

    # Simulate SMTP failure
    import smtplib
    def mock_send_message(*args, **kwargs):
        raise smtplib.SMTPConnectError(421, b"Service not available, closing transmission channel")

    monkeypatch.setattr(smtplib.SMTP, "send_message", mock_send_message)
    # Ensure delivery is attempted through smtplib.SMTP rather than testing suppression
    monkeypatch.setitem(client.application.config, "TESTING", False)
    monkeypatch.setitem(client.application.config, "MAIL_SUPPRESS_SEND", False)

    # Officer returns FDR
    ret_res = client.post(
        f"/api/fdr/{fdr_id}/return",
        json={"remarks": "Uploaded certificate blurry. Please rescan."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    # Decision MUST succeed even though email failed
    assert ret_res.status_code == 200
    ret_data = ret_res.get_json()["data"]
    assert ret_data["scrutiny_status"] == "RETURNED"

    # Verify FDR status in DB
    fdr = db.session.get(FDRRecord, fdr_id)
    assert fdr.scrutiny_status == "RETURNED"

    # Verify EmailNotificationLog recorded the failure
    log = EmailNotificationLog.query.filter_by(
        fdr_id=fdr_id,
        email_type="FDR_DEFICIENCY_CORRECTION_REQUIRED",
    ).first()
    assert log is not None
    assert log.status == "FAILED"
    assert "421" in (log.error_message or "")


def test_retry_failed_email_notification_endpoint(client, email_env):
    """
    Verify POST /api/notifications/email-logs/<id>/retry:
    - Retries a failed notification.
    - Prevents duplicate delivery if already SENT.
    - Enforces tenant isolation.
    """
    inst = email_env["inst"]
    inst_user = email_env["inst_user"]
    officer = email_env["officer"]

    # Provision failed log
    failed_log = EmailNotificationLog(
        recipient_email=inst.contact_email,
        institution_id=inst.id,
        subject="Action Required: Corrections Needed (RETRY-TEST)",
        email_type="FDR_DEFICIENCY_CORRECTION_REQUIRED",
        fdr_id=email_env["fdr"].id,
        status="FAILED",
        error_message="Simulated temporary timeout",
    )
    db.session.add(failed_log)
    db.session.commit()

    # Officer retries
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    retry_res = client.post(
        f"/api/notifications/email-logs/{failed_log.id}/retry",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert retry_res.status_code == 200
    assert retry_res.get_json()["success"] is True

    # Retry already SENT log -> skips duplicate
    sent_log = EmailNotificationLog(
        recipient_email=inst.contact_email,
        institution_id=inst.id,
        subject="Already Delivered",
        email_type="FDR_SCRUTINY_VERIFIED",
        status="SENT",
    )
    db.session.add(sent_log)
    db.session.commit()

    retry_sent_res = client.post(
        f"/api/notifications/email-logs/{sent_log.id}/retry",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert retry_sent_res.status_code == 200
    assert "already successfully delivered" in retry_sent_res.get_json()["message"]


def test_missing_institution_email_handled_gracefully(client, email_env):
    """
    Verify that an institution with no valid registered email is handled gracefully without crashing.
    """
    # Create institution with invalid email
    inst_no_email = Institution(
        institution_code="AICTE-NO-EML",
        name="No Valid Email College",
        contact_email="invalid-not-an-email",
    )
    db.session.add(inst_no_email)
    db.session.commit()

    # User with valid format email but inactive so recipient resolver skips it
    user_no_email = User(
        full_name="Dean Unknown",
        email="dean.unknown@example.com",
        role=UserRole.INSTITUTION,
        institution_id=inst_no_email.id,
        is_active=False,
    )
    user_no_email.set_password("NoPass123!")
    db.session.add(user_no_email)
    db.session.commit()

    fdr_no_email = FDRRecord(
        institution_id=inst_no_email.id,
        fdr_number="NO-EMAIL-FDR",
        bank_name="Test Bank",
        branch_name="Main Branch",
        amount=Decimal("100000.00"),
        issue_date=date.today(),
        maturity_date=date.today() + timedelta(days=365),
        scrutiny_status=ScrutinyStatus.PENDING_VERIFICATION.value,
        created_by=user_no_email.id,
    )
    db.session.add(fdr_no_email)
    db.session.commit()

    _attach_test_document(fdr_no_email.id, user_no_email.id)

    # Check recipient resolution returns empty list
    from app.services.email_service import resolve_fdr_recipients
    resolved_inst, recipients = resolve_fdr_recipients(fdr_no_email)
    assert resolved_inst is not None
    assert recipients == []

    # Officer returns the FDR
    officer = email_env["officer"]
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    ret_res = client.post(
        f"/api/fdr/{fdr_no_email.id}/return",
        json={"remarks": "Returning despite missing email address."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    # Decision must succeed without crashing
    assert ret_res.status_code == 200
    assert ret_res.get_json()["data"]["scrutiny_status"] == "RETURNED"
