# AICTE FDR Portal — Core Banking Integration Layer Specification

> **PROTOTYPE INTEGRATION NOTICE:**  
> This integration layer is an architectural prototype developed for the Smart India Hackathon (SIH) demonstration and evaluation. It operates by default in **DEMO MODE** using `MockBankProvider` with synthetic, deterministic responses. No actual connection to a commercial bank or Reserve Bank of India (RBI) Core Banking System (CBS) currently exists. Mock responses must never be represented as legal evidence of deposit execution.

---

## 1. Architectural Overview

The Bank Integration Layer decouples the AICTE FDR Management Portal from vendor-specific Core Banking Systems (CBS) using the **Adapter & Factory Design Pattern**. 

```mermaid
flowchart TD
    subgraph PortalCore [AICTE FDR Portal Application]
        FDR[FDR Record / Lifecycle]
        Petition[Renewal & Lien Petitions]
        Audit[Immutable AuditLog]
        VLog[BankVerificationLog Table]
    end

    subgraph IntegrationLayer [Bank Integration Abstraction Layer]
        Factory[get_bank_provider Factory]
        Base[BankProvider Abstract Base Class]
    end

    subgraph Adapters [Provider Implementations]
        Mock[MockBankProvider (DEMO MODE - Default)]
        Real[Future Real Bank Adapter (Disabled/Staging)]
    end

    subgraph ExternalBank [Commercial Banking Core]
        CBS[(Core Banking CBS / SFMS / e-Lien API)]
    end

    FDR -->|Verify / Status Check| Factory
    Petition -->|Check Renewal Status| Factory
    Factory --> Base
    Base <|-- Mock
    Base <|-- Real
    Real -.->|mTLS + OAuth 2.0 (Future)| CBS

    Mock -->|Synthesizes Response| VLog
    VLog --> Audit
```

---

## 2. Bank Provider Interface (`BankProvider`)

All providers (simulated or real) must implement the `BankProvider` abstract contract defined in `app/services/bank_integration/base.py`:

```python
class BankProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def mode(self) -> ProviderMode: ...  # DEMO or REAL

    @property
    @abstractmethod
    def disclaimer(self) -> str: ...

    @abstractmethod
    def verify_fdr(
        self,
        fdr_number: str,
        institution_reference: str,
        expected_details: Optional[dict] = None,
        simulation_scenario: Optional[str] = None,
    ) -> VerificationResult: ...

    @abstractmethod
    def get_fdr_details(
        self,
        fdr_number: str,
        institution_reference: str,
    ) -> dict: ...

    @abstractmethod
    def get_renewal_status(
        self,
        bank_reference: str,
    ) -> RenewalStatusResult: ...

    def initiate_renewal(
        self,
        fdr_number: str,
        institution_reference: str,
        renewal_params: dict,
    ) -> dict: ...
```

---

## 3. Mock Provider (`MockBankProvider`) Specification

The mock provider provides reliable, deterministic behavior for automated regression testing and live jury demonstrations.

### Deterministic Test Matrix

| Test Scenario | Trigger via FDR Number Pattern | Trigger via API `scenario` Parameter | Returned Status | Behavior / Payload |
| :--- | :--- | :--- | :--- | :--- |
| **FDR Matched** | `FDR-SBI-...` (standard) | `"MATCHED"` | `MATCHED` | All fields (principal, maturity date, bank name, joint lien) match portal record. Generates bank reference `MOCK-CBS-REF-XXXX`. |
| **Parameter Mismatch** | Contains `MISMATCH`, `DIFF`, `TAMPER` | `"MISMATCH"` | `MISMATCH` | Generates deliberate discrepancy: principal reduced by ₹2,50,000 and maturity date 60 days earlier in bank CBS. Highlights field differences. |
| **Account Not Found** | Contains `NOTFOUND`, `MISSING`, `404` | `"NOT_FOUND"` | `NOT_FOUND` | Simulates account absent from CBS repository. |
| **Gateway Timeout** | Contains `TIMEOUT`, `UNAVAIL`, `DOWN` | `"UNAVAILABLE"` | `UNAVAILABLE` | Simulates 10-second CBS branch connection timeout or scheduled maintenance window. |
| **Renewal Confirmed** | Reference contains `CONFIRM` | Default renewal | `CONFIRMED` | Simulates bank confirmation of a 36-month deposit term extension with new maturity date. |
| **Renewal Pending** | Reference contains `PENDING` | — | `PENDING` | Simulates branch processing queue. |
| **Renewal Rejected** | Reference contains `REJECT` | — | `REJECTED` | Simulates branch rejection due to missing joint lien mandate. |

---

## 4. Safety & Core Data Protection Rules

