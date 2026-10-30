from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ProviderMode(str, Enum):
    """Execution mode of the bank integration provider."""
    DEMO = "DEMO"  # Prototype / simulated mock integration
    REAL = "REAL"  # Live or sandbox core-banking API adapter


class BankVerificationStatus(str, Enum):
    """Standardized verification outcome returned by a bank provider."""
    MATCHED = "MATCHED"          # FDR exists in bank core and all details match
    MISMATCH = "MISMATCH"        # FDR exists in bank core but specific fields differ
    NOT_FOUND = "NOT_FOUND"      # FDR number / account does not exist in bank registry
    UNAVAILABLE = "UNAVAILABLE"  # Bank gateway timed out or service is temporarily down
    ERROR = "ERROR"              # Malformed request, schema validation error, or provider exception


class BankRenewalStatus(str, Enum):
    """Standardized renewal transaction outcome returned by a bank provider."""
    CONFIRMED = "CONFIRMED"      # Bank has executed the deposit renewal with new terms
    PENDING = "PENDING"          # Renewal instruction is undergoing branch processing
    REJECTED = "REJECTED"        # Bank declined renewal (e.g., lien instructions, funds issue)
    NOT_FOUND = "NOT_FOUND"      # Renewal reference number not found in bank CBS
    UNAVAILABLE = "UNAVAILABLE"  # Network failure or bank gateway timeout


@dataclass
class VerificationResult:
    """Standard response model for an FDR verification check against a bank provider."""
    is_mock: bool
    provider_name: str
    provider_mode: str  # "DEMO" or "REAL"
    status: str         # BankVerificationStatus value
    fdr_number: str
    bank_reference: Optional[str] = None
    matched_fields: dict[str, Any] = field(default_factory=dict)
    mismatched_fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    bank_fdr_details: Optional[dict[str, Any]] = None
    message: str = ""
    disclaimer: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RenewalStatusResult:
    """Standard response model for a renewal status query against a bank provider."""
    is_mock: bool
    provider_name: str
    provider_mode: str
    status: str         # BankRenewalStatus value
    bank_reference: Optional[str] = None
    renewal_details: Optional[dict[str, Any]] = None
    message: str = ""
    disclaimer: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BankProvider(ABC):
    """
    Abstract Base Class defining the contract for bank integration adapters.
    All real and mock providers must adhere to this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier name of the bank provider adapter."""
        pass

    @property
    @abstractmethod
    def mode(self) -> ProviderMode:
        """Operating mode: DEMO or REAL."""
        pass

    @property
    @abstractmethod
    def disclaimer(self) -> str:
        """Mandatory consumer notice indicating simulated or production status."""
        pass

    @abstractmethod
    def verify_fdr(
        self,
        fdr_number: str,
        institution_reference: str,
        expected_details: Optional[dict[str, Any]] = None,
        simulation_scenario: Optional[str] = None,
    ) -> VerificationResult:
        """
        Verify the existence and parameter consistency of a security deposit FDR.

        :param fdr_number: Unique FDR / Deposit receipt number.
        :param institution_reference: Code or identifier of the institution.
        :param expected_details: Dict of local parameters (amount, maturity_date, bank_name, etc.)
        :param simulation_scenario: Optional deterministic override for testing (DEMO mode only).
        :return: VerificationResult with matched/mismatched field differences.
        """
        pass

    @abstractmethod
    def get_fdr_details(
        self,
        fdr_number: str,
        institution_reference: str,
    ) -> dict[str, Any]:
        """
        Query the bank for raw deposit parameters.

        :param fdr_number: Unique FDR number.
        :param institution_reference: Code of the institution.
        :return: Dict containing core banking deposit parameters.
        """
        pass

    @abstractmethod
    def get_renewal_status(
        self,
        bank_reference: str,
    ) -> RenewalStatusResult:
        """
        Check the status of a previously initiated deposit renewal transaction.

        :param bank_reference: Bank transaction reference number.
        :return: RenewalStatusResult with confirmed/pending/rejected outcome.
        """
        pass

    def initiate_renewal(
        self,
        fdr_number: str,
        institution_reference: str,
        renewal_params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Initiate a deposit renewal transaction in the participating bank CBS.
        NOTE: Prototype and mock adapters do not initiate transactions. Real adapters
        must implement strict 2FA, CBS authorization tokens, and mutual TLS.
        """
        raise NotImplementedError(
            f"Provider '{self.name}' does not support automated renewal initiation. "
            "A formal bilateral integration agreement, RBI CBS connectivity adapter, "
            "and authorized digital signature credentials are required."
        )
