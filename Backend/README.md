# AICTE Security Deposit / FDR Management Portal - Backend

A modular, production-ready Flask backend for managing institution Fixed Deposit Receipts (FDRs) and security deposits under AICTE approval processes (Smart India Hackathon).

---

## 🏛️ Project Overview

The portal automates and manages:
- Institution-wise Fixed Deposit Receipt (FDR) submission & lifecycle tracking.
- Document verification and OCR ingestion.
- Discrepancy detection (mismatch in institution name, joint account clauses, tenure, maturity value).
- Maturity monitoring, renewal tracking, and AICTE lien release workflows.
- Role-based officer dashboards, notifications, and immutable audit logs.

---

## 📁 Project Structure

```
Backend/
├── app/
│   ├── __init__.py          # Flask application factory (create_app), CORS, CLI commands
│   ├── config.py            # Environment-based configuration (Dev, Test, Prod)
│   ├── extensions.py        # Shared extensions (SQLAlchemy, CORS)
│   ├── security.py          # Session auth, CSRF validation, RBAC decorators
│   ├── models/              # Database models
│   │   ├── enums.py         # Status, role, and notification enums
│   │   ├── institution.py   # Institution model
│   │   ├── user.py          # User model with Werkzeug password hashing
│   │   ├── fdr.py           # FDRRecord model
│   │   ├── document.py      # Supporting Document model
│   │   ├── audit.py         # Immutable AuditLog model
│   │   └── notification.py  # User Notification model
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py        # Health check blueprint (/api/health)
│   │   └── auth.py          # Authentication blueprint (/api/auth)
│   └── services/            # Core business logic & workflows
├── instance/                # Local SQLite storage (git-ignored)
│   └── .gitkeep
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures (app, client, runner)
│   ├── test_health.py       # Health check tests
│   ├── test_models.py       # Database schema and validation tests
│   └── test_auth.py         # Authentication, CSRF, and RBAC tests
├── .env.example             # Template for local environment variables
├── .gitignore               # Ignored files, secrets, virtualenvs, sqlite databases
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Project dependencies
├── run.py                   # Application entry point
└── README.md                # Setup and documentation
```

---

## 🛠️ Prerequisites

- **Python 3.10+** (Tested on Python 3.13 on Windows)
- **Windows PowerShell** or **Command Prompt**

---

## 🚀 Setup Instructions (Windows)

### 1. Open Terminal in the Backend Folder
```powershell
cd "c:\Users\arsh patil\OneDrive\Desktop\Backend"
```

### 2. Create a Virtual Environment (Recommended)
```powershell
python -m venv .venv
```

### 3. Activate the Virtual Environment
- **In PowerShell:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  *(If execution policies restrict script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

- **In Command Prompt (CMD):**
  ```cmd
  .\.venv\Scripts\activate.bat
  ```

### 4. Install Dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **Note for Windows users**: If Windows Application Control / AppLocker blocks direct execution of `pip.exe`, always invoke pip via the Python module runner: `python -m pip install -r requirements.txt`.

### 5. Configure Environment Variables
Copy `.env.example` to create your local `.env`:
```powershell
Copy-Item .env.example .env
```
Default parameters in `.env`:
- `FLASK_ENV=development`
- `FLASK_DEBUG=True`
- `PORT=5000`
- `HOST=127.0.0.1`
- `SECRET_KEY=dev-aicte-portal-secret-key-change-in-prod`
- `DATABASE_URL=sqlite:///aicte_fdr.db` (Stored inside `instance/aicte_fdr.db`)
- `CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`

### 6. Initialize Database Tables
Create database tables safely (will not overwrite or drop existing records):
```powershell
flask init-db
```

### 7. Provision the Initial Administrator Account
Public registration for privileged accounts is disabled by design. Provision the initial system administrator account interactively:
```powershell
flask create-admin
```
The command will prompt for:
- **Admin Email**: e.g., `admin@aicte.gov.in`
- **Full Name**: e.g., `System Administrator`
- **Password**: Secure password (hidden prompt with confirmation, minimum 8 characters)

---

## 🧪 Running Automated Tests

Run all unit tests using pytest:
```powershell
python -m pytest -q
```

All 46 tests across health, models, authentication, CSRF, FDR management, and document OCR will execute and pass:
```
tests/test_auth.py ...........
tests/test_document_ocr.py .........
tests/test_fdr.py ..............
tests/test_health.py ..
tests/test_models.py ..........
46 passed in 29.40s
```

---

## 🌐 Running the Flask Development Server

Start the application with:
```powershell
python run.py
```

Console output:
```
-> Starting AICTE Security Deposit / FDR Management Portal
-> Environment : development
-> Server URL  : http://127.0.0.1:5000
-> Health check: http://127.0.0.1:5000/api/health
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

---

## 🔐 Authentication & Role-Based Access Control (RBAC)

The backend uses server-side, cookie-based session authentication (`HttpOnly` session cookie) protected against session fixation, brute-force enumeration, and cross-site request forgery (CSRF).

### Role Categories
- **`INSTITUTION`** (or `INSTITUTION_USER`): Staff representing an educational institution. Must be linked to a valid institution.
- **`AICTE_OFFICER`**: AICTE verification officers responsible for reviewing FDR submissions.
- **`ADMIN`** (or `SYSTEM_ADMIN`): Full portal administrators.

### API Endpoints Under `/api/auth`

#### 1. Login: `POST /api/auth/login`
- **Body**:
  ```json
  {
    "email": "admin@aicte.gov.in",
    "password": "YourSecurePassword"
  }
  ```
- **Success Response (200 OK)**:
  ```json
  {
    "message": "Login successful.",
    "user": {
      "id": 1,
      "full_name": "System Administrator",
      "email": "admin@aicte.gov.in",
      "role": "ADMIN",
      "role_category": "ADMIN",
      "institution_id": null,
      "institution_name": null,
      "is_active": true,
      "created_at": "2026-10-26T12:00:00Z"
    },
    "csrf_token": "4a7f9b8c..."
  }
  ```
- **Cookies Set**:
  - `aicte_session` (`HttpOnly`, `SameSite=Lax`, `Secure` in production)
  - `csrf_token` (Accessible to JavaScript for Axios integration)

#### 2. Get Current User: `GET /api/auth/me`
- Requires active authenticated session.
- **Success Response (200 OK)**:
  ```json
  {
    "user": {
      "id": 1,
      "full_name": "System Administrator",
      "email": "admin@aicte.gov.in",
      "role": "ADMIN",
      "role_category": "ADMIN",
      "institution_id": null,
      "institution_name": null,
      "is_active": true,
      "created_at": "2026-10-26T12:00:00Z"
    },
    "csrf_token": "4a7f9b8c..."
  }
  ```
- **Unauthenticated Response**: `401 Unauthorized` (`{"code": "UNAUTHENTICATED"}`)

#### 3. Logout: `POST /api/auth/logout`
- Requires authenticated session and valid `X-CSRF-Token` header.
- Invalidation response: `200 OK` (`{"message": "Logged out successfully."}`)

#### 4. CSRF Token: `GET /api/auth/csrf-token`
- Returns current session synchronizer token: `{"csrf_token": "..."}`

---

## 💻 Frontend (React) Integration Notes

### 1. Axios Configuration with Credentials
In the React application, configure Axios to send and receive session cookies automatically:

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:5000/api',
  withCredentials: true, // CRITICAL: Sends session cookie with every cross-origin request
  headers: {
    'Content-Type': 'application/json',
  },
});
```

### 2. Handling CSRF Tokens
For all state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`), the backend requires the synchronizer token in the `X-CSRF-Token` header.

Add an Axios request interceptor:
```javascript
let currentCsrfToken = null;

export const setCsrfToken = (token) => {
  currentCsrfToken = token;
};

api.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    // Priority: stored memory token, or read from document cookie
    const token = currentCsrfToken || getCookie('csrf_token');
    if (token) {
      config.headers['X-CSRF-Token'] = token;
    }
  }
  return config;
});

