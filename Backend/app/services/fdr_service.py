from typing import Any
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import or_

from app.extensions import db
from app.models.audit import AuditLog
from app.models.enums import ScrutinyStatus, UserRole, ValidityStatus
from app.models.fdr import FDRRecord
from app.models.institution import Institution
from app.models.user import User


class FDRServiceError(Exception):
    """Base exception for FDR service operations."""

    def __init__(self, message: str, code: str = "ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class FDRValidationError(FDRServiceError):
    """Exception for schema and business validation failures."""

    def __init__(self, errors: dict):
        super().__init__(
            message="Validation failed for one or more fields.",
            code="VALIDATION_ERROR",
            status_code=400,
        )
        self.errors = errors


class FDRNotFoundError(FDRServiceError):
    """Exception when an FDR record does not exist or is inaccessible."""

    def __init__(
        self, message: str = "FDR record not found.", code: str = "FDR_NOT_FOUND"
    ):
        super().__init__(message=message, code=code, status_code=404)


class FDRPermissionError(FDRServiceError):
    """Exception for unauthorized operations on FDR records."""

    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        code: str = "PERMISSION_DENIED",
    ):
        super().__init__(message=message, code=code, status_code=403)


class FDRDuplicateError(FDRServiceError):
    """Exception when a duplicate FDR number is submitted for an institution."""

    def __init__(
        self,
        message: str = "An FDR with this number already exists for this institution.",
        code: str = "DUPLICATE_FDR_NUMBER",
    ):
        super().__init__(message=message, code=code, status_code=409)


