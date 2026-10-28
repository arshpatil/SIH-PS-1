import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import pytest

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User
from app.models.workflow_history import FDRWorkflowHistory
from app.services.maturity_service import get_business_date


@pytest.fixture
def seed_dashboard_env(app):
    """Seed test environment with multi-institution data, roles, and status distributions."""
    # 1. Institutions
    inst_a = Institution(
        institution_code="AICTE-DASH-A",
        name="Apex College of Technology",
        contact_email="apex@college.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-DASH-B",
        name="Zenith Engineering Institute",
        contact_email="zenith@college.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    # 2. Users
    user_a = User(
        full_name="Registrar Apex",
        email="user_a@apex.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a.set_password("ApexPass123!")

    user_b = User(
        full_name="Registrar Zenith",
        email="user_b@zenith.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_b.id,
        is_active=True,
    )
    user_b.set_password("ZenithPass123!")

    officer = User(
        full_name="AICTE Officer Dashboard",
        email="officer.dash@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="System Admin Dashboard",
        email="admin.dash@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([user_a, user_b, officer, admin])
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
    }


def login_user(client, email, password):
    """Log in user and return session client."""
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()



# ---------------------------------------------------------------------------
# 1. Unauthenticated Access Tests
# ---------------------------------------------------------------------------


def test_unauthenticated_dashboard_and_report_endpoints(client):
    """Ensure dashboard, chart, report, and export endpoints require authentication (401)."""
    assert client.get("/api/dashboard/stats").status_code == 401
    assert client.get("/api/dashboard/charts").status_code == 401
    assert client.get("/api/reports/fdr").status_code == 401
    assert client.get("/api/reports/fdr/export").status_code == 401


# ---------------------------------------------------------------------------
# 2. Empty Dataset Handling
# ---------------------------------------------------------------------------


def test_empty_dashboard_and_reports(client, seed_dashboard_env):
    """Verify clean zero counts, empty lists, and 0.0 value when no records exist."""
    login_user(client, "user_a@apex.edu", "ApexPass123!")

    # 1. Stats endpoint
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["total_fdrs"] == 0
    assert data["total_value"] == 0.0
    assert data["total_value_formatted"] == "0.00"
    for status in ScrutinyStatus.values():
        assert data["status_counts"][status] == 0
    for validity in ValidityStatus.values():
        assert data["validity_counts"][validity] == 0
    assert len(data["monthly_trends"]) == 6
    assert data["recent_activity"] == []

    # 2. Charts endpoint
    res_charts = client.get("/api/dashboard/charts")
    assert res_charts.status_code == 200
    chart_data = res_charts.get_json()["data"]
    assert chart_data["summary"]["total_fdrs"] == 0
    assert chart_data["summary"]["total_value"] == 0.0

    # 3. Reports endpoint
    res_rep = client.get("/api/reports/fdr")
    assert res_rep.status_code == 200
    rep_data = res_rep.get_json()
    assert rep_data["data"] == []
    assert rep_data["pagination"]["total"] == 0
    assert rep_data["summary"]["total_records"] == 0
    assert rep_data["summary"]["total_value"] == 0.0

    # 4. CSV Export endpoint
    res_csv = client.get("/api/reports/fdr/export")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("Content-Type", "")
    lines = res_csv.data.decode("utf-8").strip().splitlines()
    assert len(lines) == 1  # Only header line


# ---------------------------------------------------------------------------
# 3. Dashboard Statistics & Maturity Boundaries
# ---------------------------------------------------------------------------


def test_dashboard_statistics_and_maturity_boundaries(client, seed_dashboard_env):
    """
    Test aggregate metrics across all 6 scrutiny statuses and exact maturity boundary classifications:
    - 40 days in future -> ACTIVE
    - 20 days in future -> EXPIRING_SOON (<= 30 days)
    - 10 days in past -> MATURED (<= 0 days)
    - 40 days in past -> OVERDUE_ACTION (<= -30 days)
    """
    user_a = seed_dashboard_env["user_a"]
    inst_a = seed_dashboard_env["inst_a"]

    ref_date = get_business_date()

    # Create 6 FDRs for Institution A
    fdrs = [
        # 1. DRAFT - ACTIVE (> 30 days)
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-A-001",
            bank_name="State Bank of India",
            branch_name="Main Branch",
            amount=Decimal("100000.00"),
            issue_date=ref_date - timedelta(days=365),
            maturity_date=ref_date + timedelta(days=40),
            scrutiny_status=ScrutinyStatus.DRAFT.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
        # 2. SUBMITTED - EXPIRING_SOON (20 days)
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-A-002",
            bank_name="Punjab National Bank",
            branch_name="City Branch",
            amount=Decimal("200000.00"),
            issue_date=ref_date - timedelta(days=365),
            maturity_date=ref_date + timedelta(days=20),
            scrutiny_status=ScrutinyStatus.SUBMITTED.value,
            validity_status=ValidityStatus.EXPIRING_SOON.value,
            created_by=user_a.id,
        ),
        # 3. PENDING_VERIFICATION - MATURED (-10 days)
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-A-003",
            bank_name="HDFC Bank",
            branch_name="South Branch",
            amount=Decimal("300000.00"),
            issue_date=ref_date - timedelta(days=400),
            maturity_date=ref_date - timedelta(days=10),
            scrutiny_status=ScrutinyStatus.PENDING_VERIFICATION.value,
            validity_status=ValidityStatus.MATURED.value,
            created_by=user_a.id,
        ),
        # 4. VERIFIED - OVERDUE_ACTION (-40 days)
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-A-004",
            bank_name="ICICI Bank",
            branch_name="Tech Park Branch",
            amount=Decimal("400000.00"),
            issue_date=ref_date - timedelta(days=450),
            maturity_date=ref_date - timedelta(days=40),
            scrutiny_status=ScrutinyStatus.VERIFIED.value,
            validity_status=ValidityStatus.OVERDUE_ACTION.value,
            created_by=user_a.id,
        ),
        # 5. RETURNED - ACTIVE
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-A-005",
            bank_name="Bank of Baroda",
            branch_name="North Branch",
            amount=Decimal("500000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=ref_date + timedelta(days=100),
            scrutiny_status=ScrutinyStatus.RETURNED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
        # 6. REJECTED - ACTIVE
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-A-006",
            bank_name="Canara Bank",
            branch_name="East Branch",
            amount=Decimal("600000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=ref_date + timedelta(days=120),
            scrutiny_status=ScrutinyStatus.REJECTED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
    ]
    db.session.add_all(fdrs)
    db.session.commit()

    # Add workflow history for FDR 5
    hist = FDRWorkflowHistory(
        fdr_id=fdrs[4].id,
        from_status=ScrutinyStatus.PENDING_VERIFICATION.value,
        to_status=ScrutinyStatus.RETURNED.value,
        actor_id=seed_dashboard_env["officer"].id,
        remarks="Missing signature page",
        is_deficiency=True,
        resolution_status="UNRESOLVED",
    )
    db.session.add(hist)
    db.session.commit()

    login_user(client, "user_a@apex.edu", "ApexPass123!")
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.get_json()["data"]

    # Total counts and value
    assert data["total_fdrs"] == 6
    expected_total_val = 100000.0 + 200000.0 + 300000.0 + 400000.0 + 500000.0 + 600000.0
    assert data["total_value"] == expected_total_val
    assert data["total_value_formatted"] == "2,100,000.00"

    # Status breakdown
    sc = data["status_counts"]
    assert sc["DRAFT"] == 1
    assert sc["SUBMITTED"] == 1
    assert sc["PENDING_VERIFICATION"] == 1
    assert sc["VERIFIED"] == 1
    assert sc["RETURNED"] == 1
    assert sc["REJECTED"] == 1

    # Validity/maturity counts
    vc = data["validity_counts"]
    assert vc["ACTIVE"] == 3  # FDR 1, 5, 6
    assert vc["EXPIRING_SOON"] == 1  # FDR 2
    assert vc["MATURED"] == 1  # FDR 3
    assert vc["OVERDUE_ACTION"] == 1  # FDR 4

    # Percentages
    for item in data["status_breakdown"]:
        assert item["count"] == 1
        assert item["percentage"] == pytest.approx(16.67, 0.05)

    # Recent activity includes our workflow transition
    assert len(data["recent_activity"]) >= 1
    act = data["recent_activity"][0]
    assert act["fdr_number"] == "FDR-A-005"
    assert act["to_status"] == "RETURNED"
    assert act["remarks"] == "Missing signature page"


# ---------------------------------------------------------------------------
# 4. Multi-Tenant Role Isolation
# ---------------------------------------------------------------------------


def test_dashboard_and_reports_role_isolation(client, seed_dashboard_env):
    """
    Verify strict isolation between Institution A and Institution B.
    Verify that AICTE Officers and Admins can view aggregate data and filter by institution.
    """
    inst_a = seed_dashboard_env["inst_a"]
    inst_b = seed_dashboard_env["inst_b"]
    user_a = seed_dashboard_env["user_a"]
    user_b = seed_dashboard_env["user_b"]
    ref_date = get_business_date()

    # Inst A: 2 FDRs, Total = 300,000
    fdr_a1 = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-ISO-A1",
        bank_name="State Bank of India",
        branch_name="Branch A1",
        amount=Decimal("100000.00"),
        issue_date=ref_date - timedelta(days=100),
        maturity_date=ref_date + timedelta(days=100),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    fdr_a2 = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-ISO-A2",
        bank_name="Canara Bank",
        branch_name="Branch A2",
        amount=Decimal("200000.00"),
        issue_date=ref_date - timedelta(days=100),
        maturity_date=ref_date + timedelta(days=100),
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )

    # Inst B: 1 FDR, Total = 500,000
    fdr_b1 = FDRRecord(
        institution_id=inst_b.id,
        fdr_number="FDR-ISO-B1",
        bank_name="HDFC Bank",
        branch_name="Branch B1",
        amount=Decimal("500000.00"),
        issue_date=ref_date - timedelta(days=100),
        maturity_date=ref_date + timedelta(days=100),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_b.id,
    )
    db.session.add_all([fdr_a1, fdr_a2, fdr_b1])
    db.session.commit()

    # 1. Institution A sees only Inst A
    login_user(client, "user_a@apex.edu", "ApexPass123!")
    res_a = client.get("/api/dashboard/stats")
    data_a = res_a.get_json()["data"]
    assert data_a["total_fdrs"] == 2
    assert data_a["total_value"] == 300000.0

    # Institution A attempting to supply institution_id=inst_b.id is rejected
    res_spoof = client.get(f"/api/dashboard/stats?institution_id={inst_b.id}")
    assert res_spoof.status_code == 400
    assert "Institution users cannot access" in res_spoof.get_json()["details"]["institution_id"]

    res_rep_spoof = client.get(f"/api/reports/fdr?institution_id={inst_b.id}")
    assert res_rep_spoof.status_code == 400
    assert "Institution users cannot" in res_rep_spoof.get_json()["details"]["institution_id"]


    # 2. Institution B sees only Inst B
    login_user(client, "user_b@zenith.edu", "ZenithPass123!")
    res_b = client.get("/api/dashboard/stats")
    data_b = res_b.get_json()["data"]
    assert data_b["total_fdrs"] == 1
    assert data_b["total_value"] == 500000.0

    # 3. AICTE Officer sees all 3 FDRs (Total = 800,000)
    login_user(client, "officer.dash@aicte.gov.in", "OfficerPass123!")
    res_off = client.get("/api/dashboard/stats")
    data_off = res_off.get_json()["data"]
    assert data_off["total_fdrs"] == 3
    assert data_off["total_value"] == 800000.0

    # Officer can filter by institution_id=inst_a.id
    res_off_a = client.get(f"/api/dashboard/stats?institution_id={inst_a.id}")
    data_off_a = res_off_a.get_json()["data"]
    assert data_off_a["total_fdrs"] == 2
    assert data_off_a["total_value"] == 300000.0