// Helper to extract cookie value
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}
```

### 3. Login Flow Example in React
```javascript
async function login(email, password) {
  const response = await api.post('/auth/login', { email, password });
  // Store returned CSRF token for subsequent mutating requests
  setCsrfToken(response.data.csrf_token);
  return response.data.user;
}
```

### 4. Local CORS Settings
The backend allows credentials from React development hosts defined in `CORS_ALLOWED_ORIGINS` (default: `http://localhost:3000,http://127.0.0.1:3000`). If React runs on a different port (e.g. `5173` for Vite), update `.env`:
```
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## 📑 Fixed Deposit Receipt (FDR) Management APIs (`/api/fdr`)

All FDR endpoints require an active, authenticated session cookie (`aicte_session`). State-changing requests (`POST`, `PATCH`) also require the CSRF token in the `X-CSRF-Token` header.

### 1. Data Isolation & Authorization Rules
- **Institution Users**:
  - Automatically bound to their registered institution. The backend never trusts a client-supplied `institution_id`.
  - Can only create, view, search, and update FDRs belonging to their own institution.
  - Attempting to view or update another institution's FDR returns **HTTP 404** (preventing record existence enumeration).
  - Can only edit records in `DRAFT` or `RETURNED` status.
  - Cannot transition records to officer-controlled scrutiny statuses (`VERIFIED`, `REJECTED`, `PENDING_VERIFICATION`).
- **AICTE Officers & Administrators**:
  - Can view, filter, and paginate records across all institutions or filter by specific `institution_id`.
  - Can update scrutiny status (`VERIFIED`, `REJECTED`, `RETURNED`, `PENDING_VERIFICATION`, `SUBMITTED`, `DRAFT`) and validity status (`ACTIVE`, `EXPIRING_SOON`, `MATURED`, `OVERDUE_ACTION`).

---

### 2. Endpoints Contract & Examples

#### A. Create an FDR: `POST /api/fdr`
- **Headers**: `X-CSRF-Token: <token>`
- **Request Body**:
  ```json
  {
    "fdr_number": "SBI-FDR-2025-001",
    "bank_name": "State Bank of India",
    "branch_name": "Connaught Place, New Delhi",
    "amount": "1500000.00",
    "issue_date": "2025-01-15",
    "maturity_date": "2030-01-15"
  }
  ```
  *(Officers/Admins must also provide `"institution_id": 1`)*
- **Success Response (`201 Created`)**:
  ```json
  {
    "success": true,
    "message": "FDR record created successfully.",
    "data": {
      "id": 1,
      "institution_id": 1,
      "institution_name": "Alpha Engineering Institute",
      "fdr_number": "SBI-FDR-2025-001",
      "bank_name": "State Bank of India",
      "branch_name": "Connaught Place, New Delhi",
      "amount": "1500000.00",
      "issue_date": "2025-01-15",
      "maturity_date": "2030-01-15",
      "scrutiny_status": "DRAFT",
      "validity_status": "ACTIVE",
      "created_by": 2,
      "creator_name": "Registrar Alpha",
      "created_at": "2026-10-26T12:00:00Z",
      "updated_at": "2026-10-26T12:00:00Z"
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request` (`VALIDATION_ERROR`): Missing required fields, non-positive amount, booleans, or `maturity_date < issue_date`.
  - `409 Conflict` (`DUPLICATE_FDR_NUMBER`): FDR number already exists for this institution.

#### B. List FDR Records: `GET /api/fdr`
- **Supported Query Parameters**:
  - `page`: Page number (default: `1`)
  - `per_page`: Records per page (default: `10`, max: `100`)
  - `institution_id`: Filter by institution (Officers/Admins only)
  - `bank_name`: Substring match on bank name
  - `scrutiny_status`: Filter by status (`DRAFT`, `SUBMITTED`, `PENDING_VERIFICATION`, `VERIFIED`, `RETURNED`, `REJECTED`)
  - `validity_status`: Filter by validity (`ACTIVE`, `EXPIRING_SOON`, `MATURED`, `OVERDUE_ACTION`)
  - `maturity_from`: Filter FDRs maturing on or after `YYYY-MM-DD`
  - `maturity_to`: Filter FDRs maturing on or before `YYYY-MM-DD`
  - `search`: Case-insensitive text search across `fdr_number`, `bank_name`, and `branch_name`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": 1,
        "institution_id": 1,
        "institution_name": "Alpha Engineering Institute",
        "fdr_number": "SBI-FDR-2025-001",
        "bank_name": "State Bank of India",
        "branch_name": "Connaught Place, New Delhi",
        "amount": "1500000.00",
        "issue_date": "2025-01-15",
        "maturity_date": "2030-01-15",
        "scrutiny_status": "DRAFT",
        "validity_status": "ACTIVE",
        "created_by": 2,
        "creator_name": "Registrar Alpha",
        "created_at": "2026-10-26T12:00:00Z",
        "updated_at": "2026-10-26T12:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total": 1,
      "pages": 1
    }
  }
  ```

#### C. Get Single FDR: `GET /api/fdr/<int:fdr_id>`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": { ...fdr_record... }
  }
  ```
- **Error Response**: `404 Not Found` if record does not exist or belongs to another institution.

#### D. Update FDR: `PATCH /api/fdr/<int:fdr_id>`
- **Headers**: `X-CSRF-Token: <token>`
- **Permitted Fields for Institutions** (only while in `DRAFT` or `RETURNED` status):
  - `fdr_number`, `bank_name`, `branch_name`, `amount`, `issue_date`, `maturity_date`, `scrutiny_status` (may submit with `"SUBMITTED"`).
- **Request Body Example**:
  ```json
  {
    "branch_name": "New Branch Address",
    "amount": "1600000.00",
    "scrutiny_status": "SUBMITTED"
  }
  ```
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "FDR record updated successfully.",
    "data": { ...updated_fdr_record... }
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Field validation error or immutable field modification attempt (`institution_id`, `created_by`, `id`).
  - `403 Forbidden` (`RECORD_LOCKED`): Institution user attempting to edit record in `SUBMITTED`, `PENDING_VERIFICATION`, `VERIFIED`, or `REJECTED` status.
  - `403 Forbidden` (`OFFICER_STATUS_RESTRICTED`): Institution user attempting to set `VERIFIED` or `REJECTED`.
  - `404 Not Found`: Inaccessible or non-existent record.
  - `409 Conflict` (`DUPLICATE_FDR_NUMBER`): Changing FDR number to one already in use for the institution.

---

## 📄 Secure Document Upload, OCR, and Discrepancy Detection

### 1. Overview
The portal allows institutions to upload scanned receipts or digital PDFs of their Fixed Deposit Receipts. A local extraction pipeline extracts textual fields, detects discrepancies between the document and the registered FDR record, and flags records for manual review.

> **Important Compliance Note**: Automated OCR discrepancy detection is a preliminary validation tool. A `MATCH` outcome **does not prove authentic bank lien verification** or guarantee that a document is genuine. Genuine verification requires formal officer review and bank confirmation.

---

### 2. Supported Formats & Upload Specifications
- **Accepted MIME Types & Extensions**:
  - PDF: `.pdf` (`application/pdf`, magic signature: `%PDF-`)
  - PNG: `.png` (`image/png`, magic signature: `\x89PNG\r\n\x1a\n`)
  - JPEG: `.jpg`, `.jpeg` (`image/jpeg`, magic signature: `\xff\xd8\xff`)
- **Multipart Form Field**: `file`
- **Default Upload Size Limit**: 10 MB (`MAX_UPLOAD_SIZE_BYTES=10485760`)
- **Maximum PDF Pages Processed**: 20 pages (`MAX_PDF_PAGES=20`)
- **Storage**: Saved outside public static trees in `uploads/fdr_documents/` with randomized, collision-resistant filenames (`fdr_<id>_<token>.<ext>`). Path traversal and client-supplied paths are blocked.

---

### 3. Local OCR Engine & Tesseract Setup (Windows)

- **Digital PDFs**: PyMuPDF (`pymupdf`) extracts text directly from digital PDF streams with zero external dependencies.
- **Scanned Images / Scanned PDFs**: Image OCR uses Pillow and `pytesseract`.
- **Tesseract OCR on Windows**:
  1. Download the Windows installer from [UB-Mannheim Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
  2. Install to default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`.
  3. Ensure it is added to your Windows system `PATH`, or configure in `.env`:
     ```
     TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
     ```
  *(If Tesseract is not installed on the server, the application handles it gracefully: digital PDFs are still processed, and scanned images return status `FAILED` or a processing note indicating Tesseract setup instructions without crashing the server.)*

---

### 4. Document Endpoints

#### A. Upload Document & Run OCR: `POST /api/fdr/<int:fdr_id>/documents`
- **Headers**: `X-CSRF-Token: <token>`
- **Content-Type**: `multipart/form-data`
- **Body Form-Data**: `file: <binary_file>`
- **Success Response (`201 Created`)**:
  ```json
  {
    "success": true,
    "message": "Document uploaded and processed successfully.",
    "data": {
      "document": {
        "id": 1,
        "fdr_id": 1,
        "original_filename": "sbi_receipt.pdf",
        "stored_filename": "fdr_1_a3f8c12b9d0e.pdf",
        "file_type": "application/pdf",
        "file_size": 245760,
        "processing_status": "PROCESSED",
        "uploaded_by": 2,
        "uploaded_at": "2026-10-26T12:00:00Z"
      },
      "discrepancy_report": {
        "overall_result": "MATCH",
        "matched_fields": [
          {"field": "fdr_number", "registered": "FDR-ALPHA-001", "extracted": "FDR-ALPHA-001"},
          {"field": "bank_name", "registered": "State Bank of India", "extracted": "State Bank of India"},
          {"field": "amount", "registered": "500000.00", "extracted": "500000.00"},
          {"field": "maturity_date", "registered": "2030-01-01", "extracted": "2030-01-01"}
        ],
        "mismatched_fields": [],
        "missing_fields": [],
        "extracted_fields": {
          "fdr_number": "FDR-ALPHA-001",
          "bank_name": "State Bank of India",
          "branch_name": "Connaught Place, New Delhi",
          "amount": "500000.00",
          "issue_date": "2025-01-01",
          "maturity_date": "2030-01-01"
        },
        "disclaimer": "Automated OCR extraction and heuristic check only. Does not replace formal AICTE officer scrutiny or bank confirmation."
      }
    }
  }
  ```

#### B. List FDR Documents: `GET /api/fdr/<int:fdr_id>/documents`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": 1,
        "fdr_id": 1,
        "original_filename": "sbi_receipt.pdf",
        "stored_filename": "fdr_1_a3f8c12b9d0e.pdf",
        "file_type": "application/pdf",
        "file_size": 245760,
        "processing_status": "PROCESSED",
        "uploaded_by": 2,
        "uploaded_at": "2026-10-26T12:00:00Z"
      }
    ]
  }
  ```

#### C. Get Document Detail & Discrepancy Report: `GET /api/fdr/<int:fdr_id>/documents/<int:document_id>`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": {
      "document": { ...document_metadata... },
      "discrepancy_report": { ...discrepancy_report... }
    }
  }
  ```
