from datetime import datetime, timezone
from sqlalchemy.orm import validates
from app.extensions import db
from app.models.enums import NotificationType


class Notification(db.Model):
    """User notifications regarding FDR verification, renewals, and system alerts."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.String(50),
        nullable=False,
        default=NotificationType.INFO.value,
        index=True,
    )
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    user = db.relationship("User", back_populates="notifications")

    @validates("notification_type")
    def validate_type(self, key, notif_type):
        valid_types = NotificationType.values()
        val = (
            notif_type.value
            if isinstance(notif_type, NotificationType)
            else str(notif_type)
        )
        if val not in valid_types:
            raise ValueError(
                f"Invalid notification type '{val}'. Valid options: {valid_types}"
            )
        return val

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} title='{self.title[:30]}' read={self.is_read}>"
