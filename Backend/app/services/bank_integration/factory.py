import logging
from typing import Any, Optional
from flask import current_app

from app.services.bank_integration.base import BankProvider, ProviderMode
from app.services.bank_integration.mock_provider import MockBankProvider

logger = logging.getLogger(__name__)


def get_bank_provider(provider_type: Optional[str] = None) -> BankProvider:
    """
    Factory function returning the configured BankProvider instance.

    Guarantees:
    - Defaults to MockBankProvider unless a real provider is explicitly configured AND authorized.
    - Missing or unconfigured provider will NEVER silently imply real connectivity.
    """
    target = provider_type
    if not target:
        try:
            target = current_app.config.get("BANK_PROVIDER", "mock")
        except RuntimeError:
            # Outside of application context
            target = "mock"

    target = str(target or "mock").lower().strip()

    if target in ("mock", "demo", "simulated", "prototype"):
        return MockBankProvider()

    # If an operator attempts to configure a real bank adapter
    if target in ("real", "sbi", "hdfc", "pnb", "rbi_cbs"):
        # Strict validation: Check for authorized production credentials
        api_url = current_app.config.get("BANK_API_URL")
        client_id = current_app.config.get("BANK_CLIENT_ID")
        client_secret = current_app.config.get("BANK_CLIENT_SECRET")

        if not (api_url and client_id and client_secret):
            logger.warning(
                f"Bank provider '{target}' requested, but required credentials/API endpoints "
                "are missing. Safely defaulting to MockBankProvider (DEMO mode). Real bank "
                "connectivity cannot be established without bilateral authorization."
            )
            return MockBankProvider()

        # In prototype environment, real banking network adapters are not connected
        logger.warning(
            f"Provider '{target}' credentials supplied, but live CBS connection is disabled "
            "in this prototype environment. Falling back to MockBankProvider."
        )
        return MockBankProvider()

    logger.warning(
        f"Unrecognized BANK_PROVIDER '{target}'. Safely defaulting to MockBankProvider (DEMO mode)."
    )
    return MockBankProvider()


def get_provider_info() -> dict[str, Any]:
    """
    Returns sanitized public metadata regarding the currently active bank provider.
    Safe to expose to frontend and API consumers.
    """
    provider = get_bank_provider()
    return {
        "provider_name": provider.name,
        "provider_mode": provider.mode.value,
        "is_demo": provider.mode == ProviderMode.DEMO,
        "is_mock": True if provider.mode == ProviderMode.DEMO else False,
        "disclaimer": provider.disclaimer,
        "supported_scenarios": [
            {
                "id": "MATCHED",
                "label": "Simulate Matched (Consistent CBS Record)",
                "description": "FDR exists in bank core and all parameters match portal record.",
            },
            {
                "id": "MISMATCH",
                "label": "Simulate Mismatch (Discrepancy Detected)",
                "description": "Bank CBS shows lower deposit principal or earlier maturity date.",
            },
            {
                "id": "NOT_FOUND",
                "label": "Simulate Not Found (Account Missing)",
                "description": "FDR number is not registered in the bank repository.",
            },
            {
                "id": "UNAVAILABLE",
                "label": "Simulate Timeout / Gateway Down",
                "description": "Simulates 10s bank gateway timeout or scheduled CBS maintenance.",
            },
        ],
    }
