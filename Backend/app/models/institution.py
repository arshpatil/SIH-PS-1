from datetime import datetime, timezone
from app.extensions import db


class Institution(db.Model):
    """Educational or technical institution affiliated with AICTE."""

    __tablename__ = "institutions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institution_code = db.Column(
        db.String(64), unique=True, nullable=False, index=True
    )
    name = db.Column(db.String(255), nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)
    contact_email = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(32), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    users = db.relationship(
        "User",
        back_populates="institution",
        cascade="all, delete-orphan",
    )
    fdrs = db.relationship(
        "FDRRecord",
        back_populates="institution",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "institution_code": self.institution_code,
            "name": self.name,
            "address": self.address,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Institution id={self.id} code='{self.institution_code}' name='{self.name}'>"
