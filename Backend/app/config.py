from datetime import timedelta
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base application configuration."""

    APP_NAME = os.getenv("APP_NAME", "AICTE Security Deposit / FDR Management Portal")
    API_VERSION = os.getenv("API_VERSION", "1.0.0")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-aicte-portal-secret-key-change-in-prod")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False
    DEBUG = False

    # Session & Cookie Security
    SESSION_COOKIE_NAME = "aicte_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = (
        os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1", "t")
    )
    PERMANENT_SESSION_LIFETIME = timedelta(
        days=int(os.getenv("SESSION_LIFETIME_DAYS", 7))
    )

    # CORS configuration for React/Vite frontend development
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]

    # Document Upload & OCR Configuration
    UPLOAD_FOLDER = Path(
        os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads" / "fdr_documents"))
    )
    REQUEST_UPLOAD_FOLDER = Path(
        os.getenv("REQUEST_UPLOAD_FOLDER", str(BASE_DIR / "uploads" / "request_documents"))
    )
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024))  # 10 MB
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", 20))
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")

    # Maturity Tracking & Notification Configuration
    EXPIRING_SOON_DAYS = int(os.getenv("EXPIRING_SOON_DAYS", 30))
    OVERDUE_ACTION_DAYS = int(os.getenv("OVERDUE_ACTION_DAYS", 30))
    REMINDER_INTERVAL_DAYS = [
        int(x.strip())
        for x in os.getenv("REMINDER_INTERVAL_DAYS", "30,15,7,0").split(",")
        if x.strip()
    ]
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "False").lower() in (
        "true",
        "1",
        "t",
    )
    BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "UTC")


class DevelopmentConfig(Config):
    """Development environment configuration."""

    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'aicte_fdr.db'}",
    )


class TestingConfig(Config):
    """Testing environment configuration."""

    TESTING = True
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    UPLOAD_FOLDER = BASE_DIR / "instance" / "test_uploads"
    REQUEST_UPLOAD_FOLDER = BASE_DIR / "instance" / "test_uploads" / "requests"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "sqlite:///:memory:",
    )


class ProductionConfig(Config):
    """Production environment configuration."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    @classmethod
    def validate(cls):
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise ValueError(
                "DATABASE_URL environment variable must be set in production mode."
            )
        if cls.SECRET_KEY == "dev-aicte-portal-secret-key-change-in-prod":
            raise ValueError("A secure SECRET_KEY must be provided in production mode.")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
