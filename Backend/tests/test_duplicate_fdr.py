from datetime import date
from decimal import Decimal
import pytest

from app.extensions import db
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User


@pytest.fixture
def dup_env(app):
    inst1 = Institution(institution_code="AICTE-DUP-1", name="Alpha Institute", contact_email="inst1@dup.com")
    inst2 = Institution(institution_code="AICTE-DUP-2", name="Beta Polytechnic", contact_email="inst2@dup.com")
    db.session.add_all([inst1, inst2])
    db.session.commit()

    user1 = User(full_name="User Alpha", email="user1@dup.com", role=UserRole.INSTITUTION, institution_id=inst1.id)
    user1.set_password("AlphaPass123!")

    user2 = User(full_name="User Beta", email="user2@dup.com", role=UserRole.INSTITUTION, institution_id=inst2.id)
    user2.set_password("BetaPass123!")

    officer = User(full_name="Officer Dup", email="officer@dup.com", role=UserRole.AICTE_OFFICER)
    officer.set_password("OfficerPass123!")

    db.session.add_all([user1, user2, officer])
    db.session.commit()

    # Pre-existing FDR in Institution 1
    fdr1 = FDRRecord(
        institution_id=inst1.id,
        fdr_number="FDR-SBI-100200",
        bank_name="State Bank of India",
        branch_name="Branch 1",
        amount=Decimal("1000000.00"),
        issue_date=date(2024, 1, 1),
        maturity_date=date(2029, 1, 1),
        scrutiny_status=ScrutinyStatus.DRAFT.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=user1.id,
    )
    db.session.add(fdr1)
    db.session.commit()

    return {
        "inst1": inst1,
        "inst2": inst2,
        "user1": user1,
        "user2": user2,
        "officer": officer,
        "fdr1": fdr1,
    }


def login_client(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.get_json()["csrf_token"]


def test_intra_institution_duplicate_detection(client, dup_env):
    """Verify exact and normalized duplicate FDR rejection within same institution."""
    csrf1 = login_client(client, "user1@dup.com", "AlphaPass123!")

    # Exact duplicate
    res_exact = client.post(
        "/api/fdr",
        json={
            "fdr_number": "FDR-SBI-100200",
            "bank_name": "State Bank of India",
            "branch_name": "Branch 1",
            "amount": "500000.00",
            "issue_date": "2024-01-01",
            "maturity_date": "2029-01-01",
        },
        headers={"X-CSRF-Token": csrf1},
    )
    assert res_exact.status_code == 409
    assert res_exact.get_json()["code"] == "DUPLICATE_FDR_NUMBER"

    # Normalized duplicate (different hyphens/spaces/casing)
    res_norm = client.post(
        "/api/fdr",
        json={
            "fdr_number": " fdr sbi 100200 ",
            "bank_name": "State Bank of India",
            "branch_name": "Branch 1",
            "amount": "500000.00",
            "issue_date": "2024-01-01",
            "maturity_date": "2029-01-01",
        },
        headers={"X-CSRF-Token": csrf1},
    )
    assert res_norm.status_code == 409
    assert res_norm.get_json()["code"] == "DUPLICATE_FDR_NUMBER"


def test_cross_institution_duplicate_check_and_creation(client, dup_env):
    """Verify cross-institution duplicate gives generic warning to institutions without leaking names, while officers see details."""
    csrf2 = login_client(client, "user2@dup.com", "BetaPass123!")

    # Institution 2 pre-check duplicate endpoint
    res_check = client.post(
        "/api/fdr/check-duplicate",
        json={"fdr_number": "FDR-SBI-100200"},
        headers={"X-CSRF-Token": csrf2},
    )
    assert res_check.status_code == 200
    data_check = res_check.get_json()
    assert data_check["is_duplicate"] is True
    assert data_check["scope"] == "CROSS_INSTITUTION"
    # Crucial: Must NOT leak Institution 1 name to Institution 2!
    assert "Alpha Institute" not in data_check["message"]

    # AICTE Officer checks duplicate endpoint: Officer CAN see cross-institution reference
    csrf_off = login_client(client, "officer@dup.com", "OfficerPass123!")
    res_off_check = client.post(
        "/api/fdr/check-duplicate",
        json={"fdr_number": "FDR-SBI-100200", "institution_id": dup_env["inst2"].id},
        headers={"X-CSRF-Token": csrf_off},
    )
    assert res_off_check.status_code == 200
    data_off = res_off_check.get_json()
    assert data_off["is_duplicate"] is True
    assert data_off["scope"] == "CROSS_INSTITUTION"
    assert data_off["institution_name"] == "Alpha Institute"

    # Institution 2 logs back in and creates record (allowed by composite unique constraint uq_institution_fdr_number)
    csrf2 = login_client(client, "user2@dup.com", "BetaPass123!")
    res_create = client.post(
        "/api/fdr",
        json={
            "fdr_number": "FDR-SBI-100200",
            "bank_name": "State Bank of India",
            "branch_name": "Other Branch",
            "amount": "1000000.00",
            "issue_date": "2024-01-01",
            "maturity_date": "2029-01-01",
        },
        headers={"X-CSRF-Token": csrf2},
    )
    assert res_create.status_code == 201
