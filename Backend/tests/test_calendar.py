from datetime import date, timedelta
from decimal import Decimal
import io
import pytest

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User


@pytest.fixture
def calendar_env(app):
    """Seed test environment with 2 institutions, an officer, an admin, and test FDRs."""
    inst_1 = Institution(
        institution_code="AICTE-CAL-001",
        name="Cal Institute of Tech",
        contact_email="cal1@cit.edu",
    )
    inst_2 = Institution(
        institution_code="AICTE-CAL-002",
        name="Cal Polytechnic",
        contact_email="cal2@poly.edu",
    )
    db.session.add_all([inst_1, inst_2])
    db.session.commit()

    inst1_user = User(
        full_name="Principal Cal1",
        email="cal1@cit.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_1.id,
        is_active=True,
    )
    inst1_user.set_password("CalPass123!")

    inst2_user = User(
        full_name="Principal Cal2",
        email="cal2@poly.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_2.id,
        is_active=True,
    )
    inst2_user.set_password("CalPass123!")

    officer = User(
        full_name="Officer Rao",
        email="rao.officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="Admin Mehta",
        email="mehta.admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([inst1_user, inst2_user, officer, admin])
    db.session.commit()

    today = date.today()
    # FDR for inst 1 maturing in 30 days
    fdr_1 = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="CAL-FDR-001",
        bank_name="State Bank of India",
        branch_name="Main Campus",
        amount=Decimal("500000.00"),
        issue_date=today - timedelta(days=1000),
        maturity_date=today + timedelta(days=30),
        validity_status=ValidityStatus.EXPIRING_SOON.value,
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        created_by=inst1_user.id,
    )

    # FDR for inst 2 maturing in 60 days
    fdr_2 = FDRRecord(
        institution_id=inst_2.id,
        fdr_number="CAL-FDR-002",
        bank_name="Punjab National Bank",
        branch_name="City Branch",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=1000),
        maturity_date=today + timedelta(days=60),
        validity_status=ValidityStatus.ACTIVE.value,
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        created_by=inst2_user.id,
    )

    db.session.add_all([fdr_1, fdr_2])
    db.session.commit()

    return {
        "inst_1": inst_1,
        "inst_2": inst_2,
        "inst1_user": inst1_user,
        "inst2_user": inst2_user,
        "officer": officer,
        "admin": admin,
        "fdr_1": fdr_1,
        "fdr_2": fdr_2,
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


def test_calendar_requires_authentication(client):
    """Unauthenticated requests to /api/calendar/events must be rejected with 401."""
    resp = client.get("/api/calendar/events")
    assert resp.status_code == 401


def test_calendar_institution_tenant_isolation(client, calendar_env):
    """Institutions must see only their own events and never records of other institutions."""
    login_helper(client, "cal1@cit.edu", "CalPass123!")

    resp = client.get("/api/calendar/events")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "events" in data

    events = data["events"]
    # All events must belong to inst_1
    for ev in events:
        assert ev.get("institution_id") == calendar_env["inst_1"].id
        assert ev.get("fdr_number") != "CAL-FDR-002"

    # Confirm FDR-001 is present
    fdr_maturities = [e for e in events if e.get("type") == "FDR_MATURITY"]
    assert any(e["fdr_number"] == "CAL-FDR-001" for e in fdr_maturities)


def test_calendar_officer_and_admin_access(client, calendar_env):
    """Officers and Administrators have system-level event visibility."""
    # Officer login
    login_helper(client, "rao.officer@aicte.gov.in", "OfficerPass123!")
    resp_off = client.get("/api/calendar/events")
    assert resp_off.status_code == 200
    off_events = resp_off.get_json()["events"]
    # Officer can see both institutions' FDR maturities
    fdr_nums = [e.get("fdr_number") for e in off_events if e.get("type") == "FDR_MATURITY"]
    assert "CAL-FDR-001" in fdr_nums
    assert "CAL-FDR-002" in fdr_nums

    # Admin login with institution filter
    login_helper(client, "mehta.admin@aicte.gov.in", "AdminPass123!")
    resp_admin = client.get(f"/api/calendar/events?institution_id={calendar_env['inst_1'].id}")
    assert resp_admin.status_code == 200
    admin_events = resp_admin.get_json()["events"]
    for e in admin_events:
        assert e.get("institution_id") == calendar_env["inst_1"].id


def test_calendar_date_range_filtering(client, calendar_env):
    """Calendar respects start and end date query filters."""
    login_helper(client, "mehta.admin@aicte.gov.in", "AdminPass123!")

    today = date.today()
    # Filter only for next 35 days (should include CAL-FDR-001 at +30d, but exclude CAL-FDR-002 at +60d)
    start_str = today.isoformat()
    end_str = (today + timedelta(days=35)).isoformat()

    resp = client.get(f"/api/calendar/events?start={start_str}&end={end_str}&event_type=MATURITY")
    assert resp.status_code == 200
    events = resp.get_json()["events"]
    fdr_nums = [e.get("fdr_number") for e in events]
    assert "CAL-FDR-001" in fdr_nums
    assert "CAL-FDR-002" not in fdr_nums


def test_calendar_renewal_lifecycle_maturity_date_invariants(client, calendar_env):
    """
    Verify complete renewal pipeline on calendar:
    1. Petition submitted: original maturity date unchanged.
    2. Officer approves petition: original maturity date strictly preserved, awaiting receipt event appears.
    3. Institution submits renewed receipt: original maturity date strictly preserved, verification pending event appears.
    4. Officer verifies receipt: official maturity date updates on calendar.
    """
    fdr = calendar_env["fdr_1"]
    original_mat_d = fdr.maturity_date.isoformat()
    inst_user = calendar_env["inst1_user"]
    officer = calendar_env["officer"]

    # 1. Institution submits renewal petition
    csrf_inst = login_helper(client, inst_user.email, "CalPass123!")
    create_resp = client.post(
        "/api/requests",
        json={
            "fdr_id": fdr.id,
            "request_type": "Renewal",
            "reason": "Statutory 3-year term extension with issuing commercial bank.",
        },
        headers={"X-CSRF-Token": csrf_inst},
    )
    assert create_resp.status_code == 201, create_resp.get_data(as_text=True)
    req_id = create_resp.get_json()["data"]["id"]

    # Check calendar: maturity date must remain original
    cal_resp1 = client.get("/api/calendar/events")
    events1 = cal_resp1.get_json()["events"]
    mat_event1 = next(e for e in events1 if e.get("fdr_id") == fdr.id and e.get("type") == "FDR_MATURITY")
    assert mat_event1["date"] == original_mat_d

    # 2. Officer approves petition
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    appr_resp = client.patch(
        f"/api/requests/{req_id}/status",
        json={"status": "Approved", "remarks": "Approved. Upload renewed FDR receipt."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert appr_resp.status_code == 200

    # Institution checks calendar: official maturity date is STILL unchanged
    csrf_inst = login_helper(client, inst_user.email, "CalPass123!")
    cal_resp2 = client.get("/api/calendar/events")
    events2 = cal_resp2.get_json()["events"]
    mat_event2 = next(e for e in events2 if e.get("fdr_id") == fdr.id and e.get("type") == "FDR_MATURITY")
    assert mat_event2["date"] == original_mat_d

    # And awaiting receipt event is present
    awaiting_event = next(e for e in events2 if e.get("type") == "RENEWAL_APPROVED_AWAITING_RECEIPT")
    assert str(awaiting_event["request_id"]) == str(req_id).replace("REQ-", "").lstrip("0") or awaiting_event.get("request_formatted_id") == str(req_id)

    # 3. Institution uploads renewed deposit receipt
    proposed_new_mat = (date.today() + timedelta(days=1095)).isoformat()
    sub_resp = client.post(
        f"/api/requests/{req_id}/submit-renewal",
        data={
            "new_fdr_number": "CAL-FDR-001-REN",
            "new_issue_date": date.today().isoformat(),
            "new_maturity_date": proposed_new_mat,
            "new_amount": "500000.00",
            "remarks": "Renewed by SBI campus branch for 3 years.",
            "file": (io.BytesIO(b"%PDF-1.4 renewed receipt mock"), "renewed_receipt.pdf"),
        },
        headers={"X-CSRF-Token": csrf_inst},
        content_type="multipart/form-data",
    )
    assert sub_resp.status_code == 200

    # Official maturity date STILL UNCHANGED before verification!
    cal_resp3 = client.get("/api/calendar/events")
    events3 = cal_resp3.get_json()["events"]
    mat_event3 = next(e for e in events3 if e.get("fdr_id") == fdr.id and e.get("type") == "FDR_MATURITY")
    assert mat_event3["date"] == original_mat_d

    # Pending verification event is present with provisional date
    pending_event = next(e for e in events3 if e.get("type") == "RENEWAL_PENDING_VERIFICATION")
    assert pending_event["provisional_maturity_date"] == proposed_new_mat

    # 4. Officer verifies renewal
    csrf_officer = login_helper(client, officer.email, "OfficerPass123!")
    ver_resp = client.post(
        f"/api/requests/{req_id}/verify-renewal",
        json={"decision": "VERIFIED", "remarks": "Confirmed with bank terms."},
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert ver_resp.status_code == 200

    # NOW official maturity date is officially extended!
    cal_resp4 = client.get(f"/api/calendar/events?end={(date.today() + timedelta(days=1200)).isoformat()}")
    events4 = cal_resp4.get_json()["events"]
    mat_event4 = next(e for e in events4 if e.get("fdr_id") == fdr.id and e.get("type") == "FDR_MATURITY")
    assert mat_event4["date"] == proposed_new_mat
    assert mat_event4["fdr_number"] == "CAL-FDR-001-REN"
