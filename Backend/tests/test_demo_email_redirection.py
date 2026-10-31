from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.email_log import EmailNotificationLog
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User
from app.services.email_service import (
    get_institution_emails,
    resolve_fdr_recipients,
    resolve_institution_recipients,
    send_fdr_maturity_email,
    send_fdr_scrutiny_status_email,
    send_petition_status_email,
    send_receipt_verification_email,
    send_renewal_completed_email,
    send_renewal_receipt_required_email,
)


@pytest.fixture
def demo_email_env(app):
    """Seed test environment with demo institution and a real institution."""
    # 1. Demo Institution (matching default seed code and ID)
    demo_inst = Institution(
        institution_code="AICTE-1-10928371",
        name="ABC Institute of Technology & Engineering",
        contact_email="principal@abcite.edu.in",
    )
    # 2. Real / Regular Accredited Institution
    real_inst = Institution(
        institution_code="AICTE-REAL-998822",
        name="National Engineering College",
        contact_email="registrar@national-engg.edu",
    )
    db.session.add_all([demo_inst, real_inst])
    db.session.commit()

    demo_user = User(
        full_name="Principal ABC",
        email="principal@abcite.edu.in",
        role=UserRole.INSTITUTION,
        institution_id=demo_inst.id,
        is_active=True,
    )
    demo_user.set_password("SecurePass123!")

    real_user = User(
        full_name="Registrar National",
        email="registrar@national-engg.edu",
        role=UserRole.INSTITUTION,
        institution_id=real_inst.id,
        is_active=True,
    )
    real_user.set_password("SecurePass123!")

    officer = User(
        full_name="AICTE Desk Officer",
        email="officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    db.session.add_all([demo_user, real_user, officer])
    db.session.commit()

    # Create FDR records for both
    demo_fdr = FDRRecord(
        institution_id=demo_inst.id,
        created_by=demo_user.id,
        fdr_number="FDR-DEMO-2026-001",
        bank_name="State Bank of India",
        branch_name="Main Campus",
        amount=Decimal("2500000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=10),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.EXPIRING_SOON.value,
    )
    real_fdr = FDRRecord(
        institution_id=real_inst.id,
        created_by=real_user.id,
        fdr_number="FDR-REAL-2026-999",
        bank_name="Punjab National Bank",
        branch_name="City Central",
        amount=Decimal("3000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=15),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.EXPIRING_SOON.value,
    )
    db.session.add_all([demo_fdr, real_fdr])
    db.session.commit()

    return {
        "demo_inst": demo_inst,
        "real_inst": real_inst,
        "demo_user": demo_user,
        "real_user": real_user,
        "demo_fdr": demo_fdr,
        "real_fdr": real_fdr,
    }


def test_demo_email_redirection_active(app, demo_email_env):
    """
    Verify that when DEMO_INSTITUTION_EMAIL is configured,
    demo institution emails are redirected to 1sih.hackathon@gmail.com,
    while real institution emails remain untouched.
    """
    demo_inst = demo_email_env["demo_inst"]
    real_inst = demo_email_env["real_inst"]

    # Configure override in app config
    app.config["DEMO_INSTITUTION_EMAIL"] = "1sih.hackathon@gmail.com"
    app.config["DEMO_INSTITUTION_CODE"] = "AICTE-1-10928371"

    # 1. Demo institution resolution
    demo_recipients = get_institution_emails(demo_inst)
    assert demo_recipients == ["1sih.hackathon@gmail.com"]

    # 2. Real institution resolution remains registered address
    real_recipients = get_institution_emails(real_inst)
    assert real_recipients == ["registrar@national-engg.edu"]
    assert "1sih.hackathon@gmail.com" not in real_recipients

    # 3. Database records remain completely untouched
    assert demo_inst.contact_email == "principal@abcite.edu.in"
    assert real_inst.contact_email == "registrar@national-engg.edu"


def test_missing_demo_config_fallback(app, demo_email_env):
    """
    Verify that if DEMO_INSTITUTION_EMAIL is None/empty,
    the demo institution still safely receives emails at its registered address.
    """
    demo_inst = demo_email_env["demo_inst"]

    app.config["DEMO_INSTITUTION_EMAIL"] = None
    recipients = get_institution_emails(demo_inst)
    assert recipients == ["principal@abcite.edu.in"]


def test_all_notification_types_respect_override(app, demo_email_env):
    """
    Verify all major institution-facing notification dispatchers use the redirected address.
    """
    app.config["DEMO_INSTITUTION_EMAIL"] = "1sih.hackathon@gmail.com"
    app.config["DEMO_INSTITUTION_CODE"] = "AICTE-1-10928371"

    demo_fdr = demo_email_env["demo_fdr"]
    demo_inst = demo_email_env["demo_inst"]
    demo_user = demo_email_env["demo_user"]

    req = FDRRequest(
        fdr_id=demo_fdr.id,
        institution_id=demo_inst.id,
        created_by=demo_user.id,
        request_type="Renewal",
        reason="Maturity term renewal",
        status="Submitted",
    )
    db.session.add(req)
    db.session.commit()

    # 1. Maturity notification
    sent = send_fdr_maturity_email(demo_fdr, 10)
    assert sent >= 1
    log_mat = EmailNotificationLog.query.filter_by(fdr_id=demo_fdr.id, email_type="FDR_MATURITY_REMINDER").first()
    assert log_mat is not None
    assert log_mat.recipient_email == "1sih.hackathon@gmail.com"

    # 2. Petition status update (Submitted / Under Review / Approved)
    sent_stat = send_petition_status_email(req, "Under Review")
    assert sent_stat >= 1
    log_stat = EmailNotificationLog.query.filter(
        EmailNotificationLog.request_id == req.id,
        EmailNotificationLog.email_type.like("PETITION_STATUS_%"),
    ).first()
    assert log_stat is not None
    assert log_stat.recipient_email == "1sih.hackathon@gmail.com"

    # 3. Renewal receipt required notification
    sent_req = send_renewal_receipt_required_email(req)
    assert sent_req >= 1
    log_req = EmailNotificationLog.query.filter_by(
        request_id=req.id,
        email_type="RENEWAL_RECEIPT_REQUIRED",
    ).first()
    assert log_req is not None
    assert log_req.recipient_email == "1sih.hackathon@gmail.com"

    # 4. Scrutiny status email
    sent_sc = send_fdr_scrutiny_status_email(demo_fdr, "RETURNED", remarks="Test deficiency")
    assert sent_sc >= 1
    log_sc = EmailNotificationLog.query.filter_by(
        fdr_id=demo_fdr.id,
        email_type="FDR_DEFICIENCY_CORRECTION_REQUIRED",
    ).first()
    assert log_sc is not None
    assert log_sc.recipient_email == "1sih.hackathon@gmail.com"


def test_audit_logs_and_deduplication(app, demo_email_env):
    """
    Verify that email audit logging and reminder deduplication continue to function with redirection.
    """
    app.config["DEMO_INSTITUTION_EMAIL"] = "1sih.hackathon@gmail.com"
    app.config["DEMO_INSTITUTION_CODE"] = "AICTE-1-10928371"

    demo_fdr = demo_email_env["demo_fdr"]

    # First dispatch of reminder (interval = 30)
    sent_first = send_fdr_maturity_email(demo_fdr, 30)
    assert sent_first >= 1

    # Second dispatch should be suppressed by deduplication
    sent_second = send_fdr_maturity_email(demo_fdr, 30)
    assert sent_second == 0
