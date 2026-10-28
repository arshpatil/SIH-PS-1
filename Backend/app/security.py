from functools import wraps
import hmac
import secrets
from flask import current_app, g, jsonify, request, session

from app.extensions import db
from app.models.enums import UserRole
from app.models.user import User


def generate_csrf_token() -> str:
    """Generate or retrieve the session-bound CSRF synchronizer token."""
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["_csrf_token"] = token
    return token


def verify_csrf_token() -> bool:
    """Verify that the submitted CSRF token matches the session-bound token."""
    # Allow tests to opt out if explicitly configured, but enabled by default
    if not current_app.config.get("CSRF_ENABLED", True):
        return True

    expected = session.get("_csrf_token")
    if not expected:
        return False

    # Extract token from header or JSON payload
    submitted = request.headers.get("X-CSRF-Token") or request.headers.get(
        "X-CSRFToken"
    )
    if not submitted and request.is_json:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            submitted = payload.get("csrf_token")

    if not submitted:
        return False

    return hmac.compare_digest(str(submitted), str(expected))


def establish_session(user: User) -> str:
    """Regenerate session state after successful login to prevent session fixation attacks."""
    session.clear()
    session["user_id"] = user.id
    session["role"] = user.role
    csrf_token = secrets.token_hex(32)
    session["_csrf_token"] = csrf_token
    session.permanent = True
    return csrf_token


def destroy_session() -> None:
    """Securely invalidate and clear current session state."""
    session.clear()


def login_required(f):
    """Decorator requiring an active authenticated user session."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return (
                jsonify(
                    {
                        "error": "Authentication required. Please log in.",
                        "code": "UNAUTHENTICATED",
                    }
                ),
                401,
            )

        user = db.session.get(User, user_id)
        if not user or not user.is_active:
            destroy_session()
            return (
                jsonify(
                    {
                        "error": "User account is invalid or deactivated.",
                        "code": "INACTIVE_USER",
                    }
                ),
                401,
            )

        # Enforce CSRF protection on authenticated state-changing requests
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not verify_csrf_token():
                return (
                    jsonify(
                        {
                            "error": "CSRF validation failed: token is missing or invalid.",
                            "code": "CSRF_ERROR",
                        }
                    ),
                    403,
                )

        g.current_user = user
        return f(*args, **kwargs)

    return decorated_function


def roles_required(*allowed_roles):
    """Decorator requiring the authenticated user to hold one of the permitted roles/categories."""

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = g.current_user

            # Normalize permitted roles/categories
            allowed_categories = {
                UserRole.normalize_category(r) for r in allowed_roles
            }
            allowed_exact = {
                r.value if isinstance(r, UserRole) else str(r).upper()
                for r in allowed_roles
            }

            user_category = UserRole.normalize_category(user.role)

            if (
                user.role not in allowed_exact
                and user_category not in allowed_categories
            ):
                return (
                    jsonify(
                        {
                            "error": "Forbidden: You do not have permission to access this resource.",
                            "code": "FORBIDDEN",
                        }
                    ),
                    403,
                )

            # Institution users must have an associated institution
            if user_category == "INSTITUTION":
                if user.institution_id is None or user.institution is None:
                    return (
                        jsonify(
                            {
                                "error": "Access denied: Institution user is not affiliated with any valid institution.",
                                "code": "INSTITUTION_REQUIRED",
                            }
                        ),
                        403,
                    )

            return f(*args, **kwargs)

        return decorated_function

    return decorator
