from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.route("/health", methods=["GET"])
def check_health():
    """Health check endpoint returning application status, metadata and database connectivity."""
    db_status = "connected"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unreachable ({type(exc).__name__})"

    payload = {
        "status": "healthy",
        "app_name": current_app.config.get(
            "APP_NAME", "AICTE Security Deposit / FDR Management Portal"
        ),
        "version": current_app.config.get("API_VERSION", "1.0.0"),
        "database": db_status,
    }
    return jsonify(payload), 200
