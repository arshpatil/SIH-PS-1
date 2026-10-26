# AICTE Security Deposit / FDR Management Portal (End-to-End Integration)

A comprehensive, end-to-end integrated web application for institutional Fixed Deposit Receipt (FDR) lifecycle management, regulatory scrutiny workflows, automated OCR discrepancy detection, maturity tracking, and audit compliance under the All India Council for Technical Education (AICTE).

---

## 🏛️ Architecture Overview

The system consists of two tightly integrated components:

1. **Flask Backend (`/Backend`)**:
   - Python 3.10+ / Flask application with SQLite database (`instance/aicte_fdr.db`).
   - Server-side session authentication (`HttpOnly` session cookie) and session-bound CSRF token validation (`X-CSRF-Token`).
   - Role-Based Access Control (`INSTITUTION`, `AICTE_OFFICER`, `ADMIN`).
   - PyMuPDF / Pillow / Tesseract OCR engine for document discrepancy checking.
   - Deterministic maturity scanning service and notification engine.
   - Comprehensive scrutiny workflow state engine and structured workflow audit history.
   - 111 passing automated test suite (`python -m pytest -q`).

2. **React/Vite Frontend (`/Frontend/SIH-PS-1/frontend`)**:
   - React 19 + Vite development and production pipeline.
   - Tailwind CSS design system with an official institutional navy/slate palette.
   - Centralized Axios client (`src/api/client.js`) configured with `withCredentials: true`, automated CSRF token synchronization, and 403 CSRF-error auto-retry.
   - Role-aware UI components, sidebar, and status action bars.
   - Interactive scrutiny workflow transitions (`Submit`, `Start Review`, `Verify`, `Return`, `Reject`).
   - Direct document upload and inline OCR discrepancy detection dialog.
   - Real-time notifications with unread counter synchronization and bulk read action.
   - CSV export for FDR compliance and audit reports.

---

## 🚀 Quick Start Guide

### 1. Start the Flask Backend

Open PowerShell in the `Backend` directory:

```powershell
cd "c:\Users\arsh patil\OneDrive\Desktop\SIH-PS-1\Backend"

# Activate the existing virtual environment
.\.venv\Scripts\Activate.ps1

# (Optional) Seed sample institutions, users, and FDRs if needed:
.\.venv\Scripts\python -m flask seed-dev-data

# Run the backend server (runs on http://127.0.0.1:5000)
.\.venv\Scripts\python run.py
```

- **Backend URL**: `http://127.0.0.1:5000`
- **Health Check**: `http://127.0.0.1:5000/api/health`
- **Allowed CORS Origins**: `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://127.0.0.1:3000`

---

### 2. Start the React Frontend

Open a second PowerShell terminal in the `Frontend/SIH-PS-1/frontend` directory:

```powershell
cd "c:\Users\arsh patil\OneDrive\Desktop\SIH-PS-1\Frontend\SIH-PS-1\frontend"

# Start the Vite development server (runs on http://localhost:5173)
npm run dev
```

- **Frontend URL**: `http://localhost:5173`
- The Vite development server automatically proxies all `/api` requests to `http://127.0.0.1:5000`, guaranteeing 100% same-origin cookie delivery and eliminating cross-site cookie blocking.

---

## 🔑 Demo User Accounts

The database comes pre-seeded with three accounts representing each distinct role in the portal. You can use the quick one-click role buttons on the login screen or enter the credentials manually:

| Role Category | Role Name | Email Address | Password | Permissions & Scope |
|---|---|---|---|---|
| **Institution** | Principal / College Administrator | `principal@abcite.edu.in` | `InstitutionPass123!` | Manages own institution FDRs (`AICTE-1-10928371`), uploads receipts, views OCR discrepancies, resubmits returned FDRs. |
| **AICTE Officer** | Scrutiny Officer | `officer@aicte.gov.in` | `OfficerPass123!` | Scrutinizes submitted FDRs across all institutions, locks records for review (`start-review`), approves (`verify`), returns (`return`), or rejects (`reject`) deposits with mandatory remarks. |
| **System Admin** | Administrator | `admin@aicte.gov.in` | `AdminPass123!` | Full supervisory oversight across all colleges, workflow interventions, CSV compliance exports, and system settings. |

---

## 🧪 Verification & Automated Tests

### Backend Automated Test Suite
From the `Backend/` directory:
```powershell
.\.venv\Scripts\python -m pytest -q
```
**Result**: 111 passed in ~60s across health, models, authentication, security, FDR management, document OCR, maturity notifications, and workflow history.

### Frontend Lint and Build
From the `Frontend/SIH-PS-1/frontend/` directory:
```powershell
# Run code lint
npm run lint

# Run production build
npm run build
```
**Result**: 0 errors, production bundle compiled cleanly in `dist/`.

---

## 🔒 Security & Session Handling

1. **Cookie-Based Sessions**: The backend sets an `aicte_session` cookie (`HttpOnly`, `SameSite=Lax`). Axios includes this on all requests with `withCredentials: true`.
2. **Session-Bound CSRF Token**: All state-modifying HTTP requests (`POST`, `PUT`, `PATCH`, `DELETE`) require the `X-CSRF-Token` header. The Axios client automatically fetches and synchronizes this token upon initial load and login.
3. **Multi-Tenant Data Isolation**: Institution users are scoped strictly to their registered institution ID. Any attempt to inspect or modify an external institution's FDR triggers an immediate `404 Not Found`.
4. **Immutable Audit Logs**: Every workflow status change, document upload, and login event is written to the immutable `AuditLog` table.