def parse_strict_date(value: str | date, field_name: str) -> date:
    """Parse strict YYYY-MM-DD date representation."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be formatted as YYYY-MM-DD.")
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"'{field_name}' must be formatted as YYYY-MM-DD.")


def parse_positive_amount(value: Any) -> Decimal:
    """Parse and validate monetary amount as a finite, positive Decimal."""
    if isinstance(value, bool):
        raise ValueError("Amount must be a numeric value, not a boolean.")
    try:
        decimal_val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Amount must be a valid numeric decimal representation.")

    if not decimal_val.is_finite():
        raise ValueError("Amount must be a finite number.")

    if decimal_val <= Decimal("0"):
        raise ValueError("Amount must be a positive value greater than zero.")

    # Quantize to 2 decimal places
    return decimal_val.quantize(Decimal("0.01"))


def validate_create_payload(data: dict, current_user: User) -> dict:
    """Validate data dictionary for FDR creation."""
    errors = {}
    if not isinstance(data, dict):
        raise FDRValidationError({"body": "Request payload must be a JSON object."})

    # Required fields
    required_fields = [
        "fdr_number",
        "bank_name",
        "branch_name",
        "amount",
        "issue_date",
        "maturity_date",
    ]
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            errors[field] = f"Field '{field}' is required."

    # Validate string fields
    fdr_number = str(data.get("fdr_number", "")).strip()
    bank_name = str(data.get("bank_name", "")).strip()
    branch_name = str(data.get("branch_name", "")).strip()

    if not fdr_number and "fdr_number" not in errors:
        errors["fdr_number"] = "FDR number cannot be blank."
    if not bank_name and "bank_name" not in errors:
        errors["bank_name"] = "Bank name cannot be blank."
    if not branch_name and "branch_name" not in errors:
        errors["branch_name"] = "Branch name cannot be blank."

    # Validate amount
    amount_dec = None
    if "amount" in data and "amount" not in errors:
        try:
            amount_dec = parse_positive_amount(data["amount"])
        except ValueError as ex:
            errors["amount"] = str(ex)

    # Validate dates
    issue_d = None
    maturity_d = None
    if "issue_date" in data and "issue_date" not in errors:
        try:
            issue_d = parse_strict_date(data["issue_date"], "issue_date")
        except ValueError as ex:
            errors["issue_date"] = str(ex)

    if "maturity_date" in data and "maturity_date" not in errors:
        try:
            maturity_d = parse_strict_date(data["maturity_date"], "maturity_date")
        except ValueError as ex:
            errors["maturity_date"] = str(ex)

    if issue_d and maturity_d:
        if maturity_d < issue_d:
            errors["maturity_date"] = "Maturity date cannot be earlier than issue date."

    # Determine institution_id
    user_category = UserRole.normalize_category(current_user.role)
    institution_id = None

    if user_category == "INSTITUTION":
        if not current_user.institution_id or not current_user.institution:
            raise FDRPermissionError(
                "Institution user account is not linked to any valid registered institution.",
                code="UNLINKED_INSTITUTION",
            )
        institution_id = current_user.institution_id
    else:
        # Officer or Admin can specify institution_id
        inst_param = data.get("institution_id")
        if not inst_param:
            errors["institution_id"] = (
                "Field 'institution_id' is required when created by an officer or administrator."
            )
        else:
            try:
                inst_id = int(inst_param)
                institution = db.session.get(Institution, inst_id)
                if not institution:
                    errors["institution_id"] = (
                        f"Institution with ID {inst_id} does not exist."
                    )
                else:
                    institution_id = inst_id
            except (ValueError, TypeError):
                errors["institution_id"] = (
                    "Field 'institution_id' must be a valid integer."
                )

    # Validate initial status if supplied
    scrutiny_status = ScrutinyStatus.DRAFT.value
    if "scrutiny_status" in data:
        raw_status = str(data["scrutiny_status"]).strip().upper()
        if raw_status not in ScrutinyStatus.values():
            errors["scrutiny_status"] = (
                f"Invalid scrutiny status. Allowed: {sorted(list(ScrutinyStatus.values()))}"
            )
        elif user_category == "INSTITUTION" and raw_status in (
            ScrutinyStatus.VERIFIED.value,
            ScrutinyStatus.REJECTED.value,
            ScrutinyStatus.PENDING_VERIFICATION.value,
            ScrutinyStatus.RETURNED.value,
        ):
            errors["scrutiny_status"] = (
                f"Institution users cannot directly set scrutiny status to '{raw_status}'."
            )
        else:
            scrutiny_status = raw_status

    validity_status = ValidityStatus.ACTIVE.value
    if "validity_status" in data:
        raw_val = str(data["validity_status"]).strip().upper()
        if raw_val not in ValidityStatus.values():
            errors["validity_status"] = (
                f"Invalid validity status. Allowed: {sorted(list(ValidityStatus.values()))}"
            )
        elif user_category == "INSTITUTION" and raw_val != ValidityStatus.ACTIVE.value:
            errors["validity_status"] = (
                "Institution users may only initialize FDRs with 'ACTIVE' validity status."
            )
        else:
            validity_status = raw_val

    if errors:
        raise FDRValidationError(errors)

    return {
        "institution_id": institution_id,
        "fdr_number": fdr_number,
        "bank_name": bank_name,
        "branch_name": branch_name,
        "amount": amount_dec,
        "issue_date": issue_d,
        "maturity_date": maturity_d,
        "scrutiny_status": scrutiny_status,
        "validity_status": validity_status,
        "created_by": current_user.id,
    }



def normalize_fdr_number(number: str) -> str:
    """Normalize FDR number by stripping non-alphanumeric characters and converting to uppercase."""
    if not number:
        return ""
    import re
    return re.sub(r"[^A-Za-z0-9]", "", str(number)).upper()


def check_fdr_duplicates(fdr_number: str, institution_id: int, current_user: User) -> dict:
    """Check for identical or normalized FDR number intra- and cross-institution."""
    clean_raw = str(fdr_number).strip()
    normalized = normalize_fdr_number(clean_raw)
    if not normalized:
        return {"is_duplicate": False, "scope": None, "message": "Valid FDR number required."}

    user_category = UserRole.normalize_category(current_user.role)

    # 1. Intra-institution exact or normalized match
    inst_records = FDRRecord.query.filter_by(institution_id=institution_id).all()
    for rec in inst_records:
        if rec.fdr_number.strip().upper() == clean_raw.upper() or normalize_fdr_number(rec.fdr_number) == normalized:
            return {
                "is_duplicate": True,
                "scope": "INTERNAL",
                "message": f"An FDR with this number ('{rec.fdr_number}') already exists in this institution.",
                "fdr_id": rec.id,
            }

    # 2. Cross-institution match
    all_other_records = FDRRecord.query.filter(FDRRecord.institution_id != institution_id).all()
    for rec in all_other_records:
        if normalize_fdr_number(rec.fdr_number) == normalized:
            if user_category == "INSTITUTION":
                return {
                    "is_duplicate": True,
                    "scope": "CROSS_INSTITUTION",
                    "message": "A security deposit with this receipt reference is already registered in the AICTE portal. Please verify the receipt details or contact AICTE support.",
                }
            else:
                return {
                    "is_duplicate": True,
                    "scope": "CROSS_INSTITUTION",
                    "message": f"Matching FDR reference registered under {rec.institution.name if rec.institution else 'another institution'} (Code: {rec.institution.institution_code if rec.institution else ''}).",
                    "fdr_id": rec.id,
                    "institution_id": rec.institution_id,
                    "institution_name": rec.institution.name if rec.institution else None,
                }

    return {"is_duplicate": False, "scope": None, "message": "No duplicate FDR reference found."}

def create_fdr_record(data: dict, current_user: User) -> FDRRecord:
    """Create a new FDR record after validating inputs and enforcing uniqueness."""
    validated = validate_create_payload(data, current_user)

    # Enhanced intra-institution duplicate check with normalization (enforces uq_institution_fdr_number)
    dup_res = check_fdr_duplicates(validated["fdr_number"], validated["institution_id"], current_user)
    if dup_res["is_duplicate"] and dup_res["scope"] == "INTERNAL":
        raise FDRDuplicateError(dup_res["message"])

    fdr = FDRRecord(**validated)
    db.session.add(fdr)
    db.session.flush()

    # Log audit entry
    audit = AuditLog(
        user_id=current_user.id,
        action="FDR_CREATED",
        entity_type="FDRRecord",
        entity_id=fdr.id,
        details=f"FDR '{fdr.fdr_number}' created for institution {fdr.institution_id} with amount {fdr.amount}.",
    )
    db.session.add(audit)
    db.session.commit()
    return fdr


def get_authorized_fdr(fdr_id: int, current_user: User) -> FDRRecord:
    """Retrieve an authorized FDR record or raise FDRNotFoundError."""
    fdr = db.session.get(FDRRecord, fdr_id)
    if not fdr:
        raise FDRNotFoundError()

    user_category = UserRole.normalize_category(current_user.role)
    if user_category == "INSTITUTION":
        if fdr.institution_id != current_user.institution_id:
            # Return 404 to avoid leaking record existence across institutions
            raise FDRNotFoundError()

    return fdr


def list_authorized_fdrs(current_user: User, filters: dict) -> tuple[list[FDRRecord], dict]:
    """List FDR records applying data isolation, query filters, search, and pagination."""
    query = FDRRecord.query

    user_category = UserRole.normalize_category(current_user.role)

    # 1. Enforce strict institution data isolation
    if user_category == "INSTITUTION":
        if not current_user.institution_id:
            return [], {"page": 1, "per_page": 10, "total": 0, "pages": 0}
        query = query.filter(FDRRecord.institution_id == current_user.institution_id)
    else:
        # Officer/Admin may filter by institution_id
        inst_id = filters.get("institution_id")
        if inst_id is not None and inst_id != "":
            try:
                query = query.filter(FDRRecord.institution_id == int(inst_id))
            except (ValueError, TypeError):
                raise FDRValidationError(
                    {"institution_id": "Query param 'institution_id' must be an integer."}
                )

    # 2. Filter by bank_name
    bank_name = filters.get("bank_name")
    if bank_name:
        query = query.filter(FDRRecord.bank_name.ilike(f"%{bank_name.strip()}%"))

    # 3. Filter by scrutiny_status
    scrutiny_status = filters.get("scrutiny_status")
    if scrutiny_status:
        val = str(scrutiny_status).strip().upper()
        if val not in ScrutinyStatus.values():
            raise FDRValidationError(
                {
                    "scrutiny_status": f"Invalid scrutiny status filter '{val}'. Allowed: {sorted(list(ScrutinyStatus.values()))}"
                }
            )
        query = query.filter(FDRRecord.scrutiny_status == val)

    # 4. Filter by validity_status
    validity_status = filters.get("validity_status")
    if validity_status:
        val = str(validity_status).strip().upper()
        if val not in ValidityStatus.values():
            raise FDRValidationError(
                {
                    "validity_status": f"Invalid validity status filter '{val}'. Allowed: {sorted(list(ValidityStatus.values()))}"
                }
            )
        query = query.filter(FDRRecord.validity_status == val)

    # 4b. Filter by precise maturity brackets
    mat_bracket = filters.get("maturity_bracket") or filters.get("maturity_filter")
    if mat_bracket and str(mat_bracket).strip().upper() != "ALL":
        from datetime import timedelta
        from app.services.maturity_service import get_business_date
        ref_d = get_business_date()
        mb = str(mat_bracket).strip().upper()
        if mb in ("MATURING_90", "MATURING_90_DAYS", "90D"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=60), FDRRecord.maturity_date <= ref_d + timedelta(days=90))
        elif mb in ("MATURING_60", "MATURING_60_DAYS", "60D"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=30), FDRRecord.maturity_date <= ref_d + timedelta(days=60))
        elif mb in ("MATURING_30", "MATURING_30_DAYS", "MATURING_SOON", "30D"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=7), FDRRecord.maturity_date <= ref_d + timedelta(days=30))
        elif mb in ("MATURING_7", "MATURING_7_DAYS", "7D"):
            query = query.filter(FDRRecord.maturity_date >= ref_d, FDRRecord.maturity_date <= ref_d + timedelta(days=7))
        elif mb == "MATURED":
            query = query.filter(FDRRecord.maturity_date >= ref_d - timedelta(days=30), FDRRecord.maturity_date < ref_d)
        elif mb in ("OVERDUE", "OVERDUE_ACTION"):
            query = query.filter(FDRRecord.maturity_date < ref_d - timedelta(days=30))
        elif mb in ("ACTIVE", "FUTURE"):
            query = query.filter(FDRRecord.maturity_date > ref_d + timedelta(days=90))

    # 5. Filter by maturity range
    maturity_from = filters.get("maturity_from")
    if maturity_from:
        try:
            m_from = parse_strict_date(maturity_from, "maturity_from")
            query = query.filter(FDRRecord.maturity_date >= m_from)
        except ValueError as ex:
            raise FDRValidationError({"maturity_from": str(ex)})

    maturity_to = filters.get("maturity_to")
    if maturity_to:
        try:
            m_to = parse_strict_date(maturity_to, "maturity_to")
            query = query.filter(FDRRecord.maturity_date <= m_to)
        except ValueError as ex:
            raise FDRValidationError({"maturity_to": str(ex)})

    # 6. Global text search
    search = filters.get("search")
    if search:
        term = f"%{str(search).strip()}%"
        query = query.filter(
            or_(
                FDRRecord.fdr_number.ilike(term),
                FDRRecord.bank_name.ilike(term),
                FDRRecord.branch_name.ilike(term),
            )
        )

    # 7. Order by created_at descending
    query = query.order_by(FDRRecord.created_at.desc(), FDRRecord.id.desc())

    # 8. Pagination
    try:
        page = max(1, int(filters.get("page", 1)))
    except (ValueError, TypeError):
        raise FDRValidationError({"page": "Page parameter must be a positive integer."})

    try:
        per_page = min(100, max(1, int(filters.get("per_page", 10))))
    except (ValueError, TypeError):
        raise FDRValidationError(
            {"per_page": "Per-page parameter must be a positive integer (max 100)."}
        )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    pagination = {
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total": paginated.total,
        "pages": paginated.pages,
    }
    return paginated.items, pagination


def update_fdr_record(fdr_id: int, data: dict, current_user: User) -> FDRRecord:
    """Update permitted fields of an FDR record according to user role and workflow rules."""
    fdr = get_authorized_fdr(fdr_id, current_user)

    if not isinstance(data, dict):
        raise FDRValidationError({"body": "Request payload must be a JSON object."})

    errors = {}
    user_category = UserRole.normalize_category(current_user.role)

    # Disallowed fields that can never be modified via PATCH
    immutable_fields = {"id", "created_by", "created_at", "updated_at", "institution_id"}
    for field in immutable_fields:
        if field in data and data[field] != getattr(fdr, field, None):
            errors[field] = f"Field '{field}' is immutable and cannot be modified."

    if errors:
        raise FDRValidationError(errors)

    # Institution user editing rules
    if user_category == "INSTITUTION":
        # 1. Workflow status check: Only DRAFT and RETURNED can be edited by an institution user
        if fdr.scrutiny_status not in (ScrutinyStatus.DRAFT.value, ScrutinyStatus.RETURNED.value):
            raise FDRPermissionError(
                f"FDR record cannot be modified while in scrutiny status '{fdr.scrutiny_status}'. "
                "Only records in DRAFT or RETURNED status may be updated.",
                code="RECORD_LOCKED",
            )

        # 2. Status change restrictions for institution users
        if "scrutiny_status" in data:
            requested_status = str(data["scrutiny_status"]).strip().upper()
            if requested_status not in ScrutinyStatus.values():
                errors["scrutiny_status"] = (
                    f"Invalid scrutiny status. Allowed: {sorted(list(ScrutinyStatus.values()))}"
                )
            elif requested_status not in (
                ScrutinyStatus.DRAFT.value,
                ScrutinyStatus.SUBMITTED.value,
            ):
                raise FDRPermissionError(
                    f"Institution users cannot transition records to officer-controlled status '{requested_status}'.",
                    code="OFFICER_STATUS_RESTRICTED",
                )

        if "validity_status" in data:
            raise FDRPermissionError(
                "Institution users cannot modify validity status.",
                code="VALIDITY_STATUS_RESTRICTED",
            )

    # Officer/Admin rules
    else:
        if "scrutiny_status" in data:
            requested_status = str(data["scrutiny_status"]).strip().upper()
            if requested_status not in ScrutinyStatus.values():
                errors["scrutiny_status"] = (
                    f"Invalid scrutiny status. Allowed: {sorted(list(ScrutinyStatus.values()))}"
                )

        if "validity_status" in data:
            requested_val = str(data["validity_status"]).strip().upper()
            if requested_val not in ValidityStatus.values():
                errors["validity_status"] = (
                    f"Invalid validity status. Allowed: {sorted(list(ValidityStatus.values()))}"
                )

    # Validate updated fields
    target_fdr_number = fdr.fdr_number
    if "fdr_number" in data:
        cleaned_num = str(data["fdr_number"]).strip()
        if not cleaned_num:
            errors["fdr_number"] = "FDR number cannot be blank."
        else:
            target_fdr_number = cleaned_num

    target_bank = fdr.bank_name
    if "bank_name" in data:
        cleaned_bank = str(data["bank_name"]).strip()
        if not cleaned_bank:
            errors["bank_name"] = "Bank name cannot be blank."
        else:
            target_bank = cleaned_bank

    target_branch = fdr.branch_name
    if "branch_name" in data:
        cleaned_branch = str(data["branch_name"]).strip()
        if not cleaned_branch:
            errors["branch_name"] = "Branch name cannot be blank."
        else:
            target_branch = cleaned_branch

    target_amount = fdr.amount
    if "amount" in data:
        try:
            target_amount = parse_positive_amount(data["amount"])
        except ValueError as ex:
            errors["amount"] = str(ex)

    target_issue_d = fdr.issue_date
    if "issue_date" in data:
        try:
            target_issue_d = parse_strict_date(data["issue_date"], "issue_date")
        except ValueError as ex:
            errors["issue_date"] = str(ex)

    target_maturity_d = fdr.maturity_date
    if "maturity_date" in data:
        try:
            target_maturity_d = parse_strict_date(data["maturity_date"], "maturity_date")
        except ValueError as ex:
            errors["maturity_date"] = str(ex)

    if target_issue_d and target_maturity_d and target_maturity_d < target_issue_d:
        errors["maturity_date"] = "Maturity date cannot be earlier than issue date."

    if errors:
        raise FDRValidationError(errors)

    # Check for uniqueness conflict if FDR number is changing
    if target_fdr_number != fdr.fdr_number:
        conflict = FDRRecord.query.filter(
            FDRRecord.institution_id == fdr.institution_id,
            FDRRecord.fdr_number == target_fdr_number,
            FDRRecord.id != fdr.id,
        ).first()
        if conflict:
            raise FDRDuplicateError(
                f"FDR number '{target_fdr_number}' is already registered for this institution."
            )

    # Apply changes
    fdr.fdr_number = target_fdr_number
    fdr.bank_name = target_bank
    fdr.branch_name = target_branch
    fdr.amount = target_amount
    fdr.issue_date = target_issue_d
    fdr.maturity_date = target_maturity_d

    if "scrutiny_status" in data:
        fdr.scrutiny_status = str(data["scrutiny_status"]).strip().upper()

    if "validity_status" in data:
        fdr.validity_status = str(data["validity_status"]).strip().upper()

    # Log audit trail
    audit = AuditLog(
        user_id=current_user.id,
        action="FDR_UPDATED",
        entity_type="FDRRecord",
        entity_id=fdr.id,
        details=f"FDR '{fdr.fdr_number}' updated by {current_user.email}.",
    )
    db.session.add(audit)
    db.session.commit()

    return fdr