- **Error Responses**:
  - `404 Not Found`: Inaccessible record or document does not belong to the FDR in the URL path.

---

## 🔔 Step 6: Maturity Tracking and Notification System

### 1. Maturity Classification Rules

FDR validity status is computed deterministically from the deposit's `maturity_date` relative to the current reference business date:

| Validity Status | Condition (Days Remaining = `maturity_date - ref_date`) | Description |
|---|---|---|
| `ACTIVE` | `days_remaining > 30` | Valid fixed deposit with more than 30 days before maturity. |
| `EXPIRING_SOON` | `1 <= days_remaining <= 30` | Within the reminder window; institution must prepare renewal or lien release. |
| `MATURED` | `0 >= days_remaining > -30` | Maturity date has arrived or passed, awaiting mandatory action. |
| `OVERDUE_ACTION` | `days_remaining <= -30` | FDR is at or beyond overdue threshold without approved renewal/release. |

> **Timezone Assumption**: All business dates default to UTC (`BUSINESS_TIMEZONE=UTC`), preventing date-shift discrepancies between regional timezones. Injected business dates can be passed to the scanner CLI or service functions for deterministic audits and tests.
>
> **Status Independence**: Updating `validity_status` **never** overwrites or alters an AICTE officer's `scrutiny_status` (`DRAFT`, `SUBMITTED`, `PENDING_VERIFICATION`, `VERIFIED`, `RETURNED`, `REJECTED`).

---

### 2. Reminder Intervals & Escalation Rules

Configurable via `REMINDER_INTERVAL_DAYS` in `.env` (default: `30,15,7,0`):
- **30 Days Remaining**: Warning notification sent to institution users.
- **15 Days Remaining**: Warning notification sent to institution users.
- **7 Days Remaining**: Urgent action-required notification sent to institution users **and escalated to active AICTE officers/admins**.
- **0 Days Remaining (Maturity Date)**: Critical alert sent to institution users **and AICTE officers/admins**.
- **Overdue Threshold (>= 30 Days Overdue)**: Overdue action alert sent to institution users and AICTE officers/admins.

#### Database-Backed Deduplication
- Each notification is keyed deterministically by `(user_id, title)`.
- Re-running the scanner multiple times on the same date or subsequent dates will **never** generate duplicate notifications for the same reminder event.
- System-generated execution metrics are automatically logged into `AuditLog` (`action="MATURITY_SCAN_COMPLETED"`).

---

### 3. Notification API Contracts

All notification endpoints require an active session (`@login_required`). State-changing requests require a valid CSRF token.
Cross-user isolation is enforced: a user can only access their own notifications.

#### A. List Notifications: `GET /api/notifications`
- **Query Parameters**:
  - `page` (optional integer, default `1`)
  - `per_page` (optional integer, default `20`, max `100`)
  - `unread_only` (optional boolean: `true`/`1` to filter only unread)
- **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "notifications": [
      {
        "id": 1,
        "user_id": 2,
        "title": "FDR Maturity Reminder: FDR-ALPHA-001 (30 Days Remaining)",
        "message": "Fixed Deposit Receipt FDR-ALPHA-001 of State Bank of India (INR 500000.00) will mature on 2026-11-26 (in 30 days).",
        "notification_type": "WARNING",
        "is_read": false,
        "created_at": "2026-10-26T12:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 1,
      "pages": 1,
      "has_next": false,
      "has_prev": false
    }
  }
  ```

#### B. Get Unread Count: `GET /api/notifications/unread-count`
- **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "unread_count": 1
  }
  ```

#### C. Mark One Notification as Read: `PATCH /api/notifications/<int:notification_id>/read`
- **Headers**: `X-CSRF-Token: <token>`
- **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "Notification marked as read.",
    "notification": {
      "id": 1,
      "is_read": true,
      ...
    }
  }
  ```
- **Error Responses**:
  - `404 Not Found`: Notification does not exist or belongs to another user.
  - `403 Forbidden`: Missing or invalid CSRF token.

#### D. Mark All Notifications as Read: `PATCH /api/notifications/read-all`
- **Headers**: `X-CSRF-Token: <token>`
- **Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "Successfully marked 4 notification(s) as read.",
    "marked_count": 4
  }
  ```

---

### 4. Scheduler & Manual CLI Scan

#### Running Manual Scan via CLI (Windows)
Trigger the maturity scan manually via the safe CLI command:
```powershell
# Run scan as of the current business date:
.\.venv\Scripts\python.exe -m flask scan-fdr-maturities

# Or run scan as of a specific business date (YYYY-MM-DD):
.\.venv\Scripts\python.exe -m flask scan-fdr-maturities --date 2026-11-01
```

#### APScheduler Background Runner
- Background scheduled jobs use `APScheduler` (`BackgroundScheduler`).
- **Safety controls**:
  - **Reloader Protection**: When running with Flask debug reloader (`run.py`), the scheduler only starts in the active child worker (`WERKZEUG_RUN_MAIN == "true"`), preventing duplicate scheduler instances.
  - **Test Environment Isolation**: The scheduler is strictly disabled during automated tests (`TESTING=True` or `SCHEDULER_ENABLED=False`).
  - **Graceful Shutdown**: Automatically registers `atexit` handlers to cleanly terminate threads upon server shutdown.
- **Production Multi-Worker Consideration**: In multi-process production deployments (e.g. Gunicorn / uWSGI with multiple workers), background cron schedulers should either run on a single designated worker or via an external orchestrator (e.g., systemd timer, cron job, or Celery beat) invoking the CLI command: `flask scan-fdr-maturities`.

