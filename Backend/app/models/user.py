from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models.enums import UserRole


class User(db.Model):
    """User entity representing institution staff, AICTE verification officers, or administrators."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(50),
        nullable=False,
        default=UserRole.INSTITUTION_USER.value,
        index=True,
    )
    institution_id = db.Column(
        db.Integer,
        db.ForeignKey("institutions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    institution = db.relationship("Institution", back_populates="users")
    created_fdrs = db.relationship(
        "FDRRecord",
        foreign_keys="FDRRecord.created_by",
        back_populates="creator",
        lazy="dynamic",
    )
    uploaded_documents = db.relationship(
        "Document",
        foreign_keys="Document.uploaded_by",
        back_populates="uploader",
        lazy="dynamic",
    )
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")
    notifications = db.relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @validates("email")
    def validate_email(self, key, address):
        if not address or "@" not in address:
            raise ValueError("Invalid email address format.")
        return address.strip().lower()

    @validates("role")
    def validate_role(self, key, role_value):
        valid_roles = UserRole.values()
        val = role_value.value if isinstance(role_value, UserRole) else str(role_value)
        if val not in valid_roles:
            raise ValueError(f"Invalid user role '{val}'. Valid roles: {valid_roles}")
        return val

    def set_password(self, password: str) -> None:
        """Set user password with werkzeug secure hash."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify user password securely using Werkzeug."""
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def to_safe_dict(self) -> dict:
        """Return safe profile dictionary without exposing sensitive attributes."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "role_category": UserRole.normalize_category(self.role),
            "institution_id": self.institution_id,
            "institution_name": self.institution.name if self.institution else None,
            "institution_code": self.institution.institution_code if self.institution else None,
            "institution_address": self.institution.address if self.institution else None,
            "institution_contact_phone": self.institution.contact_phone if self.institution else None,
            "institution_contact_email": self.institution.contact_email if self.institution else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "institution_id": self.institution_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"
