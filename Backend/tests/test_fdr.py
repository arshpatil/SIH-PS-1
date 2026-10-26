from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User


@pytest.fixture
def seed_fdr_env(app):
    """Seed institutions, users across roles, and baseline FDR records."""
    # Institutions
    inst_a = Institution(
        institution_code="AICTE-INST-A",
        name="Alpha Engineering Institute",
        contact_email="director@alpha.edu",
    )
    inst_b = Institution(
        institution_code="AICTE-INST-B",
        name="Beta Technical College",
        contact_email="director@beta.edu",
    )
    db.session.add_all([inst_a, inst_b])
    db.session.commit()

    # Users
    user_a = User(
        full_name="Registrar Alpha",
        email="registrar@alpha.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_a.id,
        is_active=True,
    )
    user_a.set_password("AlphaPass123!")

    user_b = User(
        full_name="Registrar Beta",
        email="registrar@beta.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_b.id,
        is_active=True,
    )
    user_b.set_password("BetaPass123!")

    officer = User(
        full_name="Scrutiny Officer",
        email="officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    admin = User(
        full_name="System Admin",
        email="admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminPass123!")

    db.session.add_all([user_a, user_b, officer, admin])
    db.session.commit()

    # Baseline FDRs
    fdr_a1 = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-ALPHA-001",
        bank_name="State Bank of India",
        branch_name="Main Branch",
        amount=Decimal("500000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2030, 1, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    fdr_a2 = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-ALPHA-002",
        bank_name="Punjab National Bank",
        branch_name="Tech Zone",
        amount=Decimal("1200000.00"),
        issue_date=date(2025, 3, 1),
        maturity_date=date(2030, 3, 1),
        scrutiny_status=ScrutinyStatus.SUBMITTED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    fdr_a3 = FDRRecord(
        institution_id=inst_a.id,
        fdr_number="FDR-ALPHA-003",
        bank_name="HDFC Bank",
        branch_name="City Center",
        amount=Decimal("800000.00"),
        issue_date=date(2025, 5, 1),
        maturity_date=date(2028, 5, 1),
        scrutiny_status=ScrutinyStatus.RETURNED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_a.id,
    )
    fdr_b1 = FDRRecord(
        institution_id=inst_b.id,
        fdr_number="FDR-BETA-001",
        bank_name="ICICI Bank",
        branch_name="North Campus",
        amount=Decimal("2000000.00"),
        issue_date=date(2025, 2, 1),
        maturity_date=date(2032, 2, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user_b.id,
    )
    db.session.add_all([fdr_a1, fdr_a2, fdr_a3, fdr_b1])
    db.session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "user_a": user_a,
        "user_b": user_b,
        "officer": officer,
        "admin": admin,
        "fdr_a1": fdr_a1,
        "fdr_a2": fdr_a2,
        "fdr_a3": fdr_a3,
        "fdr_b1": fdr_b1,
    }


def login_and_get_csrf(client, email, password):
    """Helper to log in and extract session CSRF token."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def test_fdr_unauthenticated_access(client):
    """Test that all FDR endpoints return 401 when not authenticated."""
    assert client.get("/api/fdr").status_code == 401
    assert client.get("/api/fdr/1").status_code == 401
    assert client.post("/api/fdr", json={}).status_code == 401
    assert client.patch("/api/fdr/1", json={}).status_code == 401


def test_fdr_create_success_institution_user(client, seed_fdr_env):
    """Test institution user creating a valid FDR record for their institution."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    payload = {
        "fdr_number": "SBI-NEW-2025-01",
        "bank_name": "State Bank of India",
        "branch_name": "Connaught Place",
        "amount": "1500000.00",
        "issue_date": "2025-06-01",
        "maturity_date": "2030-06-01",
    }
    response = client.post(
        "/api/fdr",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 201
    assert response.is_json
    data = response.get_json()
    assert data["success"] is True

    record = data["data"]
    assert record["fdr_number"] == "SBI-NEW-2025-01"
    assert record["amount"] == "1500000.00"
    assert record["institution_id"] == seed_fdr_env["inst_a"].id
    assert record["institution_name"] == "Alpha Engineering Institute"
    assert record["scrutiny_status"] == "DRAFT"
    assert record["validity_status"] == "ACTIVE"


def test_fdr_institution_user_cannot_forge_institution_id(client, seed_fdr_env):
    """Test that client-supplied institution_id is ignored and derived from authenticated user."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    # User A attempts to forge Institution B's ID
    forged_inst_id = seed_fdr_env["inst_b"].id
    payload = {
        "institution_id": forged_inst_id,
        "fdr_number": "FORGE-ATTEMPT-001",
        "bank_name": "Canara Bank",
        "branch_name": "Tech Branch",
        "amount": "800000.00",
        "issue_date": "2025-01-01",
        "maturity_date": "2030-01-01",
    }
    response = client.post(
        "/api/fdr",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 201
    record = response.get_json()["data"]
    # Verified: Assigned to Institution A, not forged Institution B
    assert record["institution_id"] == seed_fdr_env["inst_a"].id


def test_fdr_create_missing_and_malformed_fields(client, seed_fdr_env):
    """Test field-level validation errors for missing or empty fields."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    # Empty payload
    res1 = client.post("/api/fdr", json={}, headers={"X-CSRF-Token": csrf_token})
    assert res1.status_code == 400
    assert res1.get_json()["code"] == "VALIDATION_ERROR"
    details = res1.get_json()["details"]
    assert "fdr_number" in details
    assert "bank_name" in details
    assert "branch_name" in details
    assert "amount" in details
    assert "issue_date" in details
    assert "maturity_date" in details


def test_fdr_create_invalid_amount_and_dates(client, seed_fdr_env):
    """Test rejection of booleans, negative amounts, invalid dates, and inverted maturity dates."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    # Boolean amount rejected
    res_bool = client.post(
        "/api/fdr",
        json={
            "fdr_number": "TEST-01",
            "bank_name": "Bank",
            "branch_name": "Branch",
            "amount": True,
            "issue_date": "2025-01-01",
            "maturity_date": "2030-01-01",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_bool.status_code == 400
    assert "Amount must be a numeric value" in res_bool.get_json()["details"]["amount"]

    # Negative amount rejected
    res_neg = client.post(
        "/api/fdr",
        json={
            "fdr_number": "TEST-02",
            "bank_name": "Bank",
            "branch_name": "Branch",
            "amount": "-500.00",
            "issue_date": "2025-01-01",
            "maturity_date": "2030-01-01",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_neg.status_code == 400
    assert "greater than zero" in res_neg.get_json()["details"]["amount"]

    # Inverted maturity date rejected (maturity < issue)
    res_inverted = client.post(
        "/api/fdr",
        json={
            "fdr_number": "TEST-03",
            "bank_name": "Bank",
            "branch_name": "Branch",
            "amount": "50000.00",
            "issue_date": "2028-01-01",
            "maturity_date": "2025-01-01",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_inverted.status_code == 400
    assert "Maturity date cannot be earlier" in res_inverted.get_json()["details"]["maturity_date"]


def test_fdr_duplicate_number_same_institution(client, seed_fdr_env):
    """Test duplicate FDR number within the SAME institution returns HTTP 409 Conflict."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    # Attempt to create FDR with already existing number "FDR-ALPHA-001" for Institution A
    payload = {
        "fdr_number": "FDR-ALPHA-001",
        "bank_name": "SBI",
        "branch_name": "Branch",
        "amount": "600000.00",
        "issue_date": "2025-01-01",
        "maturity_date": "2030-01-01",
    }
    response = client.post(
        "/api/fdr",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "DUPLICATE_FDR_NUMBER"


def test_fdr_same_number_allowed_for_different_institutions(client, seed_fdr_env):
    """Test that the same FDR number is permitted across DIFFERENT institutions."""
    csrf_token = login_and_get_csrf(client, "registrar@beta.edu", "BetaPass123!")

    # User B creates FDR with number "FDR-ALPHA-001" (which belongs to Institution A)
    payload = {
        "fdr_number": "FDR-ALPHA-001",
        "bank_name": "Central Bank",
        "branch_name": "Beta Branch",
        "amount": "990000.00",
        "issue_date": "2025-01-01",
        "maturity_date": "2030-01-01",
    }
    response = client.post(
        "/api/fdr",
        json=payload,
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["institution_id"] == seed_fdr_env["inst_b"].id


def test_fdr_list_data_isolation(client, seed_fdr_env):
    """Test that institution users see ONLY their own records, while officers see all."""
    # 1. Institution A user
    login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")
    res_a = client.get("/api/fdr")
    assert res_a.status_code == 200
    data_a = res_a.get_json()["data"]
    # All records must belong to Institution A
    assert len(data_a) == 3
    for rec in data_a:
        assert rec["institution_id"] == seed_fdr_env["inst_a"].id

    # 2. Institution B user
    login_and_get_csrf(client, "registrar@beta.edu", "BetaPass123!")
    res_b = client.get("/api/fdr")
    assert res_b.status_code == 200
    data_b = res_b.get_json()["data"]
    assert len(data_b) == 1
    assert data_b[0]["institution_id"] == seed_fdr_env["inst_b"].id

    # 3. AICTE Officer
    login_and_get_csrf(client, "officer@aicte.gov.in", "OfficerPass123!")
    res_off = client.get("/api/fdr")
    assert res_off.status_code == 200
    data_off = res_off.get_json()["data"]
    # Officer sees all 4 seeded records
    assert len(data_off) == 4


def test_fdr_detail_access_and_cross_institution_404(client, seed_fdr_env):
    """Test retrieval of own FDR succeeds, but requesting another institution's FDR returns 404."""
    # Institution A user
    login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    # Own record -> 200
    own_id = seed_fdr_env["fdr_a1"].id
    res_own = client.get(f"/api/fdr/{own_id}")
    assert res_own.status_code == 200
    assert res_own.get_json()["data"]["id"] == own_id

    # Other institution's record -> 404 (not 403, preventing existence leakage)
    other_id = seed_fdr_env["fdr_b1"].id
    res_other = client.get(f"/api/fdr/{other_id}")
    assert res_other.status_code == 404

    # Non-existent ID -> 404
    assert client.get("/api/fdr/999999").status_code == 404

    # Officer can access both
    login_and_get_csrf(client, "officer@aicte.gov.in", "OfficerPass123!")
    assert client.get(f"/api/fdr/{own_id}").status_code == 200
    assert client.get(f"/api/fdr/{other_id}").status_code == 200


def test_fdr_filtering_and_pagination(client, seed_fdr_env):
    """Test list filtering by bank, status, date range, search, and pagination."""
    login_and_get_csrf(client, "officer@aicte.gov.in", "OfficerPass123!")

    # Filter by bank_name
    res_bank = client.get("/api/fdr?bank_name=State Bank")
    assert res_bank.status_code == 200
    assert len(res_bank.get_json()["data"]) == 1

    # Filter by scrutiny_status
    res_status = client.get("/api/fdr?scrutiny_status=DRAFT")
    assert res_status.status_code == 200
    assert len(res_status.get_json()["data"]) == 2

    # Filter by maturity date range
    res_mat = client.get("/api/fdr?maturity_from=2029-01-01&maturity_to=2031-01-01")
    assert res_mat.status_code == 200
    assert len(res_mat.get_json()["data"]) == 2

    # Global search on FDR number or branch
    res_search = client.get("/api/fdr?search=City Center")
    assert res_search.status_code == 200
    assert len(res_search.get_json()["data"]) == 1

    # Pagination test
    res_page = client.get("/api/fdr?page=1&per_page=2")
    assert res_page.status_code == 200
    pag = res_page.get_json()["pagination"]
    assert pag["page"] == 1
    assert pag["per_page"] == 2
    assert pag["total"] == 4
    assert pag["pages"] == 2
    assert len(res_page.get_json()["data"]) == 2


def test_fdr_patch_institution_editable_status(client, seed_fdr_env):
    """Test institution can edit DRAFT and RETURNED records, but NOT SUBMITTED/VERIFIED records."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")

    # 1. Update DRAFT record (fdr_a1) -> Allowed
    draft_id = seed_fdr_env["fdr_a1"].id
    res_draft = client.patch(
        f"/api/fdr/{draft_id}",
        json={"amount": "650000.00", "branch_name": "Updated Branch"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_draft.status_code == 200
    assert res_draft.get_json()["data"]["amount"] == "650000.00"
    assert res_draft.get_json()["data"]["branch_name"] == "Updated Branch"

    # 2. Update RETURNED record (fdr_a3) -> Allowed
    returned_id = seed_fdr_env["fdr_a3"].id
    res_ret = client.patch(
        f"/api/fdr/{returned_id}",
        json={"branch_name": "Corrected Branch"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_ret.status_code == 200

    # 3. Update SUBMITTED record (fdr_a2) -> 403 Forbidden (Locked)
    sub_id = seed_fdr_env["fdr_a2"].id
    res_sub = client.patch(
        f"/api/fdr/{sub_id}",
        json={"branch_name": "Attempted Edit"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_sub.status_code == 403
    assert res_sub.get_json()["code"] == "RECORD_LOCKED"


def test_fdr_institution_cannot_set_officer_status(client, seed_fdr_env):
    """Test institution user cannot directly mark record as VERIFIED, REJECTED, or RETURNED."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")
    draft_id = seed_fdr_env["fdr_a1"].id

    # Institution user tries to self-verify -> 403
    res = client.patch(
        f"/api/fdr/{draft_id}",
        json={"scrutiny_status": "VERIFIED"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res.status_code == 403
    assert res.get_json()["code"] == "OFFICER_STATUS_RESTRICTED"

    # Institution user submitting for verification (DRAFT -> SUBMITTED) -> Allowed
    res_submit = client.patch(
        f"/api/fdr/{draft_id}",
        json={"scrutiny_status": "SUBMITTED"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_submit.status_code == 200
    assert res_submit.get_json()["data"]["scrutiny_status"] == "SUBMITTED"


def test_fdr_officer_can_update_status(client, seed_fdr_env):
    """Test that AICTE officer can update scrutiny_status to VERIFIED or REJECTED."""
    csrf_token = login_and_get_csrf(client, "officer@aicte.gov.in", "OfficerPass123!")
    sub_id = seed_fdr_env["fdr_a2"].id

    res = client.patch(
        f"/api/fdr/{sub_id}",
        json={"scrutiny_status": "VERIFIED"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["scrutiny_status"] == "VERIFIED"


def test_fdr_patch_immutable_fields_and_conflict(client, seed_fdr_env):
    """Test that PATCH rejects immutable field changes and duplicate number conflicts."""
    csrf_token = login_and_get_csrf(client, "registrar@alpha.edu", "AlphaPass123!")
    draft_id = seed_fdr_env["fdr_a1"].id

    # Attempt to change immutable field (institution_id)
    res_immut = client.patch(
        f"/api/fdr/{draft_id}",
        json={"institution_id": 9999},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_immut.status_code == 400
    assert "immutable" in res_immut.get_json()["details"]["institution_id"]

    # Attempt to rename fdr_number to another existing FDR in Institution A ("FDR-ALPHA-002")
    res_dup = client.patch(
        f"/api/fdr/{draft_id}",
        json={"fdr_number": "FDR-ALPHA-002"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_dup.status_code == 409
    assert res_dup.get_json()["code"] == "DUPLICATE_FDR_NUMBER"
