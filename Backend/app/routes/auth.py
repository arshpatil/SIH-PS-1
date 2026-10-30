from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.institution import Institution
from app.models.user import User
import re
import uuid
from app.security import (
    destroy_session,
    establish_session,
    generate_csrf_token,
    login_required,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/csrf-token", methods=["GET"])
def get_csrf_token():
    """Return a CSRF synchronizer token for the current session."""
    token = generate_csrf_token()
    return jsonify({"csrf_token": token}), 200


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate user with email and password, regenerating session to prevent fixation."""
    if not request.is_json:
        return (
            jsonify(
                {
                    "error": "Request body must be valid JSON.",
                    "code": "INVALID_JSON",
                }
            ),
            400,
        )

    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return (
            jsonify(
                {
                    "error": "Email and password are both required.",
                    "code": "MISSING_CREDENTIALS",
                }
            ),
            400,
        )

    # Normalize email
    clean_email = str(email).strip().lower()
    user = User.query.filter_by(email=clean_email).first()

    # Reject invalid credentials with a generic message to prevent user enumeration
    if not user or not user.check_password(str(password)):
        return (
            jsonify(
                {
                    "error": "Invalid email or password.",
                    "code": "INVALID_CREDENTIALS",
                }
            ),
            401,
        )

    # Reject inactive accounts
    if not user.is_active:
        return (
            jsonify(
                {
                    "error": "Your account has been deactivated. Please contact an administrator.",
                    "code": "ACCOUNT_INACTIVE",
                }
            ),
            403,
        )

    # Institution users must have an associated institution
    if UserRole.normalize_category(user.role) == "INSTITUTION":
        if user.institution_id is None or user.institution is None:
            return (
                jsonify(
                    {
                        "error": "Institution account is not linked to any valid registered institution.",
                        "code": "UNLINKED_INSTITUTION",
                    }
                ),
                403,
            )

    # Regenerate session and create fresh CSRF token
    csrf_token = establish_session(user)

    # Record audit log for login
    try:
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="User",
            entity_id=user.id,
            details=f"User {user.email} authenticated successfully.",
        )
        db.session.add(audit)
        db.session.commit()
    except Exception:
        db.session.rollback()

    response = jsonify(
        {
            "message": "Login successful.",
            "user": user.to_safe_dict(),
            "csrf_token": csrf_token,
        }
    )
    # Also attach non-HttpOnly csrf cookie for frontend convenience
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=False,
        samesite="Lax",
        secure=False,
    )
    return response, 200


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Securely clear the authenticated user session and invalidate state."""
    user = g.current_user
    try:
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGOUT",
            entity_type="User",
            entity_id=user.id,
            details=f"User {user.email} logged out.",
        )
        db.session.add(audit)
        db.session.commit()
    except Exception:
        db.session.rollback()

    destroy_session()
    response = jsonify({"message": "Logged out successfully."})
    response.delete_cookie("csrf_token")
    return response, 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_user():
    """Return the authenticated user's safe profile and current CSRF token."""
    return (
        jsonify(
            {
                "user": g.current_user.to_safe_dict(),
                "csrf_token": generate_csrf_token(),
            }
        ),
        200,
    )


@auth_bp.route("/profile", methods=["PATCH"])
@login_required
def update_profile():
    """Update authorized profile fields for the authenticated user."""
    if not request.is_json:
        return jsonify({"error": "Request body must be valid JSON.", "code": "INVALID_JSON"}), 400

    data = request.get_json(silent=True) or {}
    user = g.current_user
    changes_made = []

    # Update full name if provided
    new_name = data.get("full_name") or data.get("adminName")
    if new_name and isinstance(new_name, str):
        clean_name = new_name.strip()
        if len(clean_name) >= 2 and clean_name != user.full_name:
            user.full_name = clean_name
            changes_made.append("full_name")

    # Update institution details if user belongs to an institution
    if user.institution:
        new_address = data.get("address")
        if new_address and isinstance(new_address, str):
            clean_addr = new_address.strip()
            if clean_addr and clean_addr != user.institution.address:
                user.institution.address = clean_addr
                changes_made.append("institution_address")

        new_phone = data.get("contact_phone") or data.get("contactNumber")
        if new_phone and isinstance(new_phone, str):
            clean_phone = new_phone.strip()
            if clean_phone and clean_phone != user.institution.contact_phone:
                user.institution.contact_phone = clean_phone
                changes_made.append("institution_contact_phone")

        new_email = data.get("alternate_email") or data.get("alternateEmail")
        if new_email and isinstance(new_email, str):
            clean_email = new_email.strip()
            if clean_email and "@" in clean_email:
                user.institution.contact_email = clean_email
                changes_made.append("institution_contact_email")

    if changes_made:
        try:
            audit = AuditLog(
                user_id=user.id,
                action="PROFILE_UPDATED",
                entity_type="User",
                entity_id=user.id,
                details=f"User updated profile fields: {', '.join(changes_made)}",
            )
            db.session.add(audit)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Failed to update profile.", "code": "DB_ERROR"}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Profile updated successfully.",
                "user": user.to_safe_dict(),
            }
        ),
        200,
    )



