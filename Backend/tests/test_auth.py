import json
import pytest
from flask import Blueprint, jsonify

from app.config import ProductionConfig
from app.extensions import db
from app.models.enums import UserRole
from app.models.institution import Institution
from app.models.user import User
from app.security import login_required, roles_required


@pytest.fixture
def seed_data(app):
    """Seed test institutions and users for authentication and RBAC tests."""
    inst = Institution(
        institution_code="AICTE-TEST-AUTH-1",
        name="IIT Delhi",
        contact_email="director@iitd.ac.in",
    )
    db.session.add(inst)
    db.session.commit()

    # Active institution user
    inst_user = User(
        full_name="Prof. Sharma",
        email="sharma@iitd.ac.in",
        role=UserRole.INSTITUTION,
        institution_id=inst.id,
        is_active=True,
    )
    inst_user.set_password("InstitutionPass123!")

    # Inactive institution user
    inactive_user = User(
        full_name="Inactive User",
        email="inactive@iitd.ac.in",
        role=UserRole.INSTITUTION,
        institution_id=inst.id,
        is_active=False,
    )
    inactive_user.set_password("InactivePass123!")

    # Institution user WITHOUT associated institution
    unlinked_inst_user = User(
        full_name="Unlinked User",
        email="unlinked@orphan.edu",
        role=UserRole.INSTITUTION,
        institution_id=None,
        is_active=True,
    )
    unlinked_inst_user.set_password("UnlinkedPass123!")

    # AICTE Officer
    officer = User(
        full_name="Officer Verma",
        email="verma@aicte.gov.in",
        role=UserRole.AICTE_OFFICER,
        institution_id=None,
        is_active=True,
    )
    officer.set_password("OfficerPass123!")

    # Admin User
    admin = User(
        full_name="Super Admin",
        email="admin@aicte.gov.in",
        role=UserRole.ADMIN,
        institution_id=None,
        is_active=True,
    )
    admin.set_password("AdminSuperPass123!")

    db.session.add_all(
        [inst_user, inactive_user, unlinked_inst_user, officer, admin]
    )
    db.session.commit()

    return {
        "institution": inst,
        "inst_user": inst_user,
        "inactive_user": inactive_user,
        "unlinked_inst_user": unlinked_inst_user,
        "officer": officer,
        "admin": admin,
    }


@pytest.fixture
def rbac_routes(app):
    """Register temporary routes to test @roles_required and @login_required."""
    rbac_bp = Blueprint("test_rbac", __name__, url_prefix="/test-rbac")

    @rbac_bp.route("/admin-only", methods=["GET"])
    @roles_required("ADMIN")
    def admin_only():
        return jsonify({"message": "admin granted"}), 200

    @rbac_bp.route("/officer-only", methods=["GET"])
    @roles_required("AICTE_OFFICER")
    def officer_only():
        return jsonify({"message": "officer granted"}), 200

    @rbac_bp.route("/institution-only", methods=["GET"])
    @roles_required("INSTITUTION")
    def inst_only():
        return jsonify({"message": "institution granted"}), 200

    @rbac_bp.route("/state-change", methods=["POST"])
    @login_required
    def state_change():
        return jsonify({"message": "state updated"}), 200

    app.register_blueprint(rbac_bp)
    return rbac_bp


def test_login_success(client, seed_data):
    """Test successful login establishes session, returns safe user data and CSRF token."""
    response = client.post(
        "/api/auth/login",
        json={"email": "sharma@iitd.ac.in", "password": "InstitutionPass123!"},
    )

    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()

    assert data["message"] == "Login successful."
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 20

    user_data = data["user"]
    assert user_data["email"] == "sharma@iitd.ac.in"
    assert user_data["role_category"] == "INSTITUTION"
    assert "password_hash" not in user_data


def test_login_invalid_credentials(client, seed_data):
    """Test invalid passwords and non-existent emails return generic 401 error."""
    # Wrong password
    res1 = client.post(
        "/api/auth/login",
        json={"email": "sharma@iitd.ac.in", "password": "WrongPassword999!"},
    )
    assert res1.status_code == 401
    assert res1.get_json()["code"] == "INVALID_CREDENTIALS"

    # Non-existent email
    res2 = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPassword123!"},
    )
    assert res2.status_code == 401
    assert res2.get_json()["code"] == "INVALID_CREDENTIALS"


def test_login_inactive_user_rejected(client, seed_data):
    """Test deactivated accounts are rejected with 403."""
    response = client.post(
        "/api/auth/login",
        json={"email": "inactive@iitd.ac.in", "password": "InactivePass123!"},
    )
    assert response.status_code == 403
    assert response.get_json()["code"] == "ACCOUNT_INACTIVE"


def test_login_unlinked_institution_user_rejected(client, seed_data):
    """Test institution user lacking an affiliated institution is safely rejected at login."""
    response = client.post(
        "/api/auth/login",
        json={"email": "unlinked@orphan.edu", "password": "UnlinkedPass123!"},
    )
    assert response.status_code == 403
    assert response.get_json()["code"] == "UNLINKED_INSTITUTION"


