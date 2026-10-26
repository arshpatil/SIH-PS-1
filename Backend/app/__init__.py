import os
from pathlib import Path
import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.config import config_by_name
from app.extensions import cors, db
from app.routes.auth import auth_bp
from app.routes.fdr import fdr_bp
from app.routes.health import health_bp


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce foreign key constraints when using SQLite."""
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db(app: Flask | None = None) -> None:
    """Safely initialize database tables without overwriting or dropping existing data."""
    from app import models as _models  # noqa: F401 Ensure all models are registered with db.metadata

    ctx_needed = app is not None
    ctx = app.app_context() if ctx_needed else None
    if ctx:
        ctx.push()

    try:
        env = os.getenv("FLASK_ENV", "development").lower()
        if env == "production":
            raise RuntimeError(
                "Automatic db initialization is disabled in production. Use migration scripts."
            )
        db.create_all()
    finally:
        if ctx:
            ctx.pop()


def create_app(config_name: str | None = None) -> Flask:
    """Application factory for AICTE Security Deposit / FDR Management Portal."""
    # Load environment variables from .env if present
    load_dotenv()

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()

    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # Ensure instance and upload directories exist
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        upload_dir = app.config.get("UPLOAD_FOLDER")
        if upload_dir:
            os.makedirs(upload_dir, exist_ok=True)
        req_upload_dir = app.config.get("REQUEST_UPLOAD_FOLDER")
        if req_upload_dir:
            os.makedirs(req_upload_dir, exist_ok=True)
    except OSError:
        pass

    # Initialize database extension
    db.init_app(app)

    # Initialize CORS with explicit origins and credentials enabled
    allowed_origins = app.config.get("CORS_ALLOWED_ORIGINS", ["http://localhost:3000"])
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "X-CSRF-Token", "X-CSRFToken", "Accept", "Authorization"],
        expose_headers=["Content-Disposition"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    # Import models so SQLAlchemy metadata is aware of all tables
    from app import models as _models  # noqa: F401

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(fdr_bp)
    from app.routes.notifications import notifications_bp
    app.register_blueprint(notifications_bp)
    from app.routes.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    from app.routes.reports import reports_bp
    app.register_blueprint(reports_bp)
    from app.routes.requests import requests_bp
    app.register_blueprint(requests_bp)

    # Safe CLI command to initialize database for development
    @app.cli.command("init-db")
    def init_db_cli():
        """Create database tables safely if they do not exist."""
        env = os.getenv("FLASK_ENV", "development").lower()
        if env == "production":
            click.echo(
                "Automatic table creation is disabled in production. Use migrations."
            )
            return

        db.create_all()
        click.echo("Initialized database tables successfully.")

    # Safe CLI command to provision initial administrator
    @app.cli.command("create-admin")
    @click.option(
        "--email", prompt="Admin Email", help="Administrator email address"
    )
    @click.option(
        "--name",
        prompt="Full Name",
        default="System Administrator",
        help="Administrator full name",
    )
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Administrator password",
    )
    def create_admin_cli(email, name, password):
        """Interactively provision an initial administrator account safely."""
        from app.models.enums import UserRole
        from app.models.user import User

        clean_email = str(email).strip().lower()
        if not clean_email or "@" not in clean_email or "." not in clean_email:
            click.echo("Error: Invalid email address format.")
            return

        if not password or len(password) < 8:
            click.echo("Error: Password must be at least 8 characters long.")
            return

        existing = User.query.filter_by(email=clean_email).first()
        if existing:
            click.echo(
                f"Error: An account with email '{clean_email}' already exists."
            )
            return

        admin = User(
            full_name=str(name).strip(),
            email=clean_email,
            role=UserRole.ADMIN,
            institution_id=None,
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(
            f"Successfully provisioned administrator account for '{clean_email}'."
        )

    # Safe CLI command to scan FDR maturities and generate notifications
    @app.cli.command("scan-fdr-maturities")
    @click.option(
        "--date",
        "as_of_date_str",
        default=None,
        help="Reference business date (YYYY-MM-DD). Defaults to current business date.",
    )
    def scan_fdr_maturities_cli(as_of_date_str):
        """Scan all FDR records, update validity status, and generate notifications."""
        from datetime import datetime
        from app.services.maturity_service import scan_and_update_maturities

        as_of = None
        if as_of_date_str:
            try:
                as_of = datetime.strptime(as_of_date_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                click.echo("Error: Invalid date format. Please use YYYY-MM-DD.")
                return

        result = scan_and_update_maturities(as_of_date=as_of)
        click.echo(
            f"Maturity scan completed for {result['as_of_date']}: "
            f"Scanned {result['scanned_count']} FDR(s), "
            f"Updated {result['updated_count']} status(es), "
            f"Generated {result['notifications_created']} notification(s)."
        )

    # Safe CLI command to migrate fdr_workflow_history and backfill audit records
    @app.cli.command("migrate-workflow-history")
    @click.option(
        "--backfill/--no-backfill",
        default=True,
        help="Whether to backfill existing SCRUTINY_TRANSITION audit logs into fdr_workflow_history.",
    )
    def migrate_workflow_history_cli(backfill):
        """Safely create fdr_workflow_history table and backfill historical scrutiny audit logs."""
        from app.services.migration_service import run_workflow_history_migration

        res = run_workflow_history_migration(app=app, backfill=backfill)
        click.echo(res["message"])

    # Safe CLI command to seed development data for interactive testing
    @app.cli.command("seed-dev-data")
    def seed_dev_data_cli():
        """Provision initial development institution, users across roles, and sample FDR records."""
        from datetime import date, timedelta
        from decimal import Decimal
        from app.models.enums import NotificationType, ScrutinyStatus, UserRole, ValidityStatus
        from app.models.fdr import FDRRecord
        from app.models.institution import Institution
        from app.models.notification import Notification
        from app.models.user import User
        from app.models.workflow_history import FDRWorkflowHistory

        # 1. Institution
        inst = Institution.query.filter_by(institution_code="AICTE-1-10928371").first()
        if not inst:
            inst = Institution(
                institution_code="AICTE-1-10928371",
                name="ABC Institute of Technology & Engineering",
                address="Knowledge Park III, Greater Noida, Uttar Pradesh - 201310",
                contact_email="principal@abcite.edu.in",
                contact_phone="+91-120-2328000",
            )
            db.session.add(inst)
            db.session.commit()
            click.echo(f"Created institution: {inst.name} ({inst.institution_code})")

        # 2. Users across roles
        inst_user = User.query.filter_by(email="principal@abcite.edu.in").first()
        if not inst_user:
            inst_user = User(
                full_name="Dr. K. S. Ramanathan",
                email="principal@abcite.edu.in",
                role=UserRole.INSTITUTION,
                institution_id=inst.id,
                is_active=True,
            )
            inst_user.set_password("InstitutionPass123!")
            db.session.add(inst_user)

        officer_user = User.query.filter_by(email="officer@aicte.gov.in").first()
        if not officer_user:
            officer_user = User(
                full_name="AICTE Scrutiny Officer Verma",
                email="officer@aicte.gov.in",
                role=UserRole.AICTE_OFFICER,
                institution_id=None,
                is_active=True,
            )
            officer_user.set_password("OfficerPass123!")
            db.session.add(officer_user)

        admin_user = User.query.filter_by(email="admin@aicte.gov.in").first()
        if not admin_user:
            admin_user = User(
                full_name="System Administrator",
                email="admin@aicte.gov.in",
                role=UserRole.ADMIN,
                institution_id=None,
                is_active=True,
            )
            admin_user.set_password("AdminPass123!")
            db.session.add(admin_user)

        db.session.commit()
        click.echo("Created or confirmed accounts: principal@abcite.edu.in, officer@aicte.gov.in, admin@aicte.gov.in")

        # 3. Seed FDR records if none exist
        if FDRRecord.query.filter_by(institution_id=inst.id).count() == 0:
            today = date.today()
            fdr1 = FDRRecord(
                institution_id=inst.id,
                fdr_number="FDR-SBI-2021-99821",
                bank_name="State Bank of India",
                branch_name="Greater Noida Institutional Branch (IFSC: SBIN0011472)",
                amount=Decimal("3500000.00"),
                issue_date=today - timedelta(days=365 * 3),
                maturity_date=today + timedelta(days=12),
                scrutiny_status=ScrutinyStatus.VERIFIED.value,
                validity_status=ValidityStatus.EXPIRING_SOON.value,
                created_by=inst_user.id,
            )
            fdr2 = FDRRecord(
                institution_id=inst.id,
                fdr_number="FDR-PNB-2022-44719",
                bank_name="Punjab National Bank",
                branch_name="Noida Sector 18 Branch (IFSC: PUNB0243100)",
                amount=Decimal("1500000.00"),
                issue_date=today - timedelta(days=365 * 2),
                maturity_date=today + timedelta(days=22),
                scrutiny_status=ScrutinyStatus.SUBMITTED.value,
                validity_status=ValidityStatus.ACTIVE.value,
                created_by=inst_user.id,
            )
            fdr3 = FDRRecord(
                institution_id=inst.id,
                fdr_number="FDR-BOB-2023-77215",
                bank_name="Bank of Baroda",
                branch_name="Pari Chowk Branch (IFSC: BARB0PARICH)",
                amount=Decimal("2500000.00"),
                issue_date=today - timedelta(days=365),
                maturity_date=today + timedelta(days=365 * 4),
                scrutiny_status=ScrutinyStatus.PENDING_VERIFICATION.value,
                validity_status=ValidityStatus.ACTIVE.value,
                created_by=inst_user.id,
            )
            fdr4 = FDRRecord(
                institution_id=inst.id,
                fdr_number="FDR-HDFC-2024-11842",
                bank_name="HDFC Bank",
                branch_name="Sector 62 Noida Branch (IFSC: HDFC0001234)",
                amount=Decimal("2000000.00"),
                issue_date=today - timedelta(days=180),
                maturity_date=today + timedelta(days=365 * 5),
                scrutiny_status=ScrutinyStatus.RETURNED.value,
                validity_status=ValidityStatus.ACTIVE.value,
                created_by=inst_user.id,
            )
            fdr5 = FDRRecord(
                institution_id=inst.id,
                fdr_number="FDR-ICICI-2025-05531",
                bank_name="ICICI Bank",
                branch_name="Knowledge Park II Branch (IFSC: ICIC0005531)",
                amount=Decimal("1800000.00"),
                issue_date=today - timedelta(days=30),
                maturity_date=today + timedelta(days=365 * 3),
                scrutiny_status=ScrutinyStatus.DRAFT.value,
                validity_status=ValidityStatus.ACTIVE.value,
                created_by=inst_user.id,
            )
            db.session.add_all([fdr1, fdr2, fdr3, fdr4, fdr5])
            db.session.commit()

            # Add workflow history for fdr4 (returned with deficiency)
            h1 = FDRWorkflowHistory(
                fdr_id=fdr4.id,
                from_status=ScrutinyStatus.DRAFT.value,
                to_status=ScrutinyStatus.SUBMITTED.value,
                actor_id=inst_user.id,
                remarks="Initial submission for security compliance.",
                is_deficiency=False,
            )
            h2 = FDRWorkflowHistory(
                fdr_id=fdr4.id,
                from_status=ScrutinyStatus.SUBMITTED.value,
                to_status=ScrutinyStatus.PENDING_VERIFICATION.value,
                actor_id=officer_user.id,
                remarks="Review process started by AICTE officer.",
                is_deficiency=False,
            )
            h3 = FDRWorkflowHistory(
                fdr_id=fdr4.id,
                from_status=ScrutinyStatus.PENDING_VERIFICATION.value,
                to_status=ScrutinyStatus.RETURNED.value,
                actor_id=officer_user.id,
                remarks="Bank branch seal and authorized signatory signature are missing on page 2. Please re-upload.",
                is_deficiency=True,
                resolution_status="UNRESOLVED",
            )
            db.session.add_all([h1, h2, h3])

            # Seed notifications for user
            n1 = Notification(
                user_id=inst_user.id,
                title="FDR Maturing Soon (12 Days Remaining)",
                message="FDR-SBI-2021-99821 with State Bank of India matures in 12 days. Please initiate renewal or release.",
                notification_type=NotificationType.ALERT.value,
                is_read=False,
            )
            n2 = Notification(
                user_id=inst_user.id,
                title="FDR Returned for Correction",
                message="FDR-HDFC-2024-11842 was returned with remarks: Bank branch seal and authorized signatory signature are missing.",
                notification_type=NotificationType.ACTION_REQUIRED.value,
                is_read=False,
            )
            n3 = Notification(
                user_id=inst_user.id,
                title="FDR Verification Approved",
                message="FDR-SBI-2021-99821 has been verified and registered by AICTE bureau.",
                notification_type=NotificationType.INFO.value,
                is_read=True,
            )
            db.session.add_all([n1, n2, n3])
            db.session.commit()
            click.echo("Seeded sample FDR records, workflow history, and notifications.")

        # 4. Seed sample renewal / release requests if none exist
        from app.models.fdr_request import FDRRequest
        if FDRRequest.query.count() == 0 and inst_user:
            sample_fdr = FDRRecord.query.filter_by(institution_id=inst.id).first()
            if sample_fdr:
                req1 = FDRRequest(
                    fdr_id=sample_fdr.id,
                    institution_id=inst.id,
                    created_by=inst_user.id,
                    request_type="Renewal",
                    status="Under Review",
                    stage="Regional Scrutiny Desk",
                    reason="Requesting 3-year term extension with State Bank of India as per AICTE Approval Process norms.",
                    supporting_document="SBI_Deposit_Extension_Undertaking.pdf",
                    document_size=1843200,
                    remarks="Formal application filed by College Principal.",
                )
                db.session.add(req1)
                db.session.commit()

                # Ensure sample PDF exists on disk
                sample_path = Path(app.config["REQUEST_UPLOAD_FOLDER"]) / "SBI_Deposit_Extension_Undertaking.pdf"
                if not sample_path.exists():
                    os.makedirs(sample_path.parent, exist_ok=True)
                    with open(sample_path, "wb") as f:
                        f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000108 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n187\n%%EOF\n")

                click.echo("Seeded sample FDR renewal petition.")


    # Initialize background scheduler if enabled
    from app.services.scheduler import init_scheduler

    init_scheduler(app)

    # Register standard JSON error handlers
    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Resource not found", "status_code": 404}), 404

    @app.errorhandler(413)
    def handle_payload_too_large(error):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Uploaded file exceeds maximum permitted size limit.",
                    "code": "FILE_TOO_LARGE",
                }
            ),
            413,
        )

    @app.errorhandler(500)
    def handle_internal_server_error(error):
        return (
            jsonify({"error": "Internal server error", "status_code": 500}),
            500,
        )

    return app
