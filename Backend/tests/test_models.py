from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    AuditLog,
    Document,
    DocumentProcessingStatus,
    FDRRecord,
    Institution,
    Notification,
    NotificationType,
    ScrutinyStatus,
    User,
    UserRole,
    ValidityStatus,
)


def test_database_tables_created(app):
    """Verify that all six core model tables exist in SQLAlchemy metadata."""
    expected_tables = {
        "institutions",
        "users",
        "fdr_records",
        "documents",
        "audit_logs",
        "notifications",
    }
    registered_tables = set(db.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables)


def test_institution_creation_and_uniqueness(app):
    """Test institution creation, serialization, and uniqueness constraint on institution_code."""
    inst1 = Institution(
        institution_code="AICTE-ENG-001",
        name="Apex Institute of Technology",
        address="123 Knowledge Park, Tech City",
        contact_email="registrar@apexinstitute.edu.in",
        contact_phone="+91-11-23456789",
    )
    db.session.add(inst1)
    db.session.commit()

    assert inst1.id is not None
    assert inst1.institution_code == "AICTE-ENG-001"
    data = inst1.to_dict()
    assert data["institution_code"] == "AICTE-ENG-001"
    assert data["name"] == "Apex Institute of Technology"

    # Attempt duplicate institution_code
    inst2 = Institution(
        institution_code="AICTE-ENG-001",
        name="Duplicate College",
        contact_email="other@example.com",
    )
    db.session.add(inst2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_creation_roles_and_validation(app):
    """Test user creation, role validation, email validation, and officer with null institution."""
    inst = Institution(
        institution_code="AICTE-ENG-002",
        name="Global Engineering College",
        contact_email="admin@globaleng.edu",
    )
    db.session.add(inst)
    db.session.commit()

    # Valid institution user
    inst_user = User(
        full_name="Rajesh Kumar",
        email="rajesh@globaleng.edu",
        password_hash="pbkdf2:sha256:dummyhash",
        role=UserRole.INSTITUTION_USER,
        institution_id=inst.id,
        is_active=True,
    )
    db.session.add(inst_user)

    # Valid AICTE officer without institution
    officer = User(
        full_name="Dr. Anita Sharma",
        email="anita.sharma@aicte.gov.in",
        password_hash="pbkdf2:sha256:officerhash",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
    )
    db.session.add(officer)
    db.session.commit()

    assert inst_user.institution.name == "Global Engineering College"
    assert officer.institution_id is None

    # Invalid email test
    with pytest.raises(ValueError, match="Invalid email address format"):
        User(
            full_name="Bad Email",
            email="invalid-email-address",
            password_hash="hash",
            role=UserRole.INSTITUTION_USER,
        )

    # Invalid role test
    with pytest.raises(ValueError, match="Invalid user role"):
        User(
            full_name="Bad Role",
            email="valid@example.com",
            password_hash="hash",
            role="SUPER_GOD_MODE",
        )

    # Duplicate email uniqueness test
    dup_user = User(
        full_name="Duplicate Email",
        email="rajesh@globaleng.edu",
        password_hash="hash2",
        role=UserRole.INSTITUTION_USER,
    )
    db.session.add(dup_user)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_fdr_record_creation_and_validations(app):
    """Test FDRRecord positive amount, date ordering, status validation, and unique constraint."""
    inst = Institution(
        institution_code="AICTE-ENG-003",
        name="National Tech Institute",
        contact_email="info@nti.edu",
    )
    user = User(
        full_name="Pooja Verma",
        email="pooja@nti.edu",
        password_hash="hash",
        role=UserRole.INSTITUTION_USER,
    )
    inst.users.append(user)
    db.session.add(inst)
    db.session.commit()

    issue_d = date(2025, 1, 15)
    maturity_d = date(2030, 1, 15)

    # Valid FDR Record
    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number="SBI-FDR-987654321",
        bank_name="State Bank of India",
        branch_name="Connaught Place, New Delhi",
        amount=Decimal("1500000.00"),
        issue_date=issue_d,
        maturity_date=maturity_d,
        scrutiny_status=ScrutinyStatus.DRAFT,
        validity_status=ValidityStatus.ACTIVE,
        created_by=user.id,
    )
    db.session.add(fdr)
    db.session.commit()

    assert fdr.id is not None
    assert fdr.amount == Decimal("1500000.00")
    assert fdr.institution.name == "National Tech Institute"
    assert fdr.creator.full_name == "Pooja Verma"

    # Validation: Non-positive amount
    with pytest.raises(ValueError, match="positive value"):
        FDRRecord(
            institution_id=inst.id,
            fdr_number="SBI-001",
            bank_name="SBI",
            branch_name="Main",
            amount=Decimal("0.00"),
            issue_date=issue_d,
            maturity_date=maturity_d,
            created_by=user.id,
        )

    with pytest.raises(ValueError, match="positive value"):
        FDRRecord(
            institution_id=inst.id,
            fdr_number="SBI-002",
            bank_name="SBI",
            branch_name="Main",
            amount=Decimal("-50000.00"),
            issue_date=issue_d,
            maturity_date=maturity_d,
            created_by=user.id,
        )

    # Validation: Maturity date earlier than issue date
    with pytest.raises(ValueError, match="Maturity date cannot be earlier"):
        FDRRecord(
            institution_id=inst.id,
            fdr_number="SBI-003",
            bank_name="SBI",
            branch_name="Main",
            amount=Decimal("500000.00"),
            issue_date=date(2028, 1, 1),
            maturity_date=date(2025, 1, 1),
            created_by=user.id,
        )

    # Uniqueness: Duplicate FDR number for the SAME institution must fail
    dup_fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number="SBI-FDR-987654321",
        bank_name="State Bank of India",
        branch_name="Different Branch",
        amount=Decimal("1000000.00"),
        issue_date=issue_d,
        maturity_date=maturity_d,
        created_by=user.id,
    )
    db.session.add(dup_fdr)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_document_and_cascade_delete(app):
    """Test Document model validation, relationship to FDR, and cascading delete on FDR removal."""
    inst = Institution(
        institution_code="AICTE-ENG-004",
        name="Institute Four",
        contact_email="i4@example.com",
    )
    user = User(
        full_name="User Four",
        email="u4@example.com",
        password_hash="hash",
        role=UserRole.INSTITUTION_USER,
    )
    inst.users.append(user)
    db.session.add(inst)
    db.session.commit()

    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number="HDFC-FDR-1111",
        bank_name="HDFC Bank",
        branch_name="Sector 62, Noida",
        amount=Decimal("2500000.00"),
        issue_date=date(2024, 6, 1),
        maturity_date=date(2029, 6, 1),
        created_by=user.id,
    )
    db.session.add(fdr)
    db.session.commit()

    doc = Document(
        fdr_id=fdr.id,
        original_filename="Scanned_FDR_Receipt.pdf",
        stored_filename="fdr_2024_06_uuid123.pdf",
        file_type="application/pdf",
        file_size=1048576,  # 1MB
        processing_status=DocumentProcessingStatus.PENDING,
        uploaded_by=user.id,
    )
    db.session.add(doc)
    db.session.commit()

    assert doc.id is not None
    assert doc.fdr.fdr_number == "HDFC-FDR-1111"
    assert doc.uploader.full_name == "User Four"

    # Validation: File size must be positive
    with pytest.raises(ValueError, match="positive integer"):
        Document(
            fdr_id=fdr.id,
            original_filename="bad.pdf",
            stored_filename="bad.pdf",
            file_type="application/pdf",
            file_size=0,
            uploaded_by=user.id,
        )

    # Cascade test: Deleting the FDR must cascade delete associated documents
    doc_id = doc.id
    db.session.delete(fdr)
    db.session.commit()

    assert db.session.get(Document, doc_id) is None