def test_me_unauthenticated(client):
    """Test /api/auth/me returns 401 when unauthenticated."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["code"] == "UNAUTHENTICATED"


def test_me_authenticated(client, seed_data):
    """Test /api/auth/me returns current user profile after login."""
    # Log in
    login_res = client.post(
        "/api/auth/login",
        json={"email": "verma@aicte.gov.in", "password": "OfficerPass123!"},
    )
    assert login_res.status_code == 200

    # Request /api/auth/me
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    data = me_res.get_json()
    assert data["user"]["email"] == "verma@aicte.gov.in"
    assert data["user"]["role"] == "AICTE_OFFICER"
    assert "csrf_token" in data


def test_logout_and_session_invalidation(client, seed_data):
    """Test /api/auth/logout invalidates session and prevents further authenticated requests."""
    # Log in
    login_res = client.post(
        "/api/auth/login",
        json={"email": "admin@aicte.gov.in", "password": "AdminSuperPass123!"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.get_json()["csrf_token"]

    # Verify authenticated
    me_res1 = client.get("/api/auth/me")
    assert me_res1.status_code == 200

    # Logout (requires CSRF token)
    logout_res = client.post(
        "/api/auth/logout", headers={"X-CSRF-Token": csrf_token}
    )
    assert logout_res.status_code == 200
    assert logout_res.get_json()["message"] == "Logged out successfully."

    # Verify session is cleared
    me_res2 = client.get("/api/auth/me")
    assert me_res2.status_code == 401


def test_csrf_protection_on_state_changes(client, seed_data, rbac_routes):
    """Test that authenticated state-changing requests require a valid CSRF token."""
    login_res = client.post(
        "/api/auth/login",
        json={"email": "admin@aicte.gov.in", "password": "AdminSuperPass123!"},
    )
    csrf_token = login_res.get_json()["csrf_token"]

    # Attempt state-change WITHOUT CSRF token -> 403
    res_no_csrf = client.post("/test-rbac/state-change")
    assert res_no_csrf.status_code == 403
    assert res_no_csrf.get_json()["code"] == "CSRF_ERROR"

    # Attempt state-change WITH invalid CSRF token -> 403
    res_bad_csrf = client.post(
        "/test-rbac/state-change",
        headers={"X-CSRF-Token": "invalid-tampered-token"},
    )
    assert res_bad_csrf.status_code == 403
    assert res_bad_csrf.get_json()["code"] == "CSRF_ERROR"

    # Attempt state-change WITH valid CSRF token -> 200
    res_good_csrf = client.post(
        "/test-rbac/state-change", headers={"X-CSRF-Token": csrf_token}
    )
    assert res_good_csrf.status_code == 200


def test_role_based_access_control(client, seed_data, rbac_routes):
    """Test role permissions: 401 unauthenticated, 403 forbidden role, 200 permitted role."""
    # 1. Unauthenticated access
    res = client.get("/test-rbac/admin-only")
    assert res.status_code == 401

    # 2. Log in as Institution user
    client.post(
        "/api/auth/login",
        json={"email": "sharma@iitd.ac.in", "password": "InstitutionPass123!"},
    )

    # Institution user accessing Institution endpoint -> 200
    assert client.get("/test-rbac/institution-only").status_code == 200
    # Institution user accessing Officer endpoint -> 403
    assert client.get("/test-rbac/officer-only").status_code == 403
    # Institution user accessing Admin endpoint -> 403
    assert client.get("/test-rbac/admin-only").status_code == 403

    # 3. Log in as AICTE Officer
    client.post(
        "/api/auth/login",
        json={"email": "verma@aicte.gov.in", "password": "OfficerPass123!"},
    )
    assert client.get("/test-rbac/officer-only").status_code == 200
    assert client.get("/test-rbac/institution-only").status_code == 403
    assert client.get("/test-rbac/admin-only").status_code == 403

    # 4. Log in as Admin
    client.post(
        "/api/auth/login",
        json={"email": "admin@aicte.gov.in", "password": "AdminSuperPass123!"},
    )
    assert client.get("/test-rbac/admin-only").status_code == 200


def test_cookie_and_security_configuration(app):
    """Test cookie security settings (HttpOnly, SameSite, and ProductionConfig guards)."""
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_NAME"] == "aicte_session"
    assert app.config["SESSION_COOKIE_SAMESITE"] in ("Lax", "Strict", "None")

    # In testing/dev, secure cookies are False so HTTP works
    assert app.config["SESSION_COOKIE_SECURE"] is False

    # ProductionConfig enforces Secure cookies and secret validation
    assert ProductionConfig.SESSION_COOKIE_SECURE is True

    # Validate production checks
    with pytest.raises(ValueError, match="DATABASE_URL"):
        ProductionConfig.validate()


def test_create_admin_cli(app, runner):
    """Test create-admin CLI command creates initial admin and prevents duplicate accounts."""
    # First creation
    res1 = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "cli_admin@aicte.gov.in",
            "--name",
            "CLI Administrator",
            "--password",
            "SecureAdminP@ss1",
        ]
    )
    assert "Successfully provisioned administrator account" in res1.output

    # Verify user in database
    with app.app_context():
        user = User.query.filter_by(email="cli_admin@aicte.gov.in").first()
        assert user is not None
        assert user.role == UserRole.ADMIN
        assert user.check_password("SecureAdminP@ss1") is True

    # Attempt duplicate creation with same email
    res2 = runner.invoke(
        args=[
            "create-admin",
            "--email",
            "cli_admin@aicte.gov.in",
            "--name",
            "Duplicate Admin",
            "--password",
            "AnotherPass1234!",
        ]
    )
    assert "already exists" in res2.output
