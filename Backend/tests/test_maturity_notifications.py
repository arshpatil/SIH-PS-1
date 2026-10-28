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
    classify_validity_status,
    get_business_date,
    scan_and_update_maturities,
)
from app.services.scheduler import init_scheduler


@pytest.fixture
def seed_notification_env(app):
    """Seed test institutions, users, and FDRs with deterministic dates."""
    inst_a = Institution(
        institution_code="AICTE-NOTIF-A",
        name="Alpha Institute of Technology",
        contact_email="admin@alpha-tech.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-NOTIF-B",
        name="Beta College of Engineering",
        contact_email="admin@beta-eng.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    user_a1 = User(
        full_name="Alpha Registrar",
        email="registrar@alpha-tech.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a1.set_password("AlphaPass123!")

    user_a2 = User(
        full_name="Alpha Finance",
        email="finance@alpha-tech.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a2.set_password("AlphaPass123!")

    user_b1 = User(
        full_name="Beta Registrar",
        email="registrar@beta-eng.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_b.id,
        is_active=True,
    )
    user_b1.set_password("BetaPass123!")

    officer = User(
        full_name="AICTE Officer North",
        email="officer.north@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    db.session.add_all([user_a1, user_a2, user_b1, officer])
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a1": user_a1,
        "user_a2": user_a2,
        "user_b1": user_b1,
        "officer": officer,
    }


def login_and_get_csrf(client, email, password="AlphaPass123!"):
    """Helper to authenticate and extract session CSRF token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


# =====================================================================
# 1. Validity Status Boundaries & Classification Tests
# =====================================================================


def test_classify_validity_status_boundaries():
    """Test all validity status boundary conditions against a fixed business date."""
    ref_date = date(2026, 10, 1)

    # > 30 days remaining -> ACTIVE
    assert (
        classify_validity_status(date(2026, 11, 15), as_of_date=ref_date)
        == ValidityStatus.ACTIVE
    )
    assert (
        classify_validity_status(date(2026, 11, 1), as_of_date=ref_date)
        == ValidityStatus.ACTIVE
    )  # 31 days

    # 1 to 30 days remaining -> EXPIRING_SOON
    assert (
        classify_validity_status(date(2026, 10, 31), as_of_date=ref_date)
        == ValidityStatus.EXPIRING_SOON
    )  # 30 days
    assert (
        classify_validity_status(date(2026, 10, 16), as_of_date=ref_date)
        == ValidityStatus.EXPIRING_SOON
    )  # 15 days
    assert (
        classify_validity_status(date(2026, 10, 8), as_of_date=ref_date)
        == ValidityStatus.EXPIRING_SOON
    )  # 7 days
    assert (
        classify_validity_status(date(2026, 10, 2), as_of_date=ref_date)
        == ValidityStatus.EXPIRING_SOON
    )  # 1 day

    # 0 days remaining (maturity date reached) -> MATURED
    assert (
        classify_validity_status(date(2026, 10, 1), as_of_date=ref_date)
        == ValidityStatus.MATURED
    )

    # 1 to 29 days past maturity -> MATURED
    assert (
        classify_validity_status(date(2026, 9, 30), as_of_date=ref_date)
        == ValidityStatus.MATURED
    )  # -1 day
    assert (
        classify_validity_status(date(2026, 9, 15), as_of_date=ref_date)
        == ValidityStatus.MATURED
    )  # -16 days
    assert (
        classify_validity_status(date(2026, 9, 2), as_of_date=ref_date)
        == ValidityStatus.MATURED
    )  # -29 days

    # >= 30 days past maturity without action -> OVERDUE_ACTION
    assert (
        classify_validity_status(date(2026, 9, 1), as_of_date=ref_date)
        == ValidityStatus.OVERDUE_ACTION
    )  # -30 days
    assert (
        classify_validity_status(date(2026, 8, 1), as_of_date=ref_date)
        == ValidityStatus.OVERDUE_ACTION
    )  # -61 days


def test_classify_validity_status_configurable_thresholds():
    """Verify that custom thresholds adjust the classification boundaries as expected."""
    ref_date = date(2026, 10, 1)

    # Custom: expiring_soon = 60 days, overdue = 45 days
    # 45 days remaining: standard is ACTIVE, but custom is EXPIRING_SOON
    assert (
        classify_validity_status(
            date(2026, 11, 15),
            as_of_date=ref_date,
            expiring_soon_days=60,
            overdue_action_days=45,
        )
        == ValidityStatus.EXPIRING_SOON
    )

    # 35 days past maturity: standard is OVERDUE_ACTION, but custom (45 days) is MATURED
    assert (
        classify_validity_status(
            date(2026, 8, 27),
            as_of_date=ref_date,
            expiring_soon_days=60,
            overdue_action_days=45,
        )
        == ValidityStatus.MATURED
    )


def test_scan_preserves_officer_scrutiny_status(app, seed_notification_env):
    """Ensure scanning updates validity_status without overwriting scrutiny_status or unrelated fields."""
    env = seed_notification_env
    ref_date = date(2026, 10, 1)

    fdr = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-STATUS-TEST",
        bank_name="Canara Bank",
        branch_name="Head Office",
        amount=Decimal("1500000.00"),
        issue_date=date(2025, 10, 1),
        maturity_date=date(2026, 10, 1),  # Matured on ref_date
        scrutiny_status=ScrutinyStatus.VERIFIED.value,  # Officer verified!
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a1"].id,
    )
    db.session.add(fdr)
    db.session.commit()

    with app.app_context():
        scan_and_update_maturities(as_of_date=ref_date)

    updated_fdr = db.session.get(FDRRecord, fdr.id)
    assert updated_fdr.validity_status == ValidityStatus.MATURED.value
    # Scrutiny status and other fields must remain completely untouched
    assert updated_fdr.scrutiny_status == ScrutinyStatus.VERIFIED.value
    assert updated_fdr.bank_name == "Canara Bank"
    assert updated_fdr.branch_name == "Head Office"
    assert updated_fdr.amount == Decimal("1500000.00")


# =====================================================================
# 2. Reminder Intervals & Notification Delivery Tests
# =====================================================================


def test_reminder_intervals_and_maturity_date(app, seed_notification_env):
    """Test notification generation at 30, 15, 7, and 0 days remaining."""
    env = seed_notification_env
    maturity = date(2026, 11, 1)

    fdr = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-REMINDER-01",
        bank_name="Bank of Baroda",
        branch_name="Camp",
        amount=Decimal("500000.00"),
        issue_date=date(2025, 11, 1),
        maturity_date=maturity,
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a1"].id,
    )
    db.session.add(fdr)
    db.session.commit()

    # 1. Day 30 reminder: 2026-10-02
    with app.app_context():
        res30 = scan_and_update_maturities(as_of_date=date(2026, 10, 2))
    assert res30["notifications_created"] == 2  # Sent to user_a1 and user_a2
    notif30 = Notification.query.filter_by(
        user_id=env["user_a1"].id, notification_type=NotificationType.WARNING.value
    ).first()
    assert notif30 is not None
    assert "30 Days Remaining" in notif30.title

    # 2. Day 15 reminder: 2026-10-17
    with app.app_context():
        res15 = scan_and_update_maturities(as_of_date=date(2026, 10, 17))
    assert res15["notifications_created"] == 2
    notif15 = Notification.query.filter_by(
        user_id=env["user_a1"].id, title=f"FDR Maturity Reminder: {fdr.fdr_number} (15 Days Remaining)"
    ).first()
    assert notif15 is not None

    # 3. Day 7 urgent reminder: 2026-10-25 (Escalation to officer!)
    with app.app_context():
        res7 = scan_and_update_maturities(as_of_date=date(2026, 10, 25))
    # Sent to user_a1, user_a2, and officer (3 recipients)
    assert res7["notifications_created"] == 3
    officer_notif = Notification.query.filter_by(
        user_id=env["officer"].id, notification_type=NotificationType.ACTION_REQUIRED.value
    ).first()
    assert officer_notif is not None
    assert "7 Days" in officer_notif.title

    # 4. Day 0 (Maturity date reached): 2026-11-01
    with app.app_context():
        res0 = scan_and_update_maturities(as_of_date=date(2026, 11, 1))
    assert res0["notifications_created"] == 3
    notif0 = Notification.query.filter_by(
        user_id=env["user_a1"].id, notification_type=NotificationType.ALERT.value
    ).first()
    assert notif0 is not None
    assert "FDR Matured Today" in notif0.title


def test_idempotent_scan_execution(app, seed_notification_env):
    """Verify that running the scanner repeatedly on the same day never duplicates notifications."""
    env = seed_notification_env
    ref_date = date(2026, 10, 2)  # 30 days before maturity

    fdr = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-IDEMPOTENT-01",
        bank_name="Union Bank",
        branch_name="Main",
        amount=Decimal("1000000.00"),
        issue_date=date(2025, 11, 1),
        maturity_date=date(2026, 11, 1),
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a1"].id,
    )
    db.session.add(fdr)
    db.session.commit()

    with app.app_context():
        # First scan
        res1 = scan_and_update_maturities(as_of_date=ref_date)
        assert res1["notifications_created"] == 2

        # Second scan on the same date
        res2 = scan_and_update_maturities(as_of_date=ref_date)
        assert res2["notifications_created"] == 0

        # Third scan on the same date
        res3 = scan_and_update_maturities(as_of_date=ref_date)
        assert res3["notifications_created"] == 0

    # Total notifications in DB for user_a1 should still be exactly 1
    total_a1 = Notification.query.filter_by(user_id=env["user_a1"].id).count()
    assert total_a1 == 1


def test_no_cross_institution_leakage(app, seed_notification_env):
    """Verify that institution B users never receive notifications regarding institution A's FDRs."""
    env = seed_notification_env
    ref_date = date(2026, 10, 2)  # 30 days before maturity

    fdr_a = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-LEAK-CHECK-A",
        bank_name="Axis Bank",
        branch_name="Sector 1",
        amount=Decimal("2000000.00"),
        issue_date=date(2025, 11, 1),
        maturity_date=date(2026, 11, 1),
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a1"].id,
    )
    db.session.add(fdr_a)
    db.session.commit()

    with app.app_context():
        scan_and_update_maturities(as_of_date=ref_date)

    # User B1 belongs to inst_b; must have 0 notifications
    user_b_notifs = Notification.query.filter_by(user_id=env["user_b1"].id).all()
    assert len(user_b_notifs) == 0

    # User A1 and A2 belong to inst_a; must have 1 notification each
    assert Notification.query.filter_by(user_id=env["user_a1"].id).count() == 1
    assert Notification.query.filter_by(user_id=env["user_a2"].id).count() == 1


# =====================================================================
# 3. Notification API Endpoints Tests
# =====================================================================


def test_notifications_list_and_unread_count(client, seed_notification_env):
    """Test GET /api/notifications with pagination and unread_only filtering, plus unread-count."""
    env = seed_notification_env
    user_a = env["user_a1"]

    # Seed 5 notifications for user_a (3 unread, 2 read)
    for i in range(1, 6):
        n = Notification(
            user_id=user_a.id,
            title=f"Notification #{i}",
            message=f"Test message body {i}",
            notification_type=NotificationType.INFO.value,
            is_read=(i > 3),  # 1, 2, 3 unread; 4, 5 read
        )
        db.session.add(n)
    db.session.commit()

    csrf = login_and_get_csrf(client, user_a.email, "AlphaPass123!")

    # 1. Unread count endpoint
    res_count = client.get("/api/notifications/unread-count")
    assert res_count.status_code == 200
    count_data = res_count.get_json()
    assert count_data["success"] is True
    assert count_data["unread_count"] == 3

    # 2. List all notifications with pagination (per_page=2)
    res_page1 = client.get("/api/notifications?page=1&per_page=2")
    assert res_page1.status_code == 200
    p1_data = res_page1.get_json()
    assert p1_data["success"] is True
    assert len(p1_data["notifications"]) == 2
    assert p1_data["pagination"]["total"] == 5
    assert p1_data["pagination"]["pages"] == 3
    assert p1_data["pagination"]["has_next"] is True

    # 3. Filter unread_only=true
    res_unread = client.get("/api/notifications?unread_only=true")
    assert res_unread.status_code == 200
    unread_data = res_unread.get_json()
    assert len(unread_data["notifications"]) == 3
    for notif in unread_data["notifications"]:
        assert notif["is_read"] is False


def test_mark_notification_as_read(client, seed_notification_env):
    """Test PATCH /api/notifications/<id>/read marks one notification read with CSRF validation."""
    env = seed_notification_env
    user_a = env["user_a1"]

    notif = Notification(
        user_id=user_a.id,
        title="Action Required Alert",
        message="Please verify deposit receipt",
        notification_type=NotificationType.ACTION_REQUIRED.value,
        is_read=False,
    )
    db.session.add(notif)
    db.session.commit()

    csrf = login_and_get_csrf(client, user_a.email, "AlphaPass123!")

    # Mark as read
    res = client.patch(
        f"/api/notifications/{notif.id}/read",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["notification"]["is_read"] is True

    # Verify DB state
    refreshed = db.session.get(Notification, notif.id)
    assert refreshed.is_read is True


def test_mark_all_notifications_as_read(client, seed_notification_env):
    """Test PATCH /api/notifications/read-all marks all notifications of the user as read."""
    env = seed_notification_env
    user_a = env["user_a1"]

    for i in range(4):
        db.session.add(
            Notification(
                user_id=user_a.id,
                title=f"Bulk Notification #{i}",
                message="Message",
                notification_type=NotificationType.INFO.value,
                is_read=False,
            )
        )
    db.session.commit()

    csrf = login_and_get_csrf(client, user_a.email, "AlphaPass123!")

    res = client.patch("/api/notifications/read-all", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["marked_count"] == 4

    # Verify unread count is now 0
    res_count = client.get("/api/notifications/unread-count")
    assert res_count.get_json()["unread_count"] == 0


def test_cannot_access_or_modify_other_user_notifications(client, seed_notification_env):
    """Verify cross-user isolation: User B cannot view or mark User A's notifications."""
    env = seed_notification_env
    user_a = env["user_a1"]
    user_b = env["user_b1"]

    notif_a = Notification(
        user_id=user_a.id,
        title="Confidential Institution A Alert",
        message="Secret details for Inst A",
        notification_type=NotificationType.ALERT.value,
        is_read=False,
    )
    db.session.add(notif_a)
    db.session.commit()

    # Log in as User B
    csrf_b = login_and_get_csrf(client, user_b.email, "BetaPass123!")

    # User B attempts to mark User A's notification as read
    res_patch = client.patch(
        f"/api/notifications/{notif_a.id}/read",
        headers={"X-CSRF-Token": csrf_b},
    )
    # Must return 404 to avoid leaking existence
    assert res_patch.status_code == 404

    # User A's notification must remain unread
    assert db.session.get(Notification, notif_a.id).is_read is False

    # User B lists notifications; must not contain User A's notification
    res_list = client.get("/api/notifications")
    assert res_list.status_code == 200
    items = res_list.get_json()["notifications"]
    assert len(items) == 0


def test_notification_unauthenticated_and_csrf_enforcement(client, seed_notification_env):
    """Test unauthenticated access (401) and CSRF enforcement on PATCH requests (403)."""
    # 1. Unauthenticated requests
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.patch("/api/notifications/1/read").status_code == 401
    assert client.patch("/api/notifications/read-all").status_code == 401

    # 2. Authenticated but missing CSRF token
    user_a = seed_notification_env["user_a1"]
    login_and_get_csrf(client, user_a.email, "AlphaPass123!")

    res_no_csrf = client.patch("/api/notifications/1/read")
    assert res_no_csrf.status_code == 403
    assert res_no_csrf.get_json()["code"] == "CSRF_ERROR"


# =====================================================================
# 4. CLI Scan & Scheduler Safety Tests
# =====================================================================


def test_cli_scan_fdr_maturities(runner, app, seed_notification_env):
    """Test executing the flask scan-fdr-maturities CLI command with an explicit date."""
    env = seed_notification_env

    fdr = FDRRecord(
        institution_id=env["inst_a"].id,
        fdr_number="FDR-CLI-TEST-01",
        bank_name="ICICI Bank",
        branch_name="Camp",
        amount=Decimal("500000.00"),
        issue_date=date(2025, 11, 1),
        maturity_date=date(2026, 11, 1),
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=env["user_a1"].id,
    )
    db.session.add(fdr)
    db.session.commit()

    result = runner.invoke(args=["scan-fdr-maturities", "--date", "2026-10-02"])
    assert result.exit_code == 0
    assert "Maturity scan completed for 2026-10-02" in result.output
    assert "Scanned 1 FDR(s)" in result.output
    assert "Generated 2 notification(s)" in result.output


def test_cli_scan_fdr_maturities_invalid_date(runner):
    """Test executing CLI scan with invalid date format shows clean error."""
    result = runner.invoke(args=["scan-fdr-maturities", "--date", "not-a-date"])
    assert "Error: Invalid date format" in result.output


def test_scheduler_disabled_in_testing(app):
    """Verify that the background scheduler does not start during testing."""
    # In testing environment (TESTING=True), init_scheduler should return None
    scheduler = init_scheduler(app)
    assert scheduler is None
