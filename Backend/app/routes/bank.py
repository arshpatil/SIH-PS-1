import json
import logging
from flask import Blueprint, current_app, g, jsonify, request

from app.extensions import db
from app.models.audit import AuditLog
from app.models.bank_verification import BankVerificationLog
from app.models.enums import UserRole
from app.models.fdr import FDRRecord
from app.models.fdr_request import FDRRequest
from app.security import login_required
from app.services.bank_integration.factory import get_bank_provider, get_provider_info

logger = logging.getLogger(__name__)

bank_bp = Blueprint("bank", __name__, url_prefix="/api/bank")


@bank_bp.route("/status", methods=["GET"])
@login_required
def get_status():
    """
    Retrieve current bank integration provider metadata, mode (DEMO vs REAL),
    consumer disclaimers, and supported simulation scenarios.
    Does not expose sensitive credentials.
    """
    info = get_provider_info()
    return jsonify({
        "success": True,
        "data": info,
    }), 200


@bank_bp.route("/verify-fdr/<int:fdr_id>", methods=["POST"])
@login_required
def verify_fdr_endpoint(fdr_id: int):
    """
    Dispatch a bank verification query for a specific FDR record.

    Access Control:
    - AICTE Officer or Admin can verify any FDR.
    - Institution users can only verify FDRs belonging to their institution.
    """
    fdr = db.session.get(FDRRecord, fdr_id)
    if not fdr:
        return jsonify({"success": False, "error": "FDR record not found.", "code": "NOT_FOUND"}), 404

    # Tenant isolation check
    if g.current_user.role == UserRole.INSTITUTION.value:
        if fdr.institution_id != g.current_user.institution_id:
            return jsonify({"success": False, "error": "Access denied to FDR record.", "code": "FORBIDDEN"}), 403

    payload = request.get_json(silent=True) or {}
    simulation_scenario = payload.get("scenario") or payload.get("simulation_scenario")

    provider = get_bank_provider()

    expected_details = {
        "fdr_number": fdr.fdr_number,
        "amount": float(fdr.amount) if fdr.amount is not None else 0.0,
        "maturity_date": fdr.maturity_date.isoformat() if fdr.maturity_date else None,
        "issue_date": fdr.issue_date.isoformat() if fdr.issue_date else None,
        "bank_name": fdr.bank_name,
        "branch_name": fdr.branch_name,
        "institution_name": fdr.institution.name if fdr.institution else "",
        "institution_code": fdr.institution.institution_code if fdr.institution else "",
    }

    institution_ref = fdr.institution.institution_code if fdr.institution else str(fdr.institution_id)

    # Execute provider verification
    result = provider.verify_fdr(
        fdr_number=fdr.fdr_number,
        institution_reference=institution_ref,
        expected_details=expected_details,
        simulation_scenario=simulation_scenario,
    )

    # Persist verification log
    log_entry = BankVerificationLog(
        fdr_id=fdr.id,
        institution_id=fdr.institution_id,
        requested_by=g.current_user.id,
        provider_name=result.provider_name,
        provider_mode=result.provider_mode,
        verification_status=result.status,
        bank_reference=result.bank_reference,
        matched_fields_json=json.dumps(result.matched_fields),
        mismatched_fields_json=json.dumps(result.mismatched_fields),
        raw_details_json=json.dumps(result.bank_fdr_details) if result.bank_fdr_details else None,
        message=result.message,
        disclaimer=result.disclaimer,
    )
    db.session.add(log_entry)

    # Immutable Audit Log entry
    audit = AuditLog(
        user_id=g.current_user.id,
        action="BANK_VERIFICATION_CHECK",
        entity_type="FDRRecord",
        entity_id=fdr.id,
        details=(
            f"Bank verification check performed by {g.current_user.full_name} "
            f"({g.current_user.role}) using {result.provider_name} [{result.provider_mode}]. "
            f"Status: {result.status}. Bank Ref: {result.bank_reference or 'N/A'}"
        ),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": result.message,
        "data": log_entry.to_dict(),
        "result": result.to_dict(),
    }), 200


@bank_bp.route("/history/<int:fdr_id>", methods=["GET"])
@login_required
def get_verification_history(fdr_id: int):
    """
    Retrieve historical bank verification queries for an FDR record.
    """
    fdr = db.session.get(FDRRecord, fdr_id)
    if not fdr:
        return jsonify({"success": False, "error": "FDR record not found.", "code": "NOT_FOUND"}), 404

    # Tenant isolation check
    if g.current_user.role == UserRole.INSTITUTION.value:
        if fdr.institution_id != g.current_user.institution_id:
            return jsonify({"success": False, "error": "Access denied.", "code": "FORBIDDEN"}), 403

    logs = (
        BankVerificationLog.query.filter_by(fdr_id=fdr.id)
        .order_by(BankVerificationLog.created_at.desc())
        .limit(20)
        .all()
    )

    return jsonify({
        "success": True,
        "data": [l.to_dict() for l in logs],
    }), 200


@bank_bp.route("/check-renewal/<int:request_id>", methods=["POST"])
@login_required
def check_renewal_status_endpoint(request_id: int):
    """
    Query participating bank adapter or prototype mock provider for renewal execution status.
    NOTE: A mock response or approved petition does NOT alter official FDR parameters.
    """
    fdr_req = db.session.get(FDRRequest, request_id)
    if not fdr_req:
        return jsonify({"success": False, "error": "Petition request not found.", "code": "NOT_FOUND"}), 404

    # Tenant isolation check
    if g.current_user.role == UserRole.INSTITUTION.value:
        if fdr_req.institution_id != g.current_user.institution_id:
            return jsonify({"success": False, "error": "Access denied.", "code": "FORBIDDEN"}), 403

    payload = request.get_json(silent=True) or {}
    bank_ref = payload.get("bank_reference") or f"REN-REQ-{fdr_req.id:04d}"

    provider = get_bank_provider()
    result = provider.get_renewal_status(bank_ref)

    # Record in AuditLog
    audit = AuditLog(
        user_id=g.current_user.id,
        action="BANK_RENEWAL_STATUS_CHECK",
        entity_type="FDRRequest",
        entity_id=fdr_req.id,
        details=(
            f"Queried bank renewal status for REQ-{fdr_req.id:04d} using {result.provider_name} "
            f"[{result.provider_mode}]. Status: {result.status}. Ref: {bank_ref}"
        ),
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": result.message,
        "data": result.to_dict(),
    }), 200
