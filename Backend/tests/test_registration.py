import pytest
from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.institution import Institution
from app.models.user import User


def test_public_institution_registration_success(client):
    """Verify successful registration of a new institution and its user account."""
    payload = {
        "name": "Global Institute of Technology & Research",
        "email": "registrar@globaltech.edu.in",
        "contact_person": "Dr. Ananya Sharma",
        "contact_phone": "+91-9876543210",
        "address": "Sector 45, Knowledge Park, New Delhi",
        "institution_code": "AICTE-1-GLOBAL01",
        "password": "GlobalPass2026!",
        "confirm_password": "GlobalPass2026!",
    }

    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert "registered successfully" in data["message"]

    # Verify user data structure
    user_data = data["user"]
    assert user_data["email"] == "registrar@globaltech.edu.in"
    assert user_data["full_name"] == "Dr. Ananya Sharma"
    assert user_data["role_category"] == "INSTITUTION"
    assert "password_hash" not in user_data
    assert "password" not in user_data

    # Verify institution record in database
    inst = Institution.query.filter_by(institution_code="AICTE-1-GLOBAL01").first()
    assert inst is not None
    assert inst.name == "Global Institute of Technology & Research"
    assert inst.contact_phone == "+91-9876543210"

    # Verify user record in database
    user = User.query.filter_by(email="registrar@globaltech.edu.in").first()
    assert user is not None
    assert user.institution_id == inst.id
    assert user.role in (UserRole.INSTITUTION.value, UserRole.INSTITUTION_USER.value)
    assert user.check_password("GlobalPass2026!") is True

    # Verify audit log entry
    audit = AuditLog.query.filter_by(action="INSTITUTION_REGISTERED", entity_id=inst.id).first()
    assert audit is not None
    assert "registrar@globaltech.edu.in" in audit.details


def test_login_immediately_after_registration(client):
    """Verify that a newly registered institution can immediately log in."""
    payload = {
        "name": "Apex Engineering Academy",
        "email": "dean@apexacademy.edu",
        "contact_person": "Prof. R. K. Verma",
        "password": "ApexPassword123!",
        "confirm_password": "ApexPassword123!",
    }

    reg_res = client.post("/api/auth/register", json=payload)
    assert reg_res.status_code == 201

    # Attempt login with registered credentials
    login_res = client.post(
        "/api/auth/login",
        json={"email": "dean@apexacademy.edu", "password": "ApexPassword123!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.get_json()
    assert login_data["user"]["email"] == "dean@apexacademy.edu"
    assert login_data["csrf_token"] is not None


def test_privileged_roles_rejected_on_registration(client):
    """Ensure callers cannot register as ADMIN or AICTE_OFFICER."""
    for forbidden_role in ["ADMIN", "AICTE_OFFICER", "AICTE_ADMIN", "SYSTEM_ADMIN"]:
        payload = {
            "name": "Fake Bureau Office",
            "email": f"attacker_{forbidden_role.lower()}@rogue.com",
            "contact_person": "Malicious User",
            "password": "RoguePassword123!",
            "confirm_password": "RoguePassword123!",
            "role": forbidden_role,
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 403
        data = res.get_json()
        assert data["code"] == "FORBIDDEN_ROLE"


def test_duplicate_email_rejected(client):
    """Verify that duplicate user emails return 409 Conflict."""
    payload1 = {
        "name": "First Institute",
        "email": "principal@duplicatetest.org",
        "contact_person": "Dr. First",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!",
    }
    res1 = client.post("/api/auth/register", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "name": "Second Institute",
        "email": "principal@duplicatetest.org",
        "contact_person": "Dr. Second",
        "password": "SecurePassword2!",
        "confirm_password": "SecurePassword2!",
    }
    res2 = client.post("/api/auth/register", json=payload2)
    assert res2.status_code == 409
    data = res2.get_json()
    assert data["code"] == "EMAIL_ALREADY_EXISTS"


def test_duplicate_institution_code_rejected(client):
    """Verify that duplicate institution codes return 409 Conflict."""
    payload1 = {
        "name": "College Alpha",
        "email": "user1@collegealpha.org",
        "contact_person": "Officer One",
        "institution_code": "AICTE-DUP-CODE-99",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!",
    }
    res1 = client.post("/api/auth/register", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "name": "College Beta",
        "email": "user2@collegebeta.org",
        "contact_person": "Officer Two",
        "institution_code": "AICTE-DUP-CODE-99",
        "password": "SecurePassword2!",
        "confirm_password": "SecurePassword2!",
    }
    res2 = client.post("/api/auth/register", json=payload2)
    assert res2.status_code == 409
    data = res2.get_json()
    assert data["code"] == "INSTITUTION_CODE_EXISTS"


def test_registration_validation_errors(client):
    """Verify validation of missing required fields and password mismatch."""
    # Empty body
    res_empty = client.post("/api/auth/register", json={})
    assert res_empty.status_code == 400
    assert "details" in res_empty.get_json()

    # Password mismatch
    res_mismatch = client.post(
        "/api/auth/register",
        json={
            "name": "Valid Name",
            "email": "valid@email.com",
            "contact_person": "Contact Name",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!",
        },
    )
    assert res_mismatch.status_code == 400
    assert "confirm_password" in res_mismatch.get_json()["details"]

    # Short password
    res_short_pw = client.post(
        "/api/auth/register",
        json={
            "name": "Valid Name",
            "email": "valid2@email.com",
            "contact_person": "Contact Name",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert res_short_pw.status_code == 400
    assert "password" in res_short_pw.get_json()["details"]