---

### 5. Running Automated Tests

Run the full pytest suite (72 tests) without starting background threads:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## ⚖️ Step 7A: FDR Scrutiny Workflow Transitions

Step 7A formalizes the scrutiny lifecycle engine through a centralized transition validator and workflow service ([app/services/workflow_service.py](file:///c:/Users/arsh%20patil/OneDrive/Desktop/Backend/app/services/workflow_service.py)).

### 1. Allowed Scrutiny Transition Matrix

| Initial Status | Target Status | Authorized Roles | Remarks Required? | Workflow Semantics |
|---|---|---|:---:|---|
| `DRAFT` | `SUBMITTED` | `INSTITUTION`, `ADMIN` | No (Optional) | Institution user submits completed draft FDR for formal AICTE verification. |
| `RETURNED` | `SUBMITTED` | `INSTITUTION`, `ADMIN` | No (Optional) | Institution user resubmits corrected deposit receipt following officer return. |
| `SUBMITTED` | `PENDING_VERIFICATION` | `AICTE_OFFICER`, `ADMIN` | No (Optional) | AICTE scrutiny officer locks the deposit record into active review. |
| `PENDING_VERIFICATION` | `VERIFIED` | `AICTE_OFFICER`, `ADMIN` | Optional | Officer approves the FDR deposit and confirms bank lien validity. |
| `PENDING_VERIFICATION` | `RETURNED` | `AICTE_OFFICER`, `ADMIN` | **Yes (Mandatory)** | Officer returns deposit to institution for missing seals, blurry scans, or branch discrepancies. |
| `PENDING_VERIFICATION` | `REJECTED` | `AICTE_OFFICER`, `ADMIN` | **Yes (Mandatory)** | Officer rejects the FDR submission due to unresolvable defects or unauthorized encashment. |

### 2. Disallowed Transitions and Guardrails

- **Terminal States**: `VERIFIED` and `REJECTED` are final, terminal statuses. Once locked into a terminal status, no further workflow transitions are permitted.
- **Workflow Bypasses Rejected**: Direct jumps such as `DRAFT → VERIFIED`, `DRAFT → PENDING_VERIFICATION`, or `SUBMITTED → VERIFIED` are strictly prohibited. Records must be placed into `PENDING_VERIFICATION` before any officer decision can be rendered.
- **No Self-Transitions**: Transitions from a status to itself (e.g., `DRAFT → DRAFT`) are rejected as redundant no-ops.
- **Validity Status Separation**: Scrutiny workflow transitions strictly operate on `scrutiny_status`. Deposit maturity scanning and `validity_status` (`ACTIVE`, `EXPIRING_SOON`, `MATURED`, `OVERDUE_ACTION`) operate completely independently.

### 3. Role Permissions

- **Institution Users**:
  - May submit their own institution's `DRAFT` or `RETURNED` FDRs (`DRAFT → SUBMITTED`, `RETURNED → SUBMITTED`).
  - Strict multi-tenant data isolation: Attempting to access or transition another institution's FDR returns `404 Not Found`.
  - Prohibited from self-verifying, taking up scrutiny, returning, or rejecting any record.
- **AICTE Officers**:
  - May move `SUBMITTED` records into `PENDING_VERIFICATION`.
  - May render decisions: `PENDING_VERIFICATION → VERIFIED`, `RETURNED`, or `REJECTED`.
  - Prohibited from submitting deposits on behalf of institutions (`DRAFT → SUBMITTED`).
- **Portal Administrators**:
  - Hold supervisory permissions across the valid transition matrix but are bound to the same transition integrity rules.

### 4. Decision Remarks Validation

- **Mandatory on `RETURNED` and `REJECTED`**: Officers must provide clear, actionable reasons explaining why a submission was returned or rejected.
- **Sanitization & Length Limits**: Remarks are trimmed of leading/trailing whitespace. A strict maximum limit of **2,000 characters** is enforced (`MAX_REMARKS_LENGTH = 2000`).
- **Consistent Error Structure**: Submitting empty, whitespace-only, or overly long remarks returns a `400 Bad Request` with `code="VALIDATION_ERROR"` and detailed field diagnostics: `{"details": {"remarks": "..."}}`.

### 5. Audit Logging & Real-Time Notifications

- **Structured Audit Logging**: Every transition logs an immutable entry in `AuditLog` (`action="SCRUTINY_TRANSITION_<FROM>_TO_<TO>"`), detailing:
  - `previous_status` and `new_status`
  - `actor_id`, `actor_email`, and `actor_role`
  - Cleaned decision `remarks`
  - UTC ISO timestamp
- **Automatic Institution Notifications**:
  - When an officer takes up scrutiny (`PENDING_VERIFICATION`), the institution receives an informative `FDR Under Scrutiny` notification.
  - When an officer approves (`VERIFIED`), the institution receives an approval confirmation notification.
  - When an officer returns a deposit (`RETURNED`), institution users receive an `ACTION_REQUIRED` notification including the officer's exact feedback.
  - When rejected (`REJECTED`), an `ALERT` notification is delivered.
- **Transaction Safety**: Status updates, audit records, and notification generation are executed within a single database transaction. If any component encounters an exception, the entire transaction is rolled back via `db.session.rollback()`.

### 6. Schema Limitation Analysis & Proposed Minimal Migration

- **Current Limitation**: The existing `fdr_records` table only stores the single scalar `scrutiny_status` and `updated_at`. While `AuditLog` captures historical actions in unstructured JSON `details`, querying full decision history, officer notes, and review timelines across millions of records requires scanning text blobs without foreign key guarantees.
- **Proposed Minimal Migration (for Step 8 / future workflow history endpoint)**:
  ```sql
  CREATE TABLE fdr_workflow_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      fdr_id INTEGER NOT NULL REFERENCES fdr_records(id) ON DELETE CASCADE,
      from_status VARCHAR(32) NOT NULL,
      to_status VARCHAR(32) NOT NULL,
      actor_id INTEGER NOT NULL REFERENCES users(id),
      remarks TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX idx_fdr_workflow_history_fdr_id ON fdr_workflow_history(fdr_id);
  ```

---

## 🚀 Step 7B: FDR Scrutiny Workflow REST APIs

Step 7B exposes the scrutiny lifecycle engine through authenticated, CSRF-protected REST endpoints under the `/api/fdr` blueprint.

### 1. Endpoint Summary & Permission Matrix

| HTTP Method | Endpoint | Required Role | State Transition | Description |
|---|---|---|---|---|
| `POST` | `/api/fdr/<id>/submit` | `INSTITUTION`, `ADMIN` | `DRAFT` / `RETURNED` → `SUBMITTED` | Submits draft FDR or resubmits returned FDR for verification. |
| `POST` | `/api/fdr/<id>/start-review` | `AICTE_OFFICER`, `ADMIN` | `SUBMITTED` → `PENDING_VERIFICATION` | Officer locks submitted deposit into active verification. |
| `POST` | `/api/fdr/<id>/verify` | `AICTE_OFFICER`, `ADMIN` | `PENDING_VERIFICATION` → `VERIFIED` | Officer approves deposit and confirms bank lien validity. |
| `POST` | `/api/fdr/<id>/return` | `AICTE_OFFICER`, `ADMIN` | `PENDING_VERIFICATION` → `RETURNED` | Officer returns deposit with mandatory rectification reason. |
| `POST` | `/api/fdr/<id>/reject` | `AICTE_OFFICER`, `ADMIN` | `PENDING_VERIFICATION` → `REJECTED` | Officer rejects submission with mandatory rejection reason. |
| `GET` | `/api/fdr/<id>/workflow` | Authenticated | *None (Read-only)* | Returns current scrutiny/validity status, available actions, and decision history. |

---

### 2. Endpoint Contracts & Examples

#### A. Submit / Resubmit FDR: `POST /api/fdr/<int:fdr_id>/submit`
- **Headers**: `X-CSRF-Token: <token>`
- **Request Body** (optional JSON):
  ```json
  {
    "remarks": "Submitting updated FDR with official bank seal."
  }
  ```
- **Submission Requirements**:
  - Valid FDR record fields (`fdr_number`, `bank_name`, `branch_name`, positive `amount`, valid dates).
  - **At least one supporting document uploaded** (e.g. via `POST /api/fdr/<id>/documents`).
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "FDR submitted successfully for AICTE verification.",
    "data": {
      "id": 1,
      "fdr_number": "FDR-ALPHA-001",
      "scrutiny_status": "SUBMITTED",
      "validity_status": "ACTIVE",
      ...
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request` (`VALIDATION_ERROR`): Missing supporting document (`{"details": {"documents": "..."}}`).
  - `400 Bad Request` (`INVALID_TRANSITION`): FDR is not in `DRAFT` or `RETURNED` status.
  - `403 Forbidden` (`WORKFLOW_ROLE_RESTRICTED`): User is an officer or lacks institution submission permission.
  - `404 Not Found`: Inaccessible record or cross-institution access.

#### B. Start Officer Review: `POST /api/fdr/<int:fdr_id>/start-review`
- **Headers**: `X-CSRF-Token: <token>`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "FDR review initiated successfully.",
    "data": {
      "id": 1,
      "scrutiny_status": "PENDING_VERIFICATION",
      ...
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request` (`INVALID_TRANSITION`): FDR is not in `SUBMITTED` status.
  - `403 Forbidden`: Institution user attempting officer actions.

#### C. Verify FDR: `POST /api/fdr/<int:fdr_id>/verify`
- **Headers**: `X-CSRF-Token: <token>`
- **Request Body** (optional JSON):
  ```json
  {
    "remarks": "Lien verified with SBI branch manager. Approved."
  }
  ```
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "FDR verified and approved successfully.",
    "data": {
      "id": 1,
      "scrutiny_status": "VERIFIED",
      ...
    }
  }
  ```

#### D. Return for Correction: `POST /api/fdr/<int:fdr_id>/return`
- **Headers**: `X-CSRF-Token: <token>`
- **Request Body** (mandatory JSON):
  ```json
  {
    "reason": "Branch seal is missing from page 1. Please re-upload verified scan."
  }
  ```
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "FDR returned to institution for correction.",
    "reason": "Branch seal is missing from page 1. Please re-upload verified scan.",
    "scrutiny_status": "RETURNED",
    "data": {
      "id": 1,
      "scrutiny_status": "RETURNED",
      ...
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request` (`VALIDATION_ERROR`): Missing, whitespace-only, or oversized (> 2000 chars) reason.

#### E. Reject FDR: `POST /api/fdr/<int:fdr_id>/reject`
- **Headers**: `X-CSRF-Token: <token>`
- **Request Body** (mandatory JSON):
  ```json
  {
    "reason": "Deposit was encashed by institution prior to verification without AICTE NOC."
  }
  ```
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "message": "FDR submission rejected.",
    "reason": "Deposit was encashed by institution prior to verification without AICTE NOC.",
    "scrutiny_status": "REJECTED",
    "data": {
      "id": 1,
      "scrutiny_status": "REJECTED",
      ...
    }
  }
  ```

#### F. Get Workflow State & History: `GET /api/fdr/<int:fdr_id>/workflow`
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": {
      "fdr_id": 1,
      "fdr_number": "FDR-ALPHA-001",
      "scrutiny_status": "PENDING_VERIFICATION",
      "validity_status": "ACTIVE",
      "is_authorized": true,
      "available_actions": ["verify", "return", "reject"],
      "workflow_history": [
        {
          "id": 4,
          "action": "SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED",
          "previous_status": "DRAFT",
          "new_status": "SUBMITTED",
          "actor_role": "INSTITUTION",
          "actor_email": "registrar@alpha.edu",
          "remarks": "Initial submission",
          "timestamp": "2026-10-26T12:00:00Z"
        },
        {
          "id": 5,
          "action": "SCRUTINY_TRANSITION_SUBMITTED_TO_PENDING_VERIFICATION",
          "previous_status": "SUBMITTED",
          "new_status": "PENDING_VERIFICATION",
          "actor_role": "AICTE_OFFICER",
          "actor_email": "officer@aicte.gov.in",
          "remarks": null,
          "timestamp": "2026-10-26T12:15:00Z"
        }
      ]
    }
  }
  ```

---

### 3. Running Automated Tests

Run the full pytest suite (111 tests across all modules) without background jobs:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```



---

## 📜 Step 7C: Structured Workflow History & Deficiency Tracking

Step 7C replaces unstructured JSON audit scanning with a dedicated relational history model (`FDRWorkflowHistory`), tracking every scrutiny decision and deficiency notice with strict database integrity.

### 1. `FDRWorkflowHistory` Model Schema

| Column | Type | Constraints / Indexes | Description |
|---|---|---|---|
| `id` | `Integer` | `PRIMARY KEY AUTOINCREMENT` | Unique history record identifier. |
| `fdr_id` | `Integer` | `FOREIGN KEY (fdr_records.id) ON DELETE CASCADE`, indexed | Associated FDR record. |
| `from_status` | `String(32)` | `NOT NULL` | Previous scrutiny status. |
| `to_status` | `String(32)` | `NOT NULL` | New scrutiny status. |
| `actor_id` | `Integer` | `FOREIGN KEY (users.id) ON DELETE SET NULL`, indexed | User who performed the transition. |
| `remarks` | `Text` | `NULLABLE` | Officer decision notes, return reasons, or resubmission comments. |
| `is_deficiency` | `Boolean` | `NOT NULL DEFAULT FALSE`, indexed | Flagged `True` when transition outcome is `RETURNED`. |
| `resolution_status` | `String(32)` | `NULLABLE` (`"UNRESOLVED"` on return) | Current deficiency resolution state. |
| `created_at` | `DateTime(UTC)` | `NOT NULL DEFAULT UTC`, indexed | Timestamp when decision was executed. |

---

### 2. Deficiency Tracking & Resubmission Retention

1. **Deficiency Capture**: Every officer return decision (`PENDING_VERIFICATION → RETURNED`) stores the exact return reason in `remarks`, sets `is_deficiency=True`, and records `resolution_status="UNRESOLVED"`.
2. **Resubmission Preservation**: When an institution resubmits (`RETURNED → SUBMITTED`), a new history row is inserted for the resubmission event.
3. **No Automatic Resolution**: The previous deficiency record remains **permanently preserved** with its original remarks and `resolution_status="UNRESOLVED"`. Deficiencies are never automatically marked resolved merely because the deposit was resubmitted.
4. **Immutability**: Historical entries cannot be modified or deleted through ordinary API endpoints.

---

### 3. Updated Workflow State & History API

`GET /api/fdr/<int:fdr_id>/workflow`
- **Query Parameters (Optional Pagination)**:
  - `page` (integer, e.g. `1`)
  - `per_page` (integer, e.g. `10`, max `100`)
- **Success Response (`200 OK`)**:
  ```json
  {
    "success": true,
    "data": {
      "fdr_id": 1,
      "fdr_number": "FDR-ALPHA-001",
      "scrutiny_status": "RETURNED",
      "validity_status": "ACTIVE",
      "is_authorized": true,
      "available_actions": ["submit"],
      "workflow_history": [
        {
          "id": 1,
          "fdr_id": 1,
          "action": "SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED",
          "from_status": "DRAFT",
          "previous_status": "DRAFT",
          "to_status": "SUBMITTED",
          "new_status": "SUBMITTED",
          "actor_id": 2,
          "actor_name": "Registrar Alpha",
          "actor_role": "INSTITUTION",
          "actor_email": "registrar@alpha.edu",
          "remarks": "Initial submission",
          "is_deficiency": false,
          "resolution_status": null,
          "created_at": "2026-10-26T12:00:00Z",
          "timestamp": "2026-10-26T12:00:00Z"
        },
        {
          "id": 2,
          "fdr_id": 1,
          "action": "SCRUTINY_TRANSITION_PENDING_VERIFICATION_TO_RETURNED",
          "from_status": "PENDING_VERIFICATION",
          "previous_status": "PENDING_VERIFICATION",
          "to_status": "RETURNED",
          "new_status": "RETURNED",
          "actor_id": 3,
          "actor_name": "AICTE Officer",
          "actor_role": "AICTE_OFFICER",
          "actor_email": "officer@aicte.gov.in",
          "remarks": "Branch seal is missing from page 1.",
          "is_deficiency": true,
          "resolution_status": "UNRESOLVED",
          "created_at": "2026-10-26T12:15:00Z",
          "timestamp": "2026-10-26T12:15:00Z"
        }
      ],
      "deficiencies": [
        {
          "id": 2,
          "fdr_id": 1,
          "remarks": "Branch seal is missing from page 1.",
          "is_deficiency": true,
          "resolution_status": "UNRESOLVED",
          "created_at": "2026-10-26T12:15:00Z"
        }
      ],
      "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 2,
        "pages": 1,
        "has_next": false,
        "has_prev": false
      }
    }
  }
  ```

---

### 4. Database Migration Procedure & Backfilling

#### Safe Migration CLI Command (Windows)
```powershell
# Run safe migration with automatic AuditLog backfill:
.\.venv\Scripts\python.exe -m flask migrate-workflow-history

