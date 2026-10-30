from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.enums import NotificationType, ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.notification import Notification
from app.models.user import User
from app.services.maturity_service import (
    get_maturity_category,
    scan_and_update_maturities,
)


def test_advanced_maturity_milestones_and_duplicate_prevention(app):
    """Verify 90-day, 60-day milestones and rejection suppression."""
    with app.app_context():
        inst = Institution(institution_code="AICTE-MAT-ADV", name="Advanced Tech Institute", contact_email="inst@mat.edu")
        db.session.add(inst)
        db.session.commit()

        user = User(full_name="Registrar Adv", email="user@mat.edu", role=UserRole.INSTITUTION, institution_id=inst.id)
        user.set_password("MatPass123!")
        db.session.add(user)
        db.session.commit()

        ref_date = date(2026, 1, 1)

        # FDR 1: Exactly 90 days away
        fdr_90 = FDRRecord(
            institution_id=inst.id,
            fdr_number="FDR-90D-ADV",
            bank_name="HDFC Bank",
            branch_name="Branch 1",
            amount=Decimal("1000000.00"),
            issue_date=ref_date - timedelta(days=365),
            maturity_date=ref_date + timedelta(days=90),
            scrutiny_status=ScrutinyStatus.VERIFIED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user.id,
        )

        # FDR 2: Exactly 60 days away
        fdr_60 = FDRRecord(
            institution_id=inst.id,
            fdr_number="FDR-60D-ADV",
            bank_name="ICICI Bank",
            branch_name="Branch 2",
            amount=Decimal("1500000.00"),
            issue_date=ref_date - timedelta(days=365),
            maturity_date=ref_date + timedelta(days=60),
            scrutiny_status=ScrutinyStatus.VERIFIED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user.id,
        )

        # FDR 3: Maturing today but REJECTED scrutiny status -> Should be skipped!
        fdr_rejected = FDRRecord(
            institution_id=inst.id,
            fdr_number="FDR-REJ-ADV",
            bank_name="PNB",
            branch_name="Branch 3",
            amount=Decimal("500000.00"),
            issue_date=ref_date - timedelta(days=365),
            maturity_date=ref_date,
            scrutiny_status=ScrutinyStatus.REJECTED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user.id,
        )

        db.session.add_all([fdr_90, fdr_60, fdr_rejected])
        db.session.commit()

        # Run scan
        res = scan_and_update_maturities(as_of_date=ref_date)
        assert res["scanned_count"] >= 3

        # Verify 90-day notification exists
        notif_90 = Notification.query.filter(
            Notification.user_id == user.id,
            Notification.title.like("%90 Days Remaining%"),
        ).first()
        assert notif_90 is not None

        # Verify 60-day notification exists
        notif_60 = Notification.query.filter(
            Notification.user_id == user.id,
            Notification.title.like("%60 Days Remaining%"),
        ).first()
        assert notif_60 is not None

        # Verify NO notification generated for rejected FDR
        notif_rej = Notification.query.filter(
            Notification.user_id == user.id,
            Notification.title.like("%FDR-REJ-ADV%"),
        ).first()
        assert notif_rej is None

        # Rerun scan -> Idempotent, 0 new notifications
        res_rerun = scan_and_update_maturities(as_of_date=ref_date)
        assert res_rerun["notifications_created"] == 0


def test_maturity_category_brackets():
    """Verify get_maturity_category boundary classifications."""
    ref = date(2026, 6, 1)
    assert get_maturity_category(ref + timedelta(days=120), as_of_date=ref) == "FUTURE"
    assert get_maturity_category(ref + timedelta(days=90), as_of_date=ref) == "MATURING_90_DAYS"
    assert get_maturity_category(ref + timedelta(days=60), as_of_date=ref) == "MATURING_60_DAYS"
    assert get_maturity_category(ref + timedelta(days=30), as_of_date=ref) == "MATURING_30_DAYS"
    assert get_maturity_category(ref + timedelta(days=7), as_of_date=ref) == "MATURING_7_DAYS"
    assert get_maturity_category(ref + timedelta(days=0), as_of_date=ref) == "MATURING_7_DAYS"
    assert get_maturity_category(ref - timedelta(days=10), as_of_date=ref) == "MATURED"
    assert get_maturity_category(ref - timedelta(days=40), as_of_date=ref) == "OVERDUE_ACTION"
