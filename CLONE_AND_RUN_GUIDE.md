# 🚀 Clone & Run Guide: AICTE Security Deposit / FDR Management Portal

Welcome to the **AICTE Security Deposit / FDR Management Portal** repository. This guide is written specifically for developers cloning this codebase onto a new machine for the first time. Follow these step-by-step instructions to set up the Python/Flask backend and React/Vite frontend on Windows (PowerShell/CMD).

---

## 📑 Table of Contents
1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [Clone the Repository](#3-clone-the-repository)
4. [Configure the Backend](#4-configure-the-backend)
5. [Configure the Frontend](#5-configure-the-frontend)
6. [Start the Application](#6-start-the-application)
7. [Demo Login Credentials](#7-demo-login-credentials)
8. [Database & Uploaded Files](#8-database--uploaded-files)
9. [OCR Configuration (Document Scrutiny)](#9-ocr-configuration-document-scrutiny)
10. [Testing & Verification](#10-testing--verification)
11. [Troubleshooting](#11-troubleshooting)
12. [Git & Security Checklist](#12-git--security-checklist)
13. [Quick-Start Checklist](#13-quick-start-checklist)

---

## 1. Project Overview

The **AICTE Security Deposit / FDR Management Portal** is a web-based regulatory system built to streamline the lifecycle of institutional Fixed Deposit Receipts (FDRs) pledged to the All India Council for Technical Education (AICTE) under joint lien endorsements.

### System Architecture
- **Backend (`/Backend`)**:
  - **Framework**: Python 3.10+ / Flask application with SQLAlchemy ORM.
  - **Database**: SQLite (`Backend/instance/aicte_fdr.db`) in development; configurable for PostgreSQL.
  - **Security**: Cookie-based session authentication (`aicte_session` cookie, `HttpOnly`, `SameSite=Lax`), session-bound CSRF token validation (`X-CSRF-Token`), and strict Role-Based Access Control (RBAC).
  - **Document Processing & OCR**: Dual-layer text extraction using **PyMuPDF** for digital PDFs and **Tesseract OCR** for scanned images/receipts with automated discrepancy detection.
  - **Background Engine**: APScheduler for automatic maturity scanning, 30-day alerts, and compliance notification dispatch.
- **Frontend (`/Frontend/SIH-PS-1/frontend`)**:
  - **Framework**: React 19 + Vite development and production pipeline.
  - **Styling**: Tailwind CSS with an institutional navy/slate palette (`#142B4A`).
  - **API Layer**: Centralized Axios client (`src/api/client.js`) configured with `withCredentials: true`, automated CSRF token fetching/refresh, and reverse proxy routing via Vite.
  - **Features**: Interactive scrutiny status transitions, inline OCR validation reports, statutory renewal/release petitions, document downloads, real-time alerts, and CSV exports.

---

## 2. Prerequisites

Before setting up the project, verify that the required runtimes and tools are installed on your machine.

| Tool | Recommended Version | Minimum Required | Purpose |
|---|---|---|---|
| **Python** | `3.13.x` | `3.10.0+` | Flask backend runtime |
| **Node.js** | `v20.x` or `v22.x` or `v24.x` | `v18.0.0+` | Vite/React frontend runtime |
| **npm** | `10.x` or `11.x` | `9.0.0+` | Node package manager |
| **Git** | Latest (`2.40+`) | Any recent version | Source control management |
| **Tesseract OCR** *(Optional)* | `v5.3+` | Optional | Only needed for scanned image OCR; digital PDFs work natively |

### Verification Commands
Open a terminal (PowerShell or Command Prompt) and run:

```powershell
python --version
# Expected: Python 3.10.x or higher (e.g., Python 3.13.7)

node -v
# Expected: v18.x.x, v20.x.x, v22.x.x, or v24.x.x

npm -v
# Expected: 9.x.x, 10.x.x, or 11.x.x

git --version
# Expected: git version 2.x.x
```

> [!NOTE]
> If `python` opens the Microsoft Store on Windows, search for **"Manage app execution aliases"** in Windows Settings and turn off the aliases for **"App Installer (python.exe)"** and **"App Installer (python3.exe)"**.

---

## 3. Clone the Repository

Clone the project to your local workstation:

```powershell
# Clone the repository
git clone <REPOSITORY_URL>

# Enter the root directory
cd SIH-PS-1
```

### Directory Structure Notice
All file paths in this guide are relative to the repository root (`SIH-PS-1/`) unless explicitly marked otherwise:

```text
SIH-PS-1/                          <-- Repository Root
├── Backend/                       <-- Flask backend application
│   ├── app/                       <-- Application factory, models, routes, services
│   ├── instance/                  <-- Local SQLite database (gitignored)
│   ├── uploads/                   <-- Uploaded FDRs and petition documents (gitignored)
│   ├── tests/                     <-- Automated pytest suite (121 tests)
│   ├── .env.example               <-- Backend environment template
│   ├── requirements.txt           <-- Python dependencies
│   └── run.py                     <-- Backend entry point script
├── Frontend/
│   └── SIH-PS-1/
│       └── frontend/              <-- React + Vite frontend application
│           ├── src/               <-- React components, pages, context, API client
│           ├── .env.example       <-- Frontend environment template
│           ├── package.json       <-- Node dependencies & scripts
│           └── vite.config.js     <-- Vite build & proxy configuration
├── README.md                      <-- Project overview
└── CLONE_AND_RUN_GUIDE.md         <-- This setup guide
```

---

## 4. Configure the Backend

The backend runs as a Python Flask service. All commands in this section should be executed from the `Backend` directory.

### Step 4.1: Navigate to the Backend Folder
```powershell
cd Backend
```

### Step 4.2: Create and Activate the Virtual Environment
Create an isolated Python virtual environment named `.venv`:

#### On Windows PowerShell:
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

> [!IMPORTANT]
> If PowerShell gives an execution policy error (`running scripts is disabled on this system`), run this one-time command in PowerShell and try activating again:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```

#### On Windows Command Prompt (cmd.exe):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

Once activated, your terminal prompt will be prefixed with `(.venv)`.

### Step 4.3: Install Python Dependencies
Upgrade `pip` and install all dependencies listed in `requirements.txt`:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verified packages installed:
- `Flask>=3.1.0` (Core web framework)
- `Flask-SQLAlchemy>=3.1.1` & `SQLAlchemy>=2.0.36` (Database ORM)
- `python-dotenv>=1.0.1` (Environment variable loader)
- `flask-cors>=6.0.0` (Cross-Origin Resource Sharing)
- `pytest>=9.1.1` (Automated testing framework)
- `pymupdf>=1.24.0` (Digital PDF text extraction)
- `Pillow>=10.0.0` (Image processing)
- `pytesseract>=0.3.10` (OCR engine binding)
- `apscheduler>=3.10.0` (Background maturity tracking scheduler)

### Step 4.4: Configure Environment Variables
Copy `.env.example` to `.env`:

```powershell
# PowerShell
Copy-Item .env.example .env

# Command Prompt
copy .env.example .env
```

Open `Backend/.env` in any text editor. The default development values are pre-configured:

```env
# Application Environment Configuration
FLASK_ENV=development
FLASK_DEBUG=True

# Application metadata
APP_NAME="AICTE Security Deposit / FDR Management Portal"
API_VERSION=1.0.0

# Server Binding
HOST=127.0.0.1
PORT=5000

# Security (Development Key)
SECRET_KEY=dev-aicte-portal-secret-key-change-in-prod

# Database Configuration (SQLite in instance/ folder)
DATABASE_URL=sqlite:///aicte_fdr.db

# CORS Configuration for Frontend Development
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000
```

> [!CAUTION]
> Never commit `.env` or production secrets to Git. The `.env` file is already listed in `.gitignore`.

### Step 4.5: Initialize Database & Seed Development Data
On a freshly cloned repository, the database file does not exist. Run the built-in seeding command:

```powershell
python -m flask seed-dev-data
```

**What this command does automatically:**
1. Creates the SQLite database (`Backend/instance/aicte_fdr.db`) and all required tables.
2. Provisions the initial AICTE Institution: `ABC Institute of Technology & Engineering` (`AICTE-1-10928371`).
3. Provisions 3 role accounts:
   - **Institution Principal:** `principal@abcite.edu.in`
   - **AICTE Scrutiny Officer:** `officer@aicte.gov.in`
   - **System Administrator:** `admin@aicte.gov.in`
4. Seeds 4 realistic FDR records across all workflow lifecycle states (`Verified`, `Pending Verification`, `Returned`, `Draft`).
5. Provisions sample statutory petitions and supporting attachment files.

---

## 5. Configure the Frontend

The frontend is a single-page React 19 application bundled with Vite.

### Step 5.1: Navigate to the Frontend Folder
Open a **new terminal window** or return to the repository root:

```powershell
# From repository root
cd Frontend/SIH-PS-1/frontend
```

### Step 5.2: Install Node Dependencies
Install all required npm dependencies using clean, deterministic versions from `package-lock.json`:

```powershell
npm install
```

### Step 5.3: Configure Environment Variables
Copy `.env.example` to `.env`:

```powershell
# PowerShell
Copy-Item .env.example .env

# Command Prompt
copy .env.example .env
```

Inspect `Frontend/SIH-PS-1/frontend/.env`:
```env
# Backend Flask API base URL (uses Vite proxy in dev)
VITE_API_BASE_URL=/api
```

> [!TIP]
> **Why `VITE_API_BASE_URL=/api`?**
> The Vite development server is configured with a reverse proxy in `vite.config.js`:
> ```javascript
> server: {
>   port: 5173,
>   proxy: {
>     '/api': {
>       target: 'http://127.0.0.1:5000',
>       changeOrigin: true,
>       secure: false,
>     },
>   },
> }
> ```
> This ensures all browser HTTP requests to `/api/*` are made as **same-origin requests** to `http://localhost:5173/api/*` and forwarded internally to Flask on `http://127.0.0.1:5000/api/*`. This eliminates cross-site cookie blocking and guarantees `HttpOnly` session cookies work seamlessly in modern browsers.

---

## 6. Start the Application

You will run the application using **two separate terminal windows**. Both terminals must remain running while using the portal.

### Terminal 1: Backend Server (Flask)

```powershell
# 1. Navigate to Backend directory
cd "c:\path\to\SIH-PS-1\Backend"

# 2. Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Start the Flask server
python run.py
```

**Expected Terminal 1 Output:**
```text
-> Starting AICTE Security Deposit / FDR Management Portal
-> Environment : development
-> Server URL  : http://127.0.0.1:5000
-> Health check: http://127.0.0.1:5000/api/health
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

Verify backend health in your browser or with PowerShell:
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/health
# Expected Output: { status: "healthy", version: "1.0.0", ... }
```

---

### Terminal 2: Frontend Server (Vite)

```powershell
# 1. Navigate to Frontend directory
cd "c:\path\to\SIH-PS-1\Frontend\SIH-PS-1\frontend"

# 2. Start Vite development server
npm run dev
```

**Expected Terminal 2 Output:**
```text
  VITE v8.3.4  ready in 240 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

---

### Accessing the Portal
Open your web browser and navigate to:
👉 **`http://localhost:5173`**

---

## 7. Demo Login Credentials

The portal comes pre-seeded with 3 development accounts covering all primary user personas. You can click the **Quick Demo Role Buttons** on the login screen or enter these credentials manually:

| Persona | Role Identifier | Email Address | Password | Permitted Actions & Scope |
|---|---|---|---|---|
| **College Principal** | `INSTITUTION` | `principal@abcite.edu.in` | `InstitutionPass123!` | View institution's FDRs, upload new deposit receipts, submit FDR renewal/release petitions, view OCR discrepancy reports. |
| **AICTE Scrutiny Officer** | `AICTE_OFFICER` | `officer@aicte.gov.in` | `OfficerPass123!` | Scrutinize pending FDRs across colleges, lock records for review (`start-review`), verify/approve, return for rectification, or reject deposits with remarks. |
| **System Administrator** | `ADMIN` | `admin@aicte.gov.in` | `AdminPass123!` | Complete supervisory control, audit log inspection, petition status administration, system configuration, and CSV compliance exports. |

> [!WARNING]
> These credentials are for **local development and demonstration only**.

---

## 8. Database & Uploaded Files

### Database Storage
- **Database Engine**: SQLite 3 (via SQLAlchemy).
- **File Location**: `Backend/instance/aicte_fdr.db`.
- **Git Status**: Gitignored. A fresh clone will **not** contain `aicte_fdr.db` until you run `python -m flask seed-dev-data`.
- **Re-seeding / Reset**: If you ever want to reset the database to a fresh state, simply delete `Backend/instance/aicte_fdr.db` and run `python -m flask seed-dev-data` again.

### Document Upload Directories
The backend maintains two dedicated directories for document storage inside `Backend/uploads/`:

1. `Backend/uploads/fdr_documents/`
   - Stores uploaded scanned FDR receipts and bank lien endorsement certificates.
   - Companion JSON analysis files (`<filename>.analysis.json`) store cached OCR extraction and discrepancy reports.
2. `Backend/uploads/request_documents/`
   - Stores institutional petitions, bank undertakings, and renewal/release supporting documents.

Both directories are created automatically by the backend upon startup and are excluded from version control via `.gitignore`.

---

## 9. OCR Configuration (Document Scrutiny)

The portal features an automated document scrutiny engine that extracts deposit details (FDR number, amount, bank name, dates) and compares them against form inputs.

### How Text Extraction Operates:
1. **Digital PDFs (No installation required)**:
   - When colleges upload digital PDFs (e.g., generated by net banking or converted from Word), **PyMuPDF (`pymupdf`)** extracts the native embedded text directly in memory.
   - **Tesseract is NOT required for digital PDFs.** The discrepancy analysis works out of the box.
2. **Scanned Documents & Images (Optional Tesseract OCR)**:
   - When a raster image (`.png`, `.jpg`, `.jpeg`) or a scanned, non-searchable PDF is uploaded, the backend attempts to invoke **Tesseract OCR** via `pytesseract`.
   - **Graceful Fallback**: If Tesseract is not installed, the upload **does not fail**. The document is saved securely, and the OCR status is marked with an informative notice: `"Scanned PDF with minimal digital text. Tesseract OCR is not installed or available on PATH."`

### Installing Tesseract on Windows (Optional for Scanned Documents)
If you wish to test OCR on scanned image files:
1. Run with Windows Package Manager (PowerShell as Administrator):
   ```powershell
   winget install UB-Mannheim.TesseractOCR
   ```
   *Or download the Windows installer from:* [UB-Mannheim Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
2. The default installation path is `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. The backend automatically detects this path in `app/services/ocr_service.py`. Alternatively, you can add `C:\Program Files\Tesseract-OCR` to your Windows System `PATH` or define `TESSERACT_CMD` in `Backend/.env`:
   ```env
   TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```
4. Verify by running in a new terminal:
   ```powershell
   tesseract --version
   ```

---

## 10. Testing & Verification

Automated test suites ensure system stability and verify all security, authentication, and OCR features.

### Run Backend Tests (121 Automated Tests)
Ensure your backend virtual environment is activated:

```powershell
cd Backend
.\.venv\Scripts\Activate.ps1

# Run the complete test suite
python -m pytest -q
```

**Expected Result:**
```text
......................................................................................................................... [100%]
121 passed in ~65s
```

Tested test modules:
- `tests/test_auth.py`: Session cookies, login, CSRF tokens, RBAC permissions.
- `tests/test_fdr.py`: Multi-tenant data isolation, CRUD operations, FDR validation.
- `tests/test_requests.py`: Petition submission, multi-tenant boundaries, document streaming downloads.
- `tests/test_document_ocr.py`: Magic bytes file validation, PyMuPDF extraction, discrepancy detection.
- `tests/test_workflow.py` & `tests/test_workflow_api.py`: Bureau scrutiny state transitions (`Submit`, `Start Review`, `Verify`, `Return`, `Reject`).
- `tests/test_maturity_notifications.py`: Maturity calculations and alert intervals.
- `tests/test_dashboard_reports.py`: Dashboard statistics and CSV exports.

### Run Frontend Code Verification
From the frontend directory:

```powershell
cd Frontend/SIH-PS-1/frontend

# 1. Run static linter
npm run lint
# Expected: 0 errors across 59 files

# 2. Run production build verification
npm run build
# Expected: Built in ~1.2s without errors, output in dist/
```

---

## 11. Troubleshooting

### Problem 1: `python` or `pip` is not recognized
- **Cause**: Python was not added to your system `PATH` during installation.
- **Solution**: Re-run the Python Windows installer, select **"Modify"**, and ensure **"Add Python to PATH"** is checked. Alternatively, use the full path to your Python executable (e.g., `C:\Users\<User>\AppData\Local\Programs\Python\Python313\python.exe`).

### Problem 2: PowerShell script execution error (`Activate.ps1 cannot be loaded`)
- **Cause**: Windows PowerShell restricts execution of unsigned scripts by default.
- **Solution**: Open PowerShell and run:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```
  Then re-run `.\.venv\Scripts\Activate.ps1`.

### Problem 3: Port 5000 or 5173 is already in use
- **Cause**: A previous server process is still running in the background.
- **Solution for Port 5000 (Backend)**:
  ```powershell
  # Find PID using port 5000
  netstat -ano | findstr :5000

  # Kill the process by PID (replace <PID> with the number from the last column)
  taskkill /PID <PID> /F
  ```
  *Alternatively, edit `PORT=5001` in `Backend/.env` and update the proxy target in `vite.config.js`.*
- **Solution for Port 5173 (Frontend)**:
  Vite will automatically offer to use port `5174` or you can terminate the conflicting process:
  ```powershell
  netstat -ano | findstr :5173
  taskkill /PID <PID> /F
  ```

### Problem 4: Login page redirects back or shows 401 Unauthorized
- **Cause**: Either the backend is not running on port 5000, or the database was not seeded.
- **Solution**:
  1. Confirm the backend is running and `http://127.0.0.1:5000/api/health` returns `status: "healthy"`.
  2. Confirm database tables and users exist:
     ```powershell
     cd Backend
     .\.venv\Scripts\Activate.ps1
     python -m flask seed-dev-data
     ```
  3. Ensure your browser allows cookies for `localhost:5173`. Do not bypass the Vite proxy by pointing directly to port 5000 in your browser address bar.

### Problem 5: Missing attachment error when downloading in petition modal
- **Cause**: The petition record references a supporting file that does not exist in `Backend/uploads/request_documents/`.
- **Solution**: Run `python -m flask seed-dev-data` to regenerate the default sample files (`SBI_Deposit_Extension_Undertaking.pdf` and `FDR-HDFC-2024-11842_SupportingDoc.pdf`).

### Problem 6: `npm install` fails or has dependency tree conflicts
- **Cause**: Outdated npm cache or incompatible Node version.
- **Solution**:
  ```powershell
  cd Frontend/SIH-PS-1/frontend
  npm cache clean --force
  npm install
  ```

---

## 12. Git & Security Checklist

When working on this repository, observe the following security standards:

- **Tracked Files Verification**:
  Ensure sensitive local files are **never** committed:
  ```powershell
  git status
  ```
- **Files that MUST be gitignored**:
  - `Backend/.env` (contains server secret keys)
  - `Backend/.venv/` (local Python packages)
  - `Backend/instance/*.db` (local SQLite databases containing credentials and user data)
  - `Backend/uploads/*` (uploaded receipts and sensitive financial PDFs)
  - `Frontend/SIH-PS-1/frontend/node_modules/` (Node packages)
  - `Frontend/SIH-PS-1/frontend/dist/` (compiled production assets)

> [!CAUTION]
> **Important Git Rule**: Adding an existing file to `.gitignore` does **not** stop Git from tracking it if it was previously committed. If you accidentally committed a sensitive file, untrack it without deleting the local file:
> ```powershell
> git rm --cached Backend/.env
> ```

---

## 13. Quick-Start Checklist

Use this quick checklist to get the portal up and running in under 3 minutes:

| # | Step | Working Directory | Command to Run |
|---|---|---|---|
| 1 | **Clone Repo** | Desired folder | `git clone <REPO_URL>` |
| 2 | **Enter Root** | `SIH-PS-1` | `cd SIH-PS-1` |
| 3 | **Create Backend venv** | `Backend/` | `cd Backend; python -m venv .venv` |
| 4 | **Activate venv** | `Backend/` | `.\.venv\Scripts\Activate.ps1` |
| 5 | **Install Python libs** | `Backend/` | `pip install -r requirements.txt` |
| 6 | **Copy Backend .env** | `Backend/` | `Copy-Item .env.example .env` |
| 7 | **Seed Database** | `Backend/` | `python -m flask seed-dev-data` |
| 8 | **Start Backend** | `Backend/` | `python run.py` |
| 9 | **Install Frontend libs** | `Frontend/SIH-PS-1/frontend/` | `cd ../Frontend/SIH-PS-1/frontend; npm install` |
| 10 | **Copy Frontend .env** | `Frontend/SIH-PS-1/frontend/` | `Copy-Item .env.example .env` |
| 11 | **Start Frontend** | `Frontend/SIH-PS-1/frontend/` | `npm run dev` |
| 12 | **Open Portal** | Web Browser | Open **`http://localhost:5173`** |
| 13 | **Login** | Web Browser | Use `principal@abcite.edu.in` / `InstitutionPass123!` |

---
*Created for the AICTE Security Deposit / FDR Management Portal engineering team.*
