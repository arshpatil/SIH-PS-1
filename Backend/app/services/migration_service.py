import json
import logging
from sqlalchemy import inspect
from flask import Flask

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import ScrutinyStatus
from app.models.fdr import FDRRecord
from app.models.workflow_history import FDRWorkflowHistory

logger = logging.getLogger(__name__)


def run_workflow_history_migration(app: Flask | None = None, backfill: bool = True) -> dict:
    """
    Safely create the fdr_workflow_history table and indexes without modifying
    existing tables, and optionally backfill historical scrutiny audit logs.

    Safety:
    - Safe to rerun (idempotent): never duplicates records or drops tables.
    - Preserves all existing FDR records and AuditLog entries.
    - Backfills only transitions with reliable status information.
    """
    engine = db.engine
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    table_already_existed = "fdr_workflow_history" in existing_tables

    # 1. Safely create table and indexes if not present
    db.metadata.tables["fdr_workflow_history"].create(engine, checkfirst=True)

    backfilled_count = 0
    skipped_count = 0

    # 2. Backfill historical scrutiny transitions from AuditLog if requested
    if backfill:
        # Find all audit logs matching scrutiny transitions
        audit_logs = (
            AuditLog.query.filter(
                AuditLog.entity_type == "FDRRecord",
                AuditLog.action.like("SCRUTINY_TRANSITION_%"),
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
            .all()
        )

        for log in audit_logs:
            if not log.entity_id:
                skipped_count += 1
                continue

            # Verify target FDR still exists
            fdr_exists = db.session.get(FDRRecord, log.entity_id)
            if not fdr_exists:
                skipped_count += 1
                continue

            # Check if this exact audit event was already backfilled
            already_backfilled = FDRWorkflowHistory.query.filter_by(
                fdr_id=log.entity_id,
                created_at=log.created_at,
            ).first()
            if already_backfilled:
                skipped_count += 1
                continue

            # Parse JSON details if available
            parsed = {}
            if log.details:
                try:
                    parsed = json.loads(log.details)
                except (json.JSONDecodeError, TypeError):
                    parsed = {}

            from_status = parsed.get("previous_status")
            to_status = parsed.get("new_status")
            remarks = parsed.get("remarks")

            # Fallback to parsing action name if JSON was missing or incomplete
            # e.g., SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED
            if not from_status or not to_status:
                parts = log.action.replace("SCRUTINY_TRANSITION_", "").split("_TO_")
                if len(parts) == 2:
                    from_status = from_status or parts[0]
                    to_status = to_status or parts[1]

            if not from_status or not to_status:
                logger.warning(
                    f"AuditLog {log.id} lacks reliable status information; skipping backfill."
                )
                skipped_count += 1
                continue

            # Determine deficiency flag
            is_deficiency = to_status == ScrutinyStatus.RETURNED.value
            resolution_status = "UNRESOLVED" if is_deficiency else None

            history = FDRWorkflowHistory(
                fdr_id=log.entity_id,
                from_status=from_status,
                to_status=to_status,
                actor_id=log.user_id or parsed.get("actor_id"),
                remarks=remarks,
                is_deficiency=is_deficiency,
                resolution_status=resolution_status,
                created_at=log.created_at,
            )
            db.session.add(history)
            backfilled_count += 1

        if backfilled_count > 0:
            db.session.commit()

    action_summary = "already existed" if table_already_existed else "created successfully"
    msg = (
        f"Migration completed: 'fdr_workflow_history' table {action_summary}. "
        f"Backfilled {backfilled_count} historical transition(s), skipped {skipped_count}."
    )
    return {
        "success": True,
        "table_already_existed": table_already_existed,
        "backfilled_count": backfilled_count,
        "skipped_count": skipped_count,
        "message": msg,
    }


def ensure_schema_updates(engine=None) -> list[str]:
    """
    Safely verify and apply incremental schema updates (such as new columns and tables)
    to existing databases without dropping or altering existing data.
    """
    if engine is None:
        engine = db.engine
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    created = []

    from app.models.renewal_history import FDRRenewalHistory
    from app.models.bank_verification import BankVerificationLog
    from app.models.email_log import EmailNotificationLog

    # Safely create fdr_renewal_history table if absent
    if "fdr_renewal_history" not in existing_tables:
        FDRRenewalHistory.__table__.create(engine, checkfirst=True)
        created.append("fdr_renewal_history")
        logger.info("Migrated schema: created fdr_renewal_history table")

    # Safely create bank_verification_logs table if absent
    if "bank_verification_logs" not in existing_tables:
        BankVerificationLog.__table__.create(engine, checkfirst=True)
        created.append("bank_verification_logs")
        logger.info("Migrated schema: created bank_verification_logs table")

    # Safely create email_notification_logs table if absent
    if "email_notification_logs" not in existing_tables:
        EmailNotificationLog.__table__.create(engine, checkfirst=True)
        created.append("email_notification_logs")
        logger.info("Migrated schema: created email_notification_logs table")

    if "fdr_requests" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("fdr_requests")]
        new_cols = [
            ("assigned_to", "INTEGER"),
            ("renewal_fdr_number", "VARCHAR(100)"),
            ("renewal_issue_date", "DATE"),
            ("renewal_maturity_date", "DATE"),
            ("renewal_amount", "NUMERIC(15, 2)"),
            ("renewal_document", "VARCHAR(255)"),
            ("renewal_document_size", "INTEGER"),
            ("renewal_remarks", "TEXT"),
            ("renewal_submitted_at", "TIMESTAMP"),
            ("renewal_verified_at", "TIMESTAMP"),
            ("renewal_verified_by", "INTEGER"),
            ("renewal_is_synthetic", "BOOLEAN DEFAULT 0"),
            ("renewal_ocr_data", "TEXT"),
        ]
        with engine.connect() as conn:
            for col_name, col_type in new_cols:
                if col_name not in columns:
                    conn.execute(db.text(f"ALTER TABLE fdr_requests ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Migrated fdr_requests table: added column {col_name}")
            conn.commit()

    return created
