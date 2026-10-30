from datetime import date, timedelta
from decimal import Decimal
import json
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.bank_verification import BankVerificationLog
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.models.institution import Institution
from app.models.user import User
from app.services.bank_integration.base import (
    BankRenewalStatus,
    BankVerificationStatus,
    ProviderMode,
)
from app.services.bank_integration.factory import get_bank_provider, get_provider_info
from app.services.bank_integration.mock_provider import MockBankProvider


@pytest.fixture
def bank_test_env(app):
    """Seed test database with 2 institutions, an officer, and test FDRs."""
    inst_1 = Institution(
        institution_code="AICTE-BANK-001",
        name="Institute of Computer Science",
        contact_email="dean@ics.edu",
    )
    inst_2 = Institution(
        institution_code="AICTE-BANK-002",
        name="National Engineering Institute",
        contact_email="principal@nei.edu",
    )
    db.session.add_all([inst_1, inst_2])
    db.session.commit()

    inst1_user = User(
        full_name="Dean ICS",
        email="dean@ics.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_1.id,
        is_active=True,
    )
    inst1_user.set_password("SecurePass123!")

    inst2_user = User(
        full_name="Principal NEI",
        email="principal@nei.edu",
        role=UserRole.INSTITUTION,
        institution_id=inst_2.id,
        is_active=True,
    )
    inst2_user.set_password("SecurePass123!")

    officer = User(
        full_name="AICTE Verification Officer",
        email="bank.officer@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    db.session.add_all([inst1_user, inst2_user, officer])
    db.session.commit()

    # Standard valid FDR for inst 1
    fdr1 = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="FDR-SBI-445566",
        bank_name="State Bank of India",
        branch_name="Main Campus Branch",
        amount=Decimal("2000000.00"),
        issue_date=date.today() - timedelta(days=365 * 2),
        maturity_date=date.today() + timedelta(days=365),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=inst1_user.id,
    )

    # Mismatch-triggering FDR
    fdr_mismatch = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="FDR-MISMATCH-9900",
        bank_name="Punjab National Bank",
        branch_name="City Center",
        amount=Decimal("1500000.00"),
        issue_date=date.today() - timedelta(days=365 * 2),
        maturity_date=date.today() + timedelta(days=180),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=inst1_user.id,
    )

    # Missing / Not Found FDR
    fdr_notfound = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="FDR-NOTFOUND-0000",
        bank_name="Canara Bank",
        branch_name="Rural Branch",
        amount=Decimal("1000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=365),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=inst1_user.id,
    )

    # Timeout / Unavailable FDR
    fdr_timeout = FDRRecord(
        institution_id=inst_1.id,
        fdr_number="FDR-TIMEOUT-503",
        bank_name="Bank of Baroda",
        branch_name="Central Branch",
        amount=Decimal("1000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=365),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=inst1_user.id,
    )

    # FDR for inst 2 (for tenant isolation test)
    fdr2 = FDRRecord(
        institution_id=inst_2.id,
        fdr_number="FDR-HDFC-778899",
        bank_name="HDFC Bank",
        branch_name="Tech Park Branch",
        amount=Decimal("3000000.00"),
        issue_date=date.today() - timedelta(days=365),
        maturity_date=date.today() + timedelta(days=365 * 2),
        scrutiny_status=ScrutinyStatus.VERIFIED.value,
        validity_status=ValidityStatus.ACTIVE.value,
        created_by=inst2_user.id,
    )

    db.session.add_all([fdr1, fdr_mismatch, fdr_notfound, fdr_timeout, fdr2])
    db.session.commit()

    return {
        "inst_1": inst_1,
        "inst_2": inst_2,
        "inst1_user": inst1_user,
        "inst2_user": inst2_user,
        "officer": officer,
        "fdr1": fdr1,
        "fdr_mismatch": fdr_mismatch,
        "fdr_notfound": fdr_notfound,
        "fdr_timeout": fdr_timeout,
        "fdr2": fdr2,
    }


def login(client, email, password):
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, f"Login failed: {res.get_data(as_text=True)}"
    csrf_res = client.get("/api/auth/csrf-token")
    return csrf_res.get_json()["csrf_token"]


def test_provider_factory_and_defaults(app):
    """Verify provider selection defaults to DEMO mode with mock provider."""
    provider = get_bank_provider()
    assert isinstance(provider, MockBankProvider)
    assert provider.mode == ProviderMode.DEMO
    assert provider.name == "SIMULATED_MOCK_PROVIDER"
    assert "PROTOTYPE DEMONSTRATION ONLY" in provider.disclaimer

    info = get_provider_info()
    assert info["is_demo"] is True
    assert info["is_mock"] is True
    assert len(info["supported_scenarios"]) == 4


def test_mock_provider_direct_scenarios():
    """Verify all 7 mock scenarios deterministically via unit calls."""
    provider = MockBankProvider()

    # 1. Matched
    res_matched = provider.verify_fdr(
        "FDR-TEST-001",
        "INST-01",
        expected_details={"amount": "2500000", "maturity_date": "2028-01-01"},
        simulation_scenario="MATCHED",
    )
    assert res_matched.status == BankVerificationStatus.MATCHED.value
    assert res_matched.is_mock is True
    assert res_matched.bank_reference is not None
    assert "amount" in res_matched.matched_fields

    # 2. Not Found
    res_nf = provider.verify_fdr(
        "FDR-NOTFOUND-999",
        "INST-01",
        simulation_scenario="NOT_FOUND",
    )
    assert res_nf.status == BankVerificationStatus.NOT_FOUND.value
    assert res_nf.is_mock is True

    # 3. Mismatch
    res_mis = provider.verify_fdr(
        "FDR-MISMATCH-123",
        "INST-01",
        expected_details={"amount": "2000000", "maturity_date": "2027-05-01"},
        simulation_scenario="MISMATCH",
    )
    assert res_mis.status == BankVerificationStatus.MISMATCH.value
    assert "amount" in res_mis.mismatched_fields
    assert "maturity_date" in res_mis.mismatched_fields
    assert res_mis.mismatched_fields["amount"]["expected"] == 2000000.0

    # 4. Timeout / Unavailable
    res_unavail = provider.verify_fdr(
        "FDR-TIMEOUT-500",
        "INST-01",
        simulation_scenario="UNAVAILABLE",
    )
    assert res_unavail.status == BankVerificationStatus.UNAVAILABLE.value
    assert "timeout" in res_unavail.message.lower()

    # 5. Renewal Confirmed
    ren_conf = provider.get_renewal_status("REN-CONFIRM-12345")
    assert ren_conf.status == BankRenewalStatus.CONFIRMED.value
    assert ren_conf.renewal_details is not None
    assert ren_conf.renewal_details["renewal_tenure_months"] == 36

    # 6. Renewal Pending
    ren_pend = provider.get_renewal_status("REN-PENDING-9988")
    assert ren_pend.status == BankRenewalStatus.PENDING.value

    # 7. Renewal Rejected
    ren_rej = provider.get_renewal_status("REN-REJECT-0011")
    assert ren_rej.status == BankRenewalStatus.REJECTED.value

    # Renewal initiation raises NotImplementedError in prototype
    with pytest.raises(NotImplementedError):
        provider.initiate_renewal("FDR-1", "INST-1", {})


def test_bank_verify_api_matched_and_audit(client, bank_test_env):
    """
    Test API endpoint /api/bank/verify-fdr/<id> for standard matched FDR:
    - Generates BankVerificationLog
    - Generates AuditLog with actor, provider, status
    - Invariant: Does NOT silently mutate original FDR parameters
    """
    fdr = bank_test_env["fdr1"]
    orig_fdr_num = fdr.fdr_number
    orig_amt = fdr.amount
    orig_mat = fdr.maturity_date.isoformat()

    csrf = login(client, "dean@ics.edu", "SecurePass123!")

    res = client.post(
        f"/api/bank/verify-fdr/{fdr.id}",
        json={"scenario": "MATCHED"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["verification_status"] == "MATCHED"
    assert body["data"]["is_demo"] is True
    assert "PROTOTYPE DEMONSTRATION" in body["data"]["disclaimer"]

    # Verify BankVerificationLog entry in DB
    vlog = BankVerificationLog.query.filter_by(fdr_id=fdr.id).first()
    assert vlog is not None
    assert vlog.verification_status == "MATCHED"
    assert vlog.provider_mode == "DEMO"
    assert vlog.requested_by == bank_test_env["inst1_user"].id

    # Verify AuditLog entry in DB
    audit = AuditLog.query.filter_by(
        entity_type="FDRRecord",
        entity_id=fdr.id,
        action="BANK_VERIFICATION_CHECK",
    ).first()
    assert audit is not None
    assert "SIMULATED_MOCK_PROVIDER" in audit.details
    assert "MATCHED" in audit.details

    # CRITICAL INVARIANT: The official FDR parameters MUST NOT change!
    db.session.refresh(fdr)
    assert fdr.fdr_number == orig_fdr_num
    assert fdr.amount == orig_amt
    assert fdr.maturity_date.isoformat() == orig_mat


def test_bank_verify_api_mismatch_and_timeout(client, bank_test_env):
    """Test API handling of simulated discrepancy and service timeout."""
    csrf = login(client, "dean@ics.edu", "SecurePass123!")

    # Mismatch
    fdr_mis = bank_test_env["fdr_mismatch"]
    res_mis = client.post(
        f"/api/bank/verify-fdr/{fdr_mis.id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_mis.status_code == 200
    mis_body = res_mis.get_json()
    assert mis_body["data"]["verification_status"] == "MISMATCH"
    assert "amount" in mis_body["data"]["mismatched_fields"]

    # Timeout
    fdr_to = bank_test_env["fdr_timeout"]
    res_to = client.post(
        f"/api/bank/verify-fdr/{fdr_to.id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert res_to.status_code == 200
    to_body = res_to.get_json()
    assert to_body["data"]["verification_status"] == "UNAVAILABLE"


def test_tenant_isolation_and_authorization(client, bank_test_env):
    """
    Ensure RBAC and tenant isolation:
    - Unauthenticated callers blocked (401)
    - Institution 1 cannot verify Institution 2's FDR (403)
    - Officer can verify any FDR
    """
    fdr2 = bank_test_env["fdr2"]

    # 1. Unauthenticated request -> 401
    unauth_res = client.post(f"/api/bank/verify-fdr/{fdr2.id}")
    assert unauth_res.status_code == 401

    # 2. Institution 1 tries to verify Institution 2's FDR -> 403 Forbidden
    csrf_inst1 = login(client, "dean@ics.edu", "SecurePass123!")
    cross_res = client.post(
        f"/api/bank/verify-fdr/{fdr2.id}",
        headers={"X-CSRF-Token": csrf_inst1},
    )
    assert cross_res.status_code == 403
    assert "Access denied" in cross_res.get_json()["error"]

    # Institution 1 tries to access verification history of Institution 2's FDR -> 403 Forbidden
    hist_res = client.get(f"/api/bank/history/{fdr2.id}")
    assert hist_res.status_code == 403

    # 3. Officer can verify Institution 2's FDR legitimately
    csrf_officer = login(client, "bank.officer@aicte.gov.in", "OfficerPass123!")
    officer_res = client.post(
        f"/api/bank/verify-fdr/{fdr2.id}",
        headers={"X-CSRF-Token": csrf_officer},
    )
    assert officer_res.status_code == 200
    assert officer_res.get_json()["success"] is True


def test_bank_status_endpoint(client, bank_test_env):
    """Verify /api/bank/status returns provider metadata and no secrets."""
    login(client, "dean@ics.edu", "SecurePass123!")
    res = client.get("/api/bank/status")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["provider_name"] == "SIMULATED_MOCK_PROVIDER"
    assert data["provider_mode"] == "DEMO"
    assert data["is_demo"] is True
    # Ensure no secrets leak
    assert "client_secret" not in data
    assert "BANK_CLIENT_SECRET" not in data
