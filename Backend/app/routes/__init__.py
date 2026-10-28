from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.fdr import fdr_bp
from app.routes.health import health_bp
from app.routes.notifications import notifications_bp
from app.routes.reports import reports_bp

__all__ = [
    "health_bp",
    "auth_bp",
    "fdr_bp",
    "notifications_bp",
    "dashboard_bp",
    "reports_bp",
]

