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


def init_scheduler(app: Flask) -> BackgroundScheduler | None:
    """
    Safely initialize and start the APScheduler background scanner.

    Safety controls:
    - Disabled when SCHEDULER_ENABLED is False (default in dev/test).
    - Disabled when TESTING is True.
    - Under Werkzeug dev reloader, only starts in the child execution process (WERKZEUG_RUN_MAIN == 'true').
    - Avoids duplicate instances if already initialized.
    """
    global _scheduler

    if not app.config.get("SCHEDULER_ENABLED", False):
        return None

    if app.config.get("TESTING", False):
        return None

    # In development mode with Werkzeug reloader, run only in the active worker process
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    try:
        scheduler = BackgroundScheduler(daemon=True)

        def _job_wrapper():
            with app.app_context():
                try:
                    from app.services.maturity_service import (
                        scan_and_update_maturities,
                    )

                    scan_and_update_maturities()
                except Exception as exc:
                    app.logger.error(
                        f"Error during scheduled FDR maturity scan: {exc}"
                    )

        scheduler.add_job(
            func=_job_wrapper,
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