def test_audit_log_and_system_events(app):
    """Test AuditLog model for user events and system events (nullable user_id)."""
    user = User(
        full_name="Officer Ramesh",
        email="ramesh@aicte.gov.in",
        password_hash="hash",
        role=UserRole.AICTE_OFFICER,
    )
    db.session.add(user)
    db.session.commit()

    # User action log
    log1 = AuditLog(
        user_id=user.id,
        action="FDR_VERIFIED",
        entity_type="FDRRecord",
        entity_id=42,
        details="FDR verified after reviewing joint lien clause with bank.",
    )
    db.session.add(log1)

    # Automated background system event (user_id is None)
    log2 = AuditLog(
        user_id=None,
        action="MATURITY_MONITOR_SCAN",
        entity_type="SystemCron",
        entity_id=None,
        details="Daily cron scanned 120 FDRs; marked 3 as EXPIRING_SOON.",
    )
    db.session.add(log2)
    db.session.commit()

    assert log1.id is not None
    assert log1.user.full_name == "Officer Ramesh"
    assert log2.id is not None
    assert log2.user_id is None
    assert log2.action == "MATURITY_MONITOR_SCAN"


def test_notification_creation_and_cascade(app):
    """Test Notification model, read status toggle, and cascade delete upon user deletion."""
    user = User(
        full_name="Registrar College",
        email="registrar@citycollege.ac.in",
        password_hash="hash",
        role=UserRole.INSTITUTION_USER,
    )
    db.session.add(user)
    db.session.commit()

    notif = Notification(
        user_id=user.id,
        title="FDR Expiring in 30 Days",
        message="Your Fixed Deposit Receipt SBI-FDR-987654 will mature on 2026-11-25. Please initiate renewal.",
        notification_type=NotificationType.WARNING,
        is_read=False,
    )
    db.session.add(notif)
    db.session.commit()

    assert notif.id is not None
    assert notif.is_read is False
    assert notif.notification_type == "WARNING"

    # Mark as read
    notif.is_read = True
    db.session.commit()
    assert db.session.get(Notification, notif.id).is_read is True

    # Cascade deletion test
    notif_id = notif.id
    db.session.delete(user)
    db.session.commit()
    assert db.session.get(Notification, notif_id) is None


