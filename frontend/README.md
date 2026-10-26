# AICTE FDR Management System — College Dashboard Frontend

The **AICTE Fixed Deposit Receipt (FDR) Management System** is a centralized institutional web portal designed for technical colleges and institutions approved by the All India Council for Technical Education (AICTE). 

Institutions submit FDRs as statutory security deposits under the AICTE Approval Process Handbook (APH). This dashboard provides college administrators with a dedicated, professional digital interface to monitor active security deposits, track upcoming maturities, upload new receipts with joint lien endorsements, submit renewal and release requests, and receive automated compliance alerts.

---

## 🚀 Key Features

1. **Demonstration Authentication & Session**
   - Institutional sign-in with pre-filled sample administrator credentials.
   - One-click **Quick Demo Sign-In** option.
   - Clean demonstration exit confirmation dialog.

2. **College Dashboard Overview (`/`)**
   - **Institutional Welcome Banner**: Displays college details, AICTE Permanent ID, and quick action buttons.
   - **Summary Metric Cards**: Live calculated metrics for *Total FDRs*, *Active FDRs*, *Maturing Soon (Next 30 Days)*, and *Pending Requests*.
   - **Upcoming Maturities Table**: Real-time sorting by nearest maturity date, highlighting records with days remaining.
   - **Status Distribution Chart**: Interactive Donut Chart powered by [Recharts](https://recharts.org/) showing record proportions across all statuses.
   - **Recent FDR Records**: Quick search, status filter, and direct details link.
   - **Live Notifications Preview**: Inline unread indicators and quick mark-as-read actions.

3. **My FDRs Listing Page (`/fdrs`)**
   - Search across FDR reference number, bank name, and branch IFSC.
   - Multi-criteria filtering by official statuses (*Active*, *Pending Verification*, *Renewal Pending*, *Matured*, *Released*, *Rejected*).
   - Timeline filtering (*All*, *Maturing Soon (≤ 30 Days)*, *Active / Future*, *Overdue*).
   - Column sorting by Ref Number, Amount, Issue Date, and Maturity Date.
   - Pagination controls and empty state handling.

4. **Upload New FDR Page (`/upload`)**
   - Multi-step guided wizard (*Enter Details* ➔ *Review Submission* ➔ *Completed*).
   - Strict validation powered by [React Hook Form](https://react-hook-form.com/) and [Zod](https://zod.dev/):
     - Minimum deposit check (₹ 10,000+).
     - Chronological check ensuring maturity date is strictly later than issue date.
     - Document upload validation (restricted to PDF, JPEG, PNG, max 10MB).
   - Immediate reactive state update: Newly uploaded receipts immediately populate in the Dashboard counters, recent tables, and FDR listing.

5. **Individual FDR Details Page (`/fdrs/:id`)**
   - Complete breakdown of deposit principal, bank branch, interest rates, and regulatory joint lien mapping.
   - Verifiable **Audit & Activity History** timeline.
   - Interactive **Document Preview Dialog** displaying simulated bank receipt scans.
   - Contextual actions: **Request Renewal** and **Request Release** modals that submit requests directly to the application state pipeline.

6. **Renewal / Release Requests Page (`/requests`)**
   - Central tracker for all petitions submitted to the AICTE Regional Bureau.
   - Detailed status badges (*Submitted*, *Under Review*, *Approved*, *Processed*, *Rejected*).
   - Modal form for creating new renewal or release petitions with justification and document attachment.

7. **System Notifications Page (`/notifications`)**
   - Categorized tabs (*All*, *Unread*, *Maturities & Action Alerts*, *Verification & Requests*).
   - Real-time unread counter synchronized across the top navigation bar, sidebar, and dashboard.
   - Single-click *Mark as Read* and *Mark All as Read* actions.

8. **Institutional Profile & Settings (`/profile`)**
   - View and update authorized administrator details, designation, contact phone, campus postal address, and alternate alert email.
   - Reactive synchronization: Saving updates immediately updates the topbar administrator name and college branding throughout the portal.

---

## 🛠️ Technology Stack

| Purpose | Technology |
|---|---|
| Frontend Framework | **React 19** |
| Tooling & Dev Server | **Vite** |
| Language | **JavaScript (JSX)** |
| Styling | **Tailwind CSS** |
| UI Component Styling | **shadcn/ui inspired primitives** |
| Routing | **React Router (v7)** |
| Iconography | **Lucide React** |
| Charts & Visualizations | **Recharts** |
| Forms & Inputs | **React Hook Form** |
| Schema Validation | **Zod** |
| State Management | **React Context API & Custom Hooks** |

---

## 📁 Project Structure

```text
frontend/
├── public/
│   ├── favicon.svg             # Institutional portal favicon
├── src/
│   ├── components/
│   │   ├── dashboard/          # SummaryCards, UpcomingMaturities, StatusDistributionChart, etc.
│   │   ├── fdr/                # FDRStatusBadge, FDRTable components
│   │   ├── layout/             # Sidebar, TopNavbar, LogoutModal
│   │   ├── notifications/      # Notification components
│   │   ├── requests/           # RequestStatusBadge, RequestsTable
│   │   └── ui/                 # Reusable Button, Input, Select, Card, Modal, Badge, Toast, EmptyState
│   ├── constants/
│   │   ├── bankList.js         # Scheduled commercial banks in India
│   │   └── statusConstants.js  # FDR and Request statuses
│   ├── context/
│   │   └── AppContext.jsx      # Central reactive state, actions, and toast system
│   ├── data/
│   │   └── mock/               # Mock FDRs, Requests, Notifications, and Profile
│   ├── hooks/                  # useFDR, useRequests, useNotifications, useProfile, useAuth
│   ├── layouts/
│   │   └── DashboardLayout.jsx # Master layout with persistent sidebar and responsive header
│   ├── pages/
│   │   ├── DashboardPage.jsx
│   │   ├── FDRListPage.jsx
│   │   ├── FDRDetailPage.jsx
│   │   ├── UploadFDRPage.jsx
│   │   ├── RequestsPage.jsx
│   │   ├── NotificationsPage.jsx
│   │   ├── ProfilePage.jsx
│   │   ├── LoginPage.jsx
│   │   └── NotFoundPage.jsx
│   ├── schemas/                # Zod schemas for FDR upload, requests, and profile
│   ├── services/               # Mock data loaders and business calculations
│   ├── utils/                  # Currency formatters, date helpers, cn class merge
│   ├── App.jsx                 # Routing configuration
│   ├── index.css               # Tailwind CSS tokens and base styles
│   └── main.jsx
├── index.html
├── package.json
├── tailwind.config.js
├── vite.config.js
└── README.md
```

---

## 💻 Installation & Running Locally

Ensure you have **Node.js** (v18+ or v20+) installed.

### 1. Navigate to the frontend directory
```bash
cd frontend
```

### 2. Install dependencies
```bash
npm install
```

### 3. Start the development server
```bash
npm run dev
```

Open your browser and navigate to:
```text
http://localhost:5173/
```

### 4. Build for production
```bash
npm run build
```

---

## 🎨 Color Palette & Design Tokens

In accordance with institutional guidelines, the portal follows an official government-ready palette:
- **Primary Navy**: `#142B4A` (Institutional authority and trust)
- **Background**: `#F4F7FB` (Light slate canvas)
- **Cards & Panels**: `#FFFFFF` (Clean, subtle borders and shadows)
- **Gold / Accent**: `#C59B27` (AICTE compliance highlights)
- **Status Colors**:
  - *Active*: Emerald Green (`#10B981`)
  - *Pending Verification*: Amber (`#F59E0B`)
  - *Renewal Pending*: Blue (`#3B82F6`)
  - *Matured*: Purple (`#8B5CF6`)
  - *Released*: Slate Grey (`#64748B`)
  - *Rejected*: Rose Red (`#EF4444`)

---

## 🛡️ Note on Scope

This repository contains the **college-side frontend only**. All records, request workflows, and status updates are managed dynamically in frontend state for demonstration purposes without requiring a backend database or actual AICTE server connectivity.