# Or run migration without backfilling legacy audit records:
.\.venv\Scripts\python.exe -m flask migrate-workflow-history --no-backfill
```

#### Migration Characteristics & Idempotency
- **Non-Destructive**: Uses `CREATE TABLE IF NOT EXISTS` and creates indexes without modifying or dropping existing tables.
- **Data Preservation**: Preserves all existing `fdr_records`, `documents`, `users`, and `audit_logs`.
- **Rerun Safety**: Checks if the table and records already exist. Running the command multiple times produces zero duplicates.
- **Backfill Capabilities**: Historical `AuditLog` records matching `SCRUTINY_TRANSITION_%` are parsed for `previous_status`, `new_status`, `actor_id`, and `remarks`.
- **Backfill Limitations**: If historical audit records were created with missing actor references or unparseable JSON payloads, they cannot be reliably reconstructed and are skipped to avoid corrupting relational history.

#### Production Backup Precautions
Before applying migrations in a production database:
1. Create a full database snapshot / cold backup:
   - For SQLite: Copy `instance/aicte_fdr.db` to a backup location (`instance/aicte_fdr.db.bak`).
   - For PostgreSQL: Execute `pg_dump -Fc $DATABASE_URL > pre_step7c_backup.dump`.
2. Verify application connectivity before starting worker threads.

---

## 💻 Step 7D: Frontend Integration Guide (React / Vite)

This section provides a complete, developer-ready guide for integrating modern React and Vite frontends with the Flask FDR backend.

### 1. Backend Server Setup & URLs

| Setting | Value / Example | Notes |
|---|---|---|
| **Backend Startup Command** | `.\.venv\Scripts\python.exe run.py` | Runs on `http://127.0.0.1:5000` |
| **Health Check Endpoint** | `http://127.0.0.1:5000/api/health` | Unauthenticated probe returning `{"status": "healthy"}` |
| **API Base URL** | `http://127.0.0.1:5000/api` | Base prefix for all authenticated API endpoints |
| **Frontend Development Origin** | `http://localhost:5173` (Vite) or `http://localhost:3000` (CRA) | Must be whitelisted in backend CORS configuration |