def test_init_db_safe_mechanism(app, monkeypatch):
    """Test safe database initialization helper and production guard."""
    from app import init_db

    # In test/dev environment, calling init_db runs safely without error or data loss
    init_db(app)

    # In production, automatic table creation must be blocked
    monkeypatch.setenv("FLASK_ENV", "production")
    with pytest.raises(RuntimeError, match="disabled in production"):
        init_db(app)


def test_fdr_date_type_and_mutation_validation(app):
    """Test that arbitrary strings are rejected for dates and in-place updates adhere to date ordering."""
    inst = Institution(
        institution_code="AICTE-ENG-005",
        name="Tech Five",
        contact_email="five@example.com",
    )
    user = User(
        full_name="User Five",
        email="five@example.com",
        password_hash="hash",
        role=UserRole.INSTITUTION_USER,
    )
    inst.users.append(user)
    db.session.add(inst)
    db.session.commit()

    # Rejection of string instead of date object
    with pytest.raises(ValueError, match="must be a valid date object"):
        FDRRecord(
            institution_id=inst.id,
            fdr_number="STR-DATE-001",
            bank_name="PNB",
            branch_name="Delhi",
            amount=Decimal("100000"),
            issue_date="2025-01-01",  # String instead of date
            maturity_date=date(2026, 1, 1),
            created_by=user.id,
        )

    # Valid FDR record
    fdr = FDRRecord(
        institution_id=inst.id,
        fdr_number="FDR-MUTATE-001",
        bank_name="PNB",
        branch_name="Delhi",
        amount=Decimal("100000"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2026, 1, 1),
        created_by=user.id,
    )
    db.session.add(fdr)
    db.session.commit()

    # Mutation test: setting maturity date earlier than issue date must raise ValueError
    with pytest.raises(ValueError, match="Maturity date cannot be earlier"):
        fdr.maturity_date = date(2024, 1, 1)


def test_different_institutions_same_fdr_number(app):
    """Verify that identical FDR numbers are allowed across DIFFERENT institutions."""
    inst1 = Institution(
        institution_code="AICTE-DIFF-01",
        name="College A",
        contact_email="a@example.com",
    )
    inst2 = Institution(
        institution_code="AICTE-DIFF-02",
        name="College B",
        contact_email="b@example.com",
    )
    user1 = User(
        full_name="User A",
        email="usera@example.com",
        password_hash="hash",
        role=UserRole.INSTITUTION_USER,
    )
    user2 = User(
        full_name="User B",
        email="userb@example.com",
        password_hash="hash",
        role=UserRole.INSTITUTION_USER,
    )
    inst1.users.append(user1)
    inst2.users.append(user2)
    db.session.add_all([inst1, inst2])
    db.session.commit()

    shared_fdr_number = "COMMON-FDR-2025"

    fdr1 = FDRRecord(
        institution_id=inst1.id,
        fdr_number=shared_fdr_number,
        bank_name="Canara Bank",
        branch_name="Branch 1",
        amount=Decimal("500000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        created_by=user1.id,
    )
    fdr2 = FDRRecord(
        institution_id=inst2.id,
        fdr_number=shared_fdr_number,
        bank_name="Canara Bank",
        branch_name="Branch 2",
        amount=Decimal("750000.00"),
        issue_date=date(2025, 2, 1),
        maturity_date=date(2030, 2, 1),
        created_by=user2.id,
    )
    db.session.add_all([fdr1, fdr2])
    db.session.commit()

    assert fdr1.id is not None
    assert fdr2.id is not None
    assert fdr1.id != fdr2.id

