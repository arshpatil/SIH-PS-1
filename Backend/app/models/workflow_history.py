from datetime import datetime, timezone
from typing import Any
from app.extensions import db


class FDRWorkflowHistory(db.Model):
    """
    Immutable structured history of FDR scrutiny status transitions, officer decisions,
    and deficiency notices.
    """

    __tablename__ = "fdr_workflow_history"
    __table_args__ = (
        db.Index("idx_wf_history_fdr_id", "fdr_id"),
        db.Index("idx_wf_history_created_at", "created_at"),
        db.Index("idx_wf_history_is_deficiency", "is_deficiency"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fdr_id = db.Column(
        db.Integer,
        db.ForeignKey("fdr_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status = db.Column(db.String(32), nullable=False)
    to_status = db.Column(db.String(32), nullable=False)
    actor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    remarks = db.Column(db.Text, nullable=True)

    # Deficiency tracking fields
    is_deficiency = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    resolution_status = db.Column(
        db.String(32),
        nullable=True,
        default=None,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    fdr = db.relationship("FDRRecord", back_populates="workflow_history")
    actor = db.relationship("User", foreign_keys=[actor_id])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def to_dict(self, include_actor_email: bool = False) -> dict:
        """Serialize workflow history entry to dictionary, respecting privacy boundaries."""
        actor_name = None
        actor_role = None
        actor_email = None

        if self.actor:
            actor_name = self.actor.full_name
            actor_role = self.actor.role
            if include_actor_email:
                actor_email = self.actor.email

        iso_timestamp = self.created_at.isoformat() if self.created_at else None

        return {
            "id": self.id,
            "fdr_id": self.fdr_id,
            "action": f"SCRUTINY_TRANSITION_{self.from_status}_TO_{self.to_status}",
            "from_status": self.from_status,
            "previous_status": self.from_status,
            "to_status": self.to_status,
            "new_status": self.to_status,
            "actor_id": self.actor_id,
            "actor_name": actor_name,
            "actor_role": actor_role,
            "actor_email": actor_email,
            "remarks": self.remarks,
            "is_deficiency": self.is_deficiency,
            "resolution_status": self.resolution_status,
            "created_at": iso_timestamp,
            "timestamp": iso_timestamp,
        }

    def __repr__(self) -> str:
        return (
            f"<FDRWorkflowHistory id={self.id} fdr_id={self.fdr_id} "
            f"'{self.from_status}'->'{self.to_status}' deficiency={self.is_deficiency}>"
        )
