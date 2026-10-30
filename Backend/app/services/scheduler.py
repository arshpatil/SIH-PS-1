import atexit
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the currently running scheduler instance if any."""
    global _scheduler
    return _scheduler


def run_scheduled_maturity_scan(app: Flask) -> dict:
    """
    Execute the automated FDR maturity and receipt reminder scan job.
    Catches exceptions safely and logs errors so the recurring schedule never stops.
    """
    with app.app_context():
        try:
            from app.services.maturity_service import scan_and_update_maturities
            from app.services.email_service import scan_and_send_receipt_reminders

            mat_res = scan_and_update_maturities()
            receipt_emails = scan_and_send_receipt_reminders()
            logger.info(
                "Scheduled scan completed: %d FDR(s) scanned, %d status(es) updated, "
                "%d maturity email(s), %d receipt reminder(s).",
                mat_res.get("scanned_count", 0),
                mat_res.get("updated_count", 0),
                mat_res.get("emails_sent_count", 0),
                receipt_emails,
            )
            return {
                "success": True,
                "maturity_result": mat_res,
                "receipt_emails": receipt_emails,
            }
        except Exception as exc:
            logger.error(
                "Error during scheduled FDR maturity and email reminder scan: %s",
                exc,
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(exc),
            }


def init_scheduler(app: Flask) -> BackgroundScheduler | None:
    """
    Safely initialize and start the APScheduler background scanner.

    Safety controls:
    - Disabled when SCHEDULER_ENABLED is False (e.g. in test environment).
    - Disabled when TESTING is True.
    - Under Flask CLI reloader (FLASK_RUN_FROM_CLI == 'true'), starts only in child worker (WERKZEUG_RUN_MAIN == 'true').
    - Under run.py debug reloader, the parent process shuts down the scheduler before starting the reloader loop.
    - Avoids duplicate instances if already initialized.
    """
    global _scheduler

    if not app.config.get("SCHEDULER_ENABLED", True):
        return None

    if app.config.get("TESTING", False):
        return None

    # In Flask CLI reloader mode (flask run), run only in the active child worker process
    if os.environ.get("FLASK_RUN_FROM_CLI") == "true" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    try:
        scheduler = BackgroundScheduler(daemon=True)

        scheduler.add_job(
            func=lambda: run_scheduled_maturity_scan(app),
            trigger="cron",
            hour=0,
            minute=0,
            id="fdr_maturity_scanner",
            name="Daily FDR Maturity and Notification Scanner",
            replace_existing=True,
        )

        scheduler.start()
        _scheduler = scheduler

        # Ensure scheduler shuts down when process exits
        atexit.register(lambda: shutdown_scheduler())
        app.logger.info("APScheduler FDR maturity background scanner started.")
        return scheduler

    except Exception as exc:
        app.logger.error(f"Failed to initialize background scheduler: {exc}")
        return None


def shutdown_scheduler() -> None:
    """Safely shut down the background scheduler if running."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