#### Starting the Development Server
```powershell
.\.venv\Scripts\python.exe run.py
```
To verify the backend is online:
```powershell
curl http://127.0.0.1:5000/api/health
```

---

### 2. CORS Configuration

The Flask backend is configured with `Flask-CORS` using `supports_credentials=True`.
In `.env` (or environment variables), set `CORS_ALLOWED_ORIGINS` to match your frontend dev and staging URLs:
```ini
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
```
> **Security Note**: When `supports_credentials=True`, wildcard origins (`*`) are disallowed by web browsers. You must specify exact origins.

---

### 3. Session-Cookie Authentication & CSRF Handling

The backend uses **HTTP-only session cookies** (`session`) and double-submit **CSRF protection tokens**.

#### How Authentication & CSRF Work in the Frontend:
1. **CSRF Token Acquisition**: Before issuing any state-mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`), the frontend requests a fresh CSRF token from `GET /api/auth/csrf-token`.
2. **Credential Transmission**: Every request must send `credentials: 'include'` (or Axios `withCredentials: true`) so the browser attaches the session cookie.
3. **CSRF Header**: The frontend must send the CSRF token in the `X-CSRF-Token` header for all mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`).
4. **Login**: `POST /api/auth/login` sets the authenticated session cookie on the browser.
5. **Session Check**: `GET /api/auth/me` verifies current authentication status and active role (`INSTITUTION`, `AICTE_OFFICER`, `ADMIN`).
6. **Logout**: `POST /api/auth/logout` invalidates the server session and clears client context.

---

### 4. Recommended Axios Configuration (React / Vite)

Create an API client module (e.g. `src/api/client.js` or `src/api/client.ts`) that automatically manages CSRF tokens and credentials:

```javascript
import axios from 'axios';

// 1. Create configured Axios instance
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000/api',
  withCredentials: true, // CRITICAL: Ensures browser sends session cookies
  headers: {
    'Accept': 'application/json',
  },
});

let csrfTokenCache = null;

// 2. Function to fetch or reuse CSRF token
export async function getCsrfToken(forceRefresh = false) {
  if (!csrfTokenCache || forceRefresh) {
    const response = await apiClient.get('/auth/csrf-token');
    csrfTokenCache = response.data.csrf_token;
  }
  return csrfTokenCache;
}

// 3. Request interceptor: Automatically attach X-CSRF-Token on mutating requests
apiClient.interceptors.request.use(async (config) => {
  const mutatingMethods = ['post', 'put', 'patch', 'delete'];
  if (mutatingMethods.includes(config.method?.toLowerCase() || '')) {
    const token = await getCsrfToken();
    if (token) {
      config.headers['X-CSRF-Token'] = token;
    }
  }
  return config;
}, (error) => Promise.reject(error));

// 4. Response interceptor: Handle expired session or CSRF errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      csrfTokenCache = null;
      // Redirect to login or dispatch auth state reset
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    } else if (error.response?.status === 403 && error.response?.data?.error === 'CSRF_ERROR') {
      // Refresh CSRF token and retry once if CSRF validation failed
      csrfTokenCache = null;
      const originalRequest = error.config;
      if (!originalRequest._retried) {
        originalRequest._retried = true;
        const newToken = await getCsrfToken(true);
        originalRequest.headers['X-CSRF-Token'] = newToken;
        return apiClient(originalRequest);
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

### 5. API Endpoints Reference

#### Authentication (`/api/auth`)
| Method | Endpoint | Description | Payload / Notes |
|---|---|---|---|
| `GET` | `/auth/csrf-token` | Obtain CSRF token | Returns `{"csrf_token": "..."}` |
| `POST` | `/auth/login` | Log in user | `{"email": "...", "password": "..."}` |
| `POST` | `/auth/logout` | Log out and destroy session | No payload required (`X-CSRF-Token` required) |
| `GET` | `/auth/me` | Fetch active user profile and role | Returns `{id, email, full_name, role, institution_id}` |

#### FDR Management & Document Upload (`/api/fdr`)
| Method | Endpoint | Description | Payload / Notes |
|---|---|---|---|
| `POST` | `/fdr` | Create draft FDR record | `{"fdr_number": "...", "bank_name": "...", "branch_name": "...", "ifsc_code": "...", "account_number": "...", "deposit_amount": 500000.0, "start_date": "2024-01-01", "maturity_date": "2029-01-01", "joint_account_clause": true}` |
| `GET` | `/fdr` | List authorized FDR records | Query params: `page`, `per_page`, `scrutiny_status`, `validity_status`, `bank_name`, `search` |
| `GET` | `/fdr/<id>` | Retrieve single FDR with documents | Returns full FDR details and associated files |
| `PATCH` | `/fdr/<id>` | Update draft or returned FDR | Only modifiable in `DRAFT` or `RETURNED` status |
| `POST` | `/fdr/<id>/documents` | Upload PDF or image document | `multipart/form-data` with `file` field. Performs automatic local OCR extraction |
| `GET` | `/fdr/<id>/documents/<doc_id>` | Download document securely | Returns binary stream (`Content-Disposition: attachment`). Public static access is disabled |

#### FDR Scrutiny Workflow Endpoints (`/api/fdr/<id>/*`)
| Method | Endpoint | Allowed Roles | Valid From Status | New Status | Description / Payload |
|---|---|---|---|---|---|
| `POST` | `/fdr/<id>/submit` | `INSTITUTION` | `DRAFT`, `RETURNED` | `SUBMITTED` | Submit initial deposit or resubmit returned deposit. Optional: `{"remarks": "Resubmitting with updated seal"}` |
| `POST` | `/fdr/<id>/start-review` | `AICTE_OFFICER`, `ADMIN` | `SUBMITTED` | `PENDING_VERIFICATION` | Lock deposit for review. No payload required |
| `POST` | `/fdr/<id>/verify` | `AICTE_OFFICER`, `ADMIN` | `PENDING_VERIFICATION` | `VERIFIED` | Approve FDR. Terminal verification. Optional: `{"remarks": "All documents verified"}` |
| `POST` | `/fdr/<id>/return` | `AICTE_OFFICER`, `ADMIN` | `PENDING_VERIFICATION` | `RETURNED` | Return deposit with deficiency notice. **Mandatory**: `{"remarks": "Branch seal missing"}` (min 5 chars) |
| `POST` | `/fdr/<id>/reject` | `AICTE_OFFICER`, `ADMIN` | `PENDING_VERIFICATION` | `REJECTED` | Final rejection. Terminal state. **Mandatory**: `{"remarks": "Fraudulent document"}` (min 5 chars) |
| `GET` | `/fdr/<id>/workflow` | `INSTITUTION`, `AICTE_OFFICER`, `ADMIN` | Any | — | Returns current status, available actions, structured timeline, and deficiency list |

#### Notifications (`/api/notifications`)
| Method | Endpoint | Description | Payload / Notes |
|---|---|---|---|
| `GET` | `/notifications` | List user's notifications | Query params: `unread_only=true`, `page=1`, `per_page=20` |
| `GET` | `/notifications/unread-count` | Unread notifications badge count | Returns `{"unread_count": 3}` |
| `PATCH` | `/notifications/<id>/read` | Mark single notification as read | Sets `is_read=true` (`X-CSRF-Token` required) |
| `POST` | `/notifications/mark-all-read` | Mark all user notifications as read | Marks all unread items (`X-CSRF-Token` required) |

---

### 6. Workflow History and Deficiency Response Format

When querying `GET /api/fdr/<id>/workflow`, the frontend receives a unified payload detailing allowed actions, chronologically ordered history events, and active deficiency notices:

```json
{
  "success": true,
  "data": {
    "fdr_id": 101,
    "fdr_number": "FDR-2026-9901",
    "scrutiny_status": "RETURNED",
    "validity_status": "ACTIVE",
    "is_authorized": true,
    "available_actions": ["submit"],
    "workflow_history": [
      {
        "id": 1,
        "fdr_id": 101,
        "action": "SCRUTINY_TRANSITION_DRAFT_TO_SUBMITTED",
        "from_status": "DRAFT",
        "to_status": "SUBMITTED",
        "actor_id": 12,
        "actor_name": "Registrar Alpha",
        "actor_role": "INSTITUTION",
        "actor_email": "registrar@alpha.edu",
        "remarks": "Initial submission for accreditation approval.",
        "is_deficiency": false,
        "resolution_status": null,
        "created_at": "2026-10-26T10:00:00Z"
      },
      {
        "id": 2,
        "fdr_id": 101,
        "action": "SCRUTINY_TRANSITION_PENDING_VERIFICATION_TO_RETURNED",
        "from_status": "PENDING_VERIFICATION",
        "to_status": "RETURNED",
        "actor_id": 4,
        "actor_name": "Scrutiny Officer",
        "actor_role": "AICTE_OFFICER",
        "actor_email": "officer@aicte.gov.in",
        "remarks": "Bank branch seal and authorized signatory signature are missing on page 2.",
        "is_deficiency": true,
        "resolution_status": "UNRESOLVED",
        "created_at": "2026-10-26T11:30:00Z"
      }
    ],
    "deficiencies": [
      {
        "id": 2,
        "fdr_id": 101,
        "remarks": "Bank branch seal and authorized signatory signature are missing on page 2.",
        "is_deficiency": true,
        "resolution_status": "UNRESOLVED",
        "created_at": "2026-10-26T11:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 2,
      "pages": 1,
      "has_next": false,
      "has_prev": false
    }
  }
}
```

---

### 7. Common API Error Codes & Handling

All error responses return a standardized JSON structure with HTTP status codes:
```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable explanation of what failed."
}
```

| HTTP Status | Error Code (`error`) | Typical Cause | Recommended Frontend Handling |
|---|---|---|---|
| `400` | `VALIDATION_ERROR` | Missing required fields, invalid date formats, remarks under 5 chars. | Display form field errors to the user. |
| `400` | `INVALID_TRANSITION` | Attempted illegal state transition (e.g. `DRAFT → VERIFIED`). | Refresh workflow state via `GET /api/fdr/<id>/workflow` to sync UI buttons. |
| `400` | `TERMINAL_STATUS_LOCKED` | Attempted transition on an already `VERIFIED` or `REJECTED` FDR. | Disable all action buttons; notify user record is finalized. |
| `400` | `REMARKS_REQUIRED` | Returning or rejecting without providing decision remarks. | Highlight remark text box with a required validation prompt. |
| `401` | `UNAUTHENTICATED` | Session expired, missing, or invalid. | Clear user session cache; redirect to `/login`. |
| `403` | `CSRF_ERROR` | Missing or mismatched `X-CSRF-Token` header. | Fetch new CSRF token via `GET /api/auth/csrf-token` and retry request. |
| `403` | `WORKFLOW_ROLE_RESTRICTED` | Officer attempted submission, or institution attempted verification/rejection. | Hide unauthorized action buttons based on user role. |
| `404` | `FDR_NOT_FOUND` | FDR does not exist or belongs to another institution (data isolation). | Show "FDR Record Not Found" alert; navigate to list view. |
| `413` | `FILE_TOO_LARGE` | Uploaded document exceeds 16MB file limit. | Warn user prior to upload and block submission. |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | Uploaded file is not PDF, PNG, JPG, or JPEG. | Restrict file input dialog `accept=".pdf,.png,.jpg,.jpeg"`. |
| `500` | `SERVER_ERROR` | Unhandled backend exception. | Display generic error modal with retry option. |

---

## 📊 Step 8: Dashboard, Reports & Analytics APIs

Step 8 introduces executive dashboards, chart-ready time-series distributions, multi-criteria report filtering with pagination, and secure CSV downloads fortified against formula injection.

### 1. New Endpoints Overview

| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/dashboard/stats` | `INSTITUTION`, `AICTE_OFFICER`, `ADMIN` | Total FDR count, total monetary value, status counts (all 6 guaranteed), validity/maturity counts (all 4 guaranteed), monthly trends, and recent activity. |
| `GET` | `/api/dashboard/charts` | `INSTITUTION`, `AICTE_OFFICER`, `ADMIN` | Percentage distribution for scrutiny and validity, monthly time-series metrics, and high-level summary for React charts. |
| `GET` | `/api/reports/fdr` | `INSTITUTION`, `AICTE_OFFICER`, `ADMIN` | Paginated report querying with database-side filtering, multi-field sorting, and aggregate valuation summary. |
| `GET` | `/api/reports/fdr/export` | `INSTITUTION`, `AICTE_OFFICER`, `ADMIN` | Secure CSV export of filtered records with formula injection mitigation (`text/csv` attachment). |

---

### 2. Dashboard Statistics & Charts API

#### `GET /api/dashboard/stats`
- **Query Parameters**:
  - `institution_id` *(optional, for `AICTE_OFFICER` and `ADMIN` only)*: Filter metrics to a specific institution. Institution users are always strictly scoped to their own institution regardless of query params.
- **Example Response (`200 OK`)**:
```json
{
  "success": true,
  "data": {
    "total_fdrs": 6,
    "total_value": 2100000.0,
    "total_value_formatted": "2,100,000.00",
    "status_counts": {
      "DRAFT": 1,
      "SUBMITTED": 1,
      "PENDING_VERIFICATION": 1,
      "VERIFIED": 1,
      "RETURNED": 1,
      "REJECTED": 1
    },
    "validity_counts": {
      "ACTIVE": 3,
      "EXPIRING_SOON": 1,
      "MATURED": 1,
      "OVERDUE_ACTION": 1
    },
    "status_breakdown": [
      { "status": "DRAFT", "count": 1, "percentage": 16.67 },
      { "status": "SUBMITTED", "count": 1, "percentage": 16.67 },
      { "status": "PENDING_VERIFICATION", "count": 1, "percentage": 16.67 },
      { "status": "VERIFIED", "count": 1, "percentage": 16.67 },
      { "status": "RETURNED", "count": 1, "percentage": 16.67 },
      { "status": "REJECTED", "count": 1, "percentage": 16.67 }
    ],
    "validity_breakdown": [
      { "status": "ACTIVE", "count": 3, "percentage": 50.0 },
      { "status": "EXPIRING_SOON", "count": 1, "percentage": 16.67 },
      { "status": "MATURED", "count": 1, "percentage": 16.67 },
      { "status": "OVERDUE_ACTION", "count": 1, "percentage": 16.67 }
    ],
    "monthly_trends": [
      { "month": "2026-05", "count": 0, "total_value": 0.0, "total_value_formatted": "0.00" },
      { "month": "2026-06", "count": 0, "total_value": 0.0, "total_value_formatted": "0.00" },
      { "month": "2026-07", "count": 0, "total_value": 0.0, "total_value_formatted": "0.00" },
      { "month": "2026-08", "count": 1, "total_value": 500000.0, "total_value_formatted": "500,000.00" },
      { "month": "2026-09", "count": 2, "total_value": 600000.0, "total_value_formatted": "600,000.00" },
      { "month": "2026-10", "count": 3, "total_value": 1000000.0, "total_value_formatted": "1,000,000.00" }
    ],
    "recent_activity": [
      {
        "id": 12,
        "fdr_id": 5,
        "fdr_number": "FDR-2026-005",
        "from_status": "PENDING_VERIFICATION",
        "to_status": "RETURNED",
        "action": "SCRUTINY_TRANSITION_PENDING_VERIFICATION_TO_RETURNED",
        "actor_id": 3,
        "actor_name": "AICTE Officer",
        "actor_role": "AICTE_OFFICER",
        "remarks": "Missing signature page on Annexure II",
        "is_deficiency": true,
        "timestamp": "2026-10-26T14:30:00Z"
      }
    ]
  }
}
```

#### `GET /api/dashboard/charts`
Optimized payload for chart widgets (pie, bar, line charts in Recharts/Chart.js):
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_fdrs": 6,
      "total_value": 2100000.0,
      "total_value_formatted": "2,100,000.00"
    },
    "workflow_distribution": [ ... ],
    "validity_distribution": [ ... ],
    "monthly_trends": [ ... ]
  }
}
```

---

### 3. FDR Reports & Filtering API

#### `GET /api/reports/fdr`
- **Supported Query Parameters**:
  | Parameter | Type | Example | Description |
  |---|---|---|---|
  | `scrutiny_status` | String | `VERIFIED` | Filter by workflow status (`DRAFT`, `SUBMITTED`, `PENDING_VERIFICATION`, `VERIFIED`, `RETURNED`, `REJECTED`). |
  | `validity_status` | String | `EXPIRING_SOON` | Filter by maturity status (`ACTIVE`, `EXPIRING_SOON`, `MATURED`, `OVERDUE_ACTION`). |
  | `maturity_from` | Date (`YYYY-MM-DD`) | `2027-01-01` | Minimum maturity date. |
  | `maturity_to` | Date (`YYYY-MM-DD`) | `2027-12-31` | Maximum maturity date. |
  | `created_from` | Date (`YYYY-MM-DD`) | `2026-01-01` | Minimum creation date. |
  | `created_to` | Date (`YYYY-MM-DD`) | `2026-12-31` | Maximum creation date. |
  | `bank_name` | String | `State Bank` | Case-insensitive partial bank name search. |
  | `institution_id` | Integer | `2` | Filter by institution *(Officers/Admins only)*. |
  | `sort_by` | String | `amount` | Field to sort by: `id`, `fdr_number`, `amount`, `issue_date`, `maturity_date`, `scrutiny_status`, `validity_status`, `created_at`, `bank_name`. *(Default: `created_at`)*. |
  | `order` | String | `desc` | Direction: `asc` or `desc`. *(Default: `desc`)*. |
  | `page` | Integer | `1` | Page number $\ge 1$. *(Default: `1`)*. |
  | `per_page` | Integer | `20` | Records per page (1–100). *(Default: `20`)*. |

- **Example Response (`200 OK`)**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "institution_id": 2,
      "institution_name": "Apex College of Technology",
      "fdr_number": "FDR-2026-901",
      "bank_name": "State Bank of India",
      "branch_name": "Industrial Estate",
      "amount": "500000.00",
      "issue_date": "2024-01-15",
      "maturity_date": "2029-01-15",
      "scrutiny_status": "VERIFIED",
      "validity_status": "ACTIVE",
      "created_by": 5,
      "creator_name": "Registrar Alpha",
      "created_at": "2026-02-10T09:15:00Z",
      "updated_at": "2026-02-15T11:20:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "pages": 3,
    "has_next": true,
    "has_prev": false
  },
  "summary": {
    "total_records": 45,
    "total_value": 22500000.0,
    "total_value_formatted": "22,500,000.00"
  }
}
```

---

### 4. CSV Export with Formula Injection Defense

#### `GET /api/reports/fdr/export`
- **Query Parameters**: Identical to `/api/reports/fdr` (filters by status, dates, bank, and sorting).
- **Response Headers**:
  - `Content-Type: text/csv; charset=utf-8`
  - `Content-Disposition: attachment; filename="fdr_report_YYYYMMDD_HHMMSS.csv"`
- **Security Protections**:
  - **Tenant Scoping**: Institution users can only ever download their own records.
  - **CWE-1236 Mitigation**: Cell values beginning with formula prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) are prepended with a single quote (`'`), ensuring Microsoft Excel, LibreOffice Calc, and Google Sheets treat them as safe, static text rather than executable formulas.
  - **Header Structure**: `["FDR ID", "FDR Number", "Institution ID", "Institution Name", "Bank Name", "Branch Name", "Amount (INR)", "Issue Date", "Maturity Date", "Workflow Status", "Validity Status", "Created At (UTC)"]`.

---

### 5. React / Axios Integration Examples

#### Fetching Dashboard Statistics & Charts
```javascript
import apiClient from './api/client';

export async function fetchDashboardData(institutionId = null) {
  const params = institutionId ? { institution_id: institutionId } : {};
  const response = await apiClient.get('/dashboard/stats', { params });
  return response.data.data;
}

export async function fetchChartSummaries() {
  const response = await apiClient.get('/dashboard/charts');
  return response.data.data;
}
```

#### Fetching Filtered & Paginated Reports
```javascript
export async function fetchFDRReport({
  scrutinyStatus,
  validityStatus,
  maturityFrom,
  maturityTo,
  sortBy = 'created_at',
  order = 'desc',
  page = 1,
  perPage = 20,
}) {
  const params = {
    ...(scrutinyStatus && { scrutiny_status: scrutinyStatus }),
    ...(validityStatus && { validity_status: validityStatus }),
    ...(maturityFrom && { maturity_from: maturityFrom }),
    ...(maturityTo && { maturity_to: maturityTo }),
    sort_by: sortBy,
    order,
    page,
    per_page: perPage,
  };

  const response = await apiClient.get('/reports/fdr', { params });
  return response.data; // Contains { success, data, pagination, summary }
}
```

#### Downloading Filtered CSV Export
```javascript
export async function downloadFdrCsv(filters = {}) {
  const response = await apiClient.get('/reports/fdr/export', {
    params: filters,
    responseType: 'blob', // CRITICAL: Treat binary stream as Blob
  });

  // Extract filename from Content-Disposition header if available
  const disposition = response.headers['content-disposition'];
  let filename = 'fdr_report.csv';
  if (disposition && disposition.includes('filename=')) {
    filename = disposition.split('filename=')[1].replace(/["']/g, '');
  }

  // Trigger browser file download
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
```