1. **Decoupling of Petitions from Banking Reality:**
   - AICTE approval of a renewal petition is an administrative clearance under APH regulations; it **does not** constitute confirmation that the commercial bank has rolled over the deposit.
   - An approved petition remains in `Approved — Awaiting Renewed Deposit Receipt` until verified.
2. **Immutability of Official Records:**
   - Under no circumstances does a simulated/mock bank response alter the official `FDRRecord` parameters (`fdr_number`, `amount`, `issue_date`, `maturity_date`).
   - Official deposit parameters are only modified upon authorized officer endorsement of the verified bank receipt or via an authorized live CBS webhook signed with verified certificates.
3. **Manual Fallback Preservation:**
   - The manual receipt upload and desk scrutiny workflow remains the primary, authoritative mechanism.
   - Bank verification serves as an auxiliary decision-support tool.

---

## 5. Security & Access Control

1. **Credential Isolation:**
   - All bank credentials (`BANK_CLIENT_ID`, `BANK_CLIENT_SECRET`, `BANK_API_URL`, `BANK_CERT_PATH`) remain strictly on the backend inside environment variables.
   - No bank secrets are serialized or exposed to the frontend React bundle.
2. **Tenant Isolation:**
   - Institution users can only trigger verification or view bank logs for FDRs owned by their own institution code.
   - Cross-institution queries are rejected with `403 Forbidden`.
   - AICTE Scrutiny Officers and Central Administrators have cross-institution oversight.
3. **Immutable Audit Trail:**
   - Every verification request is persisted in `bank_verification_logs` and simultaneously logged in `audit_logs` (`action="BANK_VERIFICATION_CHECK"`).

---

## 6. Real-Bank Integration Requirements (Production Readiness)

Connecting the AICTE portal to a participating commercial bank (e.g., State Bank of India, Punjab National Bank, Canara Bank, HDFC Bank) requires satisfying the following technical, legal, and operational prerequisites:

### A. Regulatory & Legal Clearance
1. **Tripartite Agreement / MoU:** Written Memorandum of Understanding executed between AICTE, the participating commercial bank, and the Ministry of Education.
2. **Statutory Authorization:** Explicit institutional mandate authorizing AICTE to query security deposit balances and place/maintain joint liens under Section 10 of the AICTE Act.
3. **DPDP Act 2023 Compliance:** Data Protection and Privacy adherence for institutional financial records.

### B. Core Banking System (CBS) Connectivity Architecture
1. **Host-to-Host (H2H) / Open Banking Gateway:** Direct connectivity to the bank's Corporate API Gateway (e.g., SBI Corporate e-Banking Gateway, NPCI Account Aggregator, or RBI SFMS).
2. **Transport Security:** Mutual Transport Layer Security (**mTLS**) using SHA-256 / RSA 4096-bit digital certificates issued by a recognized Certifying Authority (CA).
3. **IP Whitelisting & VPN:** Dedicated leased line or encrypted IPsec VPN tunnel between AICTE government data centers and the bank's Primary Data Center (PDC).

### C. Authentication & Token Management
1. **OAuth 2.0 with Mutual TLS (RFC 8705):** Token requests using `client_credentials` grant with certificate-bound access tokens.
2. **Request Payload Signing:** JSON Web Signature (JWS / RFC 7515) with detached signature headers (`X-Signature`) using AICTE's private key.
3. **Token Caching & Rotation:** In-memory caching with Redis and automatic token refresh prior to expiry.

### D. Supported Banking Operations
| API Operation | HTTP Method | Expected Payload | Bank CBS Action |
| :--- | :--- | :--- | :--- |
| `/v1/fdr/verify` | `POST` | `{ fdrNumber, ifsc, institutionPan }` | Verifies deposit existence, balance, and joint lien flag. |
| `/v1/fdr/details` | `GET` | Query params: `fdrNumber` | Retrieves interest accrued, auto-renewal flag, and maturity date. |
| `/v1/fdr/lien-status` | `GET` | Query params: `fdrNumber` | Confirms AICTE is designated as primary joint lien holder. |
| `/v1/fdr/renewal-status` | `POST` | `{ bankReference, fdrNumber }` | Queries execution status of branch renewal mandate. |
| `/v1/fdr/webhook` | `POST` | Signed webhook notification | Pushes asynchronous updates when an FDR is renewed or lien is altered. |

### E. Sandbox to Production Phased Rollout
1. **Stage 1 (Mock / Prototype - Current):** In-portal simulation and interface validation.
2. **Stage 2 (Bank Sandbox):** Integration with bank sandbox using synthetic test accounts and mock CBS stubs.
3. **Stage 3 (User Acceptance Testing - UAT):** Dual-run testing with selected pilot technical institutions.
4. **Stage 4 (Production Approval):** Final security audit (CERT-In certified auditor), RBI advisory compliance, and formal production signoff.