# ---------------------------------------------------------------------------
# 5. Report Filtering, Sorting, and Pagination
# ---------------------------------------------------------------------------


def test_fdr_report_filtering_sorting_and_pagination(client, seed_dashboard_env):
    """Verify database-side filtering, sorting, pagination, and aggregate summary in reports."""
    inst_a = seed_dashboard_env["inst_a"]
    user_a = seed_dashboard_env["user_a"]
    ref_date = get_business_date()

    # Seed 5 FDR records
    records = [
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-REP-01",
            bank_name="Axis Bank",
            branch_name="Branch 1",
            amount=Decimal("150000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=date(2027, 1, 1),
            scrutiny_status=ScrutinyStatus.DRAFT.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-REP-02",
            bank_name="HDFC Bank",
            branch_name="Branch 2",
            amount=Decimal("350000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=date(2027, 6, 1),
            scrutiny_status=ScrutinyStatus.VERIFIED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-REP-03",
            bank_name="Axis Bank",
            branch_name="Branch 3",
            amount=Decimal("250000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=date(2027, 3, 1),
            scrutiny_status=ScrutinyStatus.VERIFIED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-REP-04",
            bank_name="SBI",
            branch_name="Branch 4",
            amount=Decimal("500000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=date(2028, 1, 1),
            scrutiny_status=ScrutinyStatus.SUBMITTED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
        FDRRecord(
            institution_id=inst_a.id,
            fdr_number="FDR-REP-05",
            bank_name="Axis Bank",
            branch_name="Branch 5",
            amount=Decimal("100000.00"),
            issue_date=ref_date - timedelta(days=100),
            maturity_date=date(2028, 6, 1),
            scrutiny_status=ScrutinyStatus.REJECTED.value,
            validity_status=ValidityStatus.ACTIVE.value,
            created_by=user_a.id,
        ),
    ]
    db.session.add_all(records)
    db.session.commit()

    login_user(client, "user_a@apex.edu", "ApexPass123!")

    # 1. Filter by scrutiny_status
    res = client.get("/api/reports/fdr?scrutiny_status=VERIFIED")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["data"]) == 2
    assert data["summary"]["total_records"] == 2
    assert data["summary"]["total_value"] == 600000.0  # 350k + 250k

    # 2. Filter by bank_name
    res_bank = client.get("/api/reports/fdr?bank_name=axis")
    assert res_bank.status_code == 200
    data_bank = res_bank.get_json()
    assert len(data_bank["data"]) == 3
    for rec in data_bank["data"]:
        assert "Axis" in rec["bank_name"]

    # 3. Filter by maturity date range
    res_mat = client.get("/api/reports/fdr?maturity_from=2027-01-01&maturity_to=2027-05-01")
    assert res_mat.status_code == 200
    data_mat = res_mat.get_json()
    assert len(data_mat["data"]) == 2  # REP-01 (Jan 2027) and REP-03 (Mar 2027)

    # 4. Sorting: sort_by=amount&order=asc
    res_sort = client.get("/api/reports/fdr?sort_by=amount&order=asc")
    assert res_sort.status_code == 200
    items = res_sort.get_json()["data"]
    amounts = [float(x["amount"]) for x in items]
    assert amounts == sorted(amounts)

    # Sorting: sort_by=amount&order=desc
    res_sort_desc = client.get("/api/reports/fdr?sort_by=amount&order=desc")
    assert res_sort_desc.status_code == 200
    items_desc = res_sort_desc.get_json()["data"]
    amounts_desc = [float(x["amount"]) for x in items_desc]
    assert amounts_desc == sorted(amounts, reverse=True)

    # 5. Pagination: page 1 of per_page=2
    res_p1 = client.get("/api/reports/fdr?page=1&per_page=2")
    assert res_p1.status_code == 200
    p1 = res_p1.get_json()
    assert len(p1["data"]) == 2
    assert p1["pagination"]["page"] == 1
    assert p1["pagination"]["pages"] == 3
    assert p1["pagination"]["total"] == 5
    assert p1["pagination"]["has_next"] is True
    assert p1["pagination"]["has_prev"] is False

    # Page 2
    res_p2 = client.get("/api/reports/fdr?page=2&per_page=2")
    p2 = res_p2.get_json()
    assert len(p2["data"]) == 2
    assert p2["pagination"]["page"] == 2
    assert p2["pagination"]["has_next"] is True
    assert p2["pagination"]["has_prev"] is True

    # Page 3
    res_p3 = client.get("/api/reports/fdr?page=3&per_page=2")
    p3 = res_p3.get_json()
    assert len(p3["data"]) == 1
    assert p3["pagination"]["page"] == 3
    assert p3["pagination"]["has_next"] is False
    assert p3["pagination"]["has_prev"] is True


# ---------------------------------------------------------------------------
# 6. Report Validation Error Handling
# ---------------------------------------------------------------------------


def test_fdr_report_parameter_validation_errors(client, seed_dashboard_env):
    """Verify that invalid filters, sorting parameters, and date ranges return 400 VALIDATION_ERROR."""
    login_user(client, "user_a@apex.edu", "ApexPass123!")

    # Invalid scrutiny_status
    res1 = client.get("/api/reports/fdr?scrutiny_status=NON_EXISTENT")
    assert res1.status_code == 400
    assert "Invalid scrutiny status" in res1.get_json()["details"]["scrutiny_status"]

    # Invalid validity_status
    res2 = client.get("/api/reports/fdr?validity_status=BOGUS")
    assert res2.status_code == 400
    assert "Invalid validity status" in res2.get_json()["details"]["validity_status"]

    # Inverted maturity range
    res3 = client.get("/api/reports/fdr?maturity_from=2028-01-01&maturity_to=2027-01-01")
    assert res3.status_code == 400
    assert "cannot be after" in res3.get_json()["details"]["maturity_from"]

    # Invalid sort_by column
    res4 = client.get("/api/reports/fdr?sort_by=password")
    assert res4.status_code == 400
    assert "Invalid sort field" in res4.get_json()["details"]["sort_by"]

    # Invalid sort order
    res5 = client.get("/api/reports/fdr?order=sideways")
    assert res5.status_code == 400
    assert "Sort order must be 'asc' or 'desc'" in res5.get_json()["details"]["order"]

    # Invalid page parameter
    res6 = client.get("/api/reports/fdr?page=-1")
    assert res6.status_code == 400
    assert "Page parameter must be a positive integer" in res6.get_json()["details"]["page"]

    # Invalid per_page parameter
    res7 = client.get("/api/reports/fdr?per_page=500")
    assert res7.status_code == 400
    assert "between 1 and 100" in res7.get_json()["details"]["per_page"]


# ---------------------------------------------------------------------------
# 7. CSV Export & Formula Injection Protection
# ---------------------------------------------------------------------------


def test_csv_export_content_and_formula_injection_defense(client, seed_dashboard_env):
    """
    Verify CSV export:
    - Returns text/csv with attachment header and filename.
    - Sanitizes malicious spreadsheet formulas (=, +, -, @) to prevent CSV Injection (CWE-1236).
    - Preserves data integrity and tenant isolation.
    """
    inst_a = seed_dashboard_env["inst_a"]
    user_a = seed_dashboard_env["user_a"]
    ref_date = get_business_date()

    # Create FDR record with formula characters in user-controlled fields
    injection_fdr = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="=CMD|' /C calc'!A0",
        bank_name="+SUM(1,2)",
        branch_name="@ALERT",
        amount=Decimal("750000.00"),
        issue_date=ref_date - timedelta(days=100),
        maturity_date=ref_date + timedelta(days=200),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    db.session.add(injection_fdr)
    db.session.commit()

    login_user(client, "user_a@apex.edu", "ApexPass123!")

    res = client.get("/api/reports/fdr/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("Content-Type", "")
    assert "attachment; filename=" in res.headers.get("Content-Disposition", "")

    csv_text = res.data.decode("utf-8")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Verify header row
    assert rows[0] == [
        "FDR ID",
        "FDR Number",
        "Institution ID",
        "Institution Name",
        "Bank Name",
        "Branch Name",
        "Amount (INR)",
        "Issue Date",
        "Maturity Date",
        "Workflow Status",
        "Validity Status",
        "Created At (UTC)",
    ]

    # Verify sanitized data row
    data_row = rows[1]
    # Cells starting with formula characters must have a leading single quote (')
    assert data_row[1] == "'=CMD|' /C calc'!A0"
    assert data_row[4] == "'+SUM(1,2)"
    assert data_row[5] == "'@ALERT"
    assert data_row[6] == "750000.00"
    assert data_row[9] == "DRAFT"
    assert data_row[10] == "ACTIVE"