@auth_bp.route("/register", methods=["POST"])
def register():
    """Public registration endpoint for new educational institutions.

    Creates an Institution record and associated primary institution user account.
    Public registration strictly assigns the INSTITUTION role. Privileged roles (ADMIN,
    AICTE_OFFICER) are strictly rejected or ignored.
    """
    if not request.is_json:
        return (
            jsonify({"success": False, "error": "Request body must be valid JSON.", "code": "INVALID_JSON"}),
            400,
        )

    data = request.get_json(silent=True) or {}

    # 1. Reject explicit attempt to claim privileged roles
    claimed_role = str(data.get("role", "")).strip().upper()
    if claimed_role in (UserRole.ADMIN.value, UserRole.AICTE_OFFICER.value, "AICTE_ADMIN", "SYSTEM_ADMIN"):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Privileged roles (Admin, AICTE Officer) cannot be registered publicly.",
                    "code": "FORBIDDEN_ROLE",
                }
            ),
            403,
        )

    # 2. Extract and validate required fields
    inst_name = str(data.get("name") or data.get("institution_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    contact_person = str(data.get("contact_person") or data.get("full_name") or data.get("principal_name", "")).strip()
    contact_phone = str(data.get("contact_phone") or data.get("phone", "")).strip()
    address = str(data.get("address", "")).strip()
    inst_code = str(data.get("institution_code") or data.get("aicte_id", "")).strip()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password") or data.get("confirmPassword", ""))

    errors = {}
    if not inst_name or len(inst_name) < 2:
        errors["name"] = "Institution name is required (minimum 2 characters)."
    elif len(inst_name) > 255:
        errors["name"] = "Institution name cannot exceed 255 characters."

    if not email:
        errors["email"] = "Official institution email is required."
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors["email"] = "Please provide a valid email address format."

    if not contact_person or len(contact_person) < 2:
        errors["contact_person"] = "Contact person / principal name is required (minimum 2 characters)."
    elif len(contact_person) > 150:
        errors["contact_person"] = "Contact person name cannot exceed 150 characters."

    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters long."
    elif not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        errors["password"] = "Password must contain both letters and at least one number."

    if confirm_password and password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    if errors:
        return (
            jsonify({"success": False, "error": "Validation failed for one or more fields.", "code": "VALIDATION_ERROR", "details": errors}),
            400,
        )

    # 3. Check for existing duplicate user email
    if User.query.filter_by(email=email).first():
        return (
            jsonify({"success": False, "error": f"An account with email '{email}' already exists.", "code": "EMAIL_ALREADY_EXISTS"}),
            409,
        )

    # 4. Generate or validate institution code
    if inst_code:
        clean_code = inst_code.upper()
        if Institution.query.filter_by(institution_code=clean_code).first():
            return (
                jsonify({"success": False, "error": f"An institution with code '{clean_code}' already exists.", "code": "INSTITUTION_CODE_EXISTS"}),
                409,
            )
    else:
        # Auto-generate unique AICTE registration code
        clean_code = f"AICTE-REG-{uuid.uuid4().hex[:8].upper()}"
        while Institution.query.filter_by(institution_code=clean_code).first():
            clean_code = f"AICTE-REG-{uuid.uuid4().hex[:8].upper()}"

    # 5. Transactional record creation
    try:
        new_inst = Institution(
            institution_code=clean_code,
            name=inst_name,
            address=address if address else None,
            contact_email=email,
            contact_phone=contact_phone if contact_phone else None,
        )
        db.session.add(new_inst)
        db.session.flush()

        new_user = User(
            full_name=contact_person,
            email=email,
            role=UserRole.INSTITUTION_USER.value,
            institution_id=new_inst.id,
            is_active=True,
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()

        # Audit log registration
        audit = AuditLog(
            user_id=new_user.id,
            action="INSTITUTION_REGISTERED",
            entity_type="Institution",
            entity_id=new_inst.id,
            details=f"Public registration: Institution '{new_inst.name}' (Code: {new_inst.institution_code}) registered by {new_user.email}.",
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return (
            jsonify({"success": False, "error": f"Failed to register institution: {str(ex)}", "code": "REGISTRATION_FAILED"}),
            500,
        )

    return (
        jsonify(
            {
                "success": True,
                "message": "Institution registered successfully. You may now log in with your credentials.",
                "institution": new_inst.to_dict(),
                "user": new_user.to_safe_dict(),
            }
        ),
        201,
    )
