from enum import Enum


class ScrutinyStatus(str, Enum):
    """FDR scrutiny workflow status values."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    RETURNED = "RETURNED"
    REJECTED = "REJECTED"

    @classmethod
    def values(cls) -> set[str]:
        return {item.value for item in cls}


class ValidityStatus(str, Enum):
    """FDR validity and maturity status values."""
    ACTIVE = "ACTIVE"
    EXPIRING_SOON = "EXPIRING_SOON"
    MATURED = "MATURED"
    OVERDUE_ACTION = "OVERDUE_ACTION"

    @classmethod
    def values(cls) -> set[str]:
        return {item.value for item in cls}


class DocumentProcessingStatus(str, Enum):
    """Document OCR and processing status values."""
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"

    @classmethod
    def values(cls) -> set[str]:
        return {item.value for item in cls}


class UserRole(str, Enum):
    """Role-based access control roles."""
    INSTITUTION = "INSTITUTION"
    INSTITUTION_USER = "INSTITUTION_USER"  # Backward-compatible alias
    AICTE_OFFICER = "AICTE_OFFICER"
    ADMIN = "ADMIN"
    AICTE_ADMIN = "AICTE_ADMIN"            # Backward-compatible alias
    SYSTEM_ADMIN = "SYSTEM_ADMIN"          # Backward-compatible alias

    @classmethod
    def values(cls) -> set[str]:
        return {item.value for item in cls}

    @classmethod
    def normalize_category(cls, role_value: "UserRole | str") -> str:
        """Map role values into canonical role categories: INSTITUTION, AICTE_OFFICER, ADMIN."""
        val = role_value.value if isinstance(role_value, cls) else str(role_value).upper()
        if val in (cls.INSTITUTION.value, cls.INSTITUTION_USER.value):
            return "INSTITUTION"
        if val in (cls.ADMIN.value, cls.AICTE_ADMIN.value, cls.SYSTEM_ADMIN.value):
            return "ADMIN"
        if val == cls.AICTE_OFFICER.value:
            return "AICTE_OFFICER"
        return val


class NotificationType(str, Enum):
    """Notification classification categories."""
    INFO = "INFO"
    WARNING = "WARNING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ALERT = "ALERT"

    @classmethod
    def values(cls) -> set[str]:
        return {item.value for item in cls}
