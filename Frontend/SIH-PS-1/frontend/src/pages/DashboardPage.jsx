import React from 'react'
import { Link } from 'react-router-dom'
import {
  PlusCircle,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  FileCheck2,
  Calendar,
  Building,
  Landmark,
  ArrowRight,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SummaryCards } from '../components/dashboard/SummaryCards'
import { UpcomingMaturitiesTable } from '../components/dashboard/UpcomingMaturitiesTable'
import { StatusDistributionChart } from '../components/dashboard/StatusDistributionChart'
import { RecentFDRsTable } from '../components/dashboard/RecentFDRsTable'
import { NotificationsPreview } from '../components/dashboard/NotificationsPreview'
import { AdminDashboardPage } from './AdminDashboardPage'
import { OfficerDashboardPage } from './OfficerDashboardPage'
import { useApp } from '../context/AppContext'

export function DashboardPage() {
  const { profile, stats, currentUser, requests } = useApp()

  const role = currentUser?.role || currentUser?.role_category

  // Route to dedicated Administrator workspace
  if (role === 'ADMIN') {
    return <AdminDashboardPage />
  }

  // Route to dedicated Scrutiny Officer workbench
  if (role === 'AICTE_OFFICER') {
    return <OfficerDashboardPage />
  }

  // Institution / College Dashboard
  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Institution Regulatory Header Banner */}
      <div className="bg-[#0B1B3D] border border-[#1E3A63] rounded-xl p-5 sm:p-6 text-white shadow-subtle relative overflow-hidden">
        {/* Subtle decorative grid/watermark */}
        <div className="absolute right-0 top-0 translate-x-12 -translate-y-8 w-72 h-72 bg-gradient-to-br from-white/10 to-transparent rounded-full blur-2xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-2 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-white/10 text-amber-300 text-2xs font-bold uppercase tracking-wider border border-white/15">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
              <span>AICTE Joint Security Deposit Management</span>
            </div>

            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              {profile.collegeName || currentUser?.institution_name || 'Technical Educational Institution'}
            </h1>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-300">
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">AICTE Permanent ID:</span>
                <span className="font-mono text-amber-300 font-semibold">
                  {profile.aictePermanentId || currentUser?.institution_code || '1-4392817291'}
                </span>
              </span>
              <span className="text-slate-500">•</span>
              <span className="flex items-center gap-1.5">
                <span className="text-slate-400">Account Administrator:</span>
                <span className="text-white font-medium">
                  {currentUser?.full_name || 'Principal / Registrar'}
                </span>
              </span>
            </div>

            <p className="text-slate-300 text-xs sm:text-sm leading-relaxed pt-1">
              Statutory oversight for institutional fixed deposit receipts pledged jointly with AICTE New Delhi.
              Monitor compliance, track maturing receipts, and initiate renewals or release petitions.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <Link to="/upload">
              <Button
                variant="warning"
                size="md"
                icon={PlusCircle}
                className="font-semibold shadow-xs"
              >
                Deposit New FDR
              </Button>
            </Link>
            <Link to="/requests">
              <Button
                variant="secondary"
                size="md"
                className="bg-white/10 hover:bg-white/20 text-white border-white/20 hover:border-white/30"
              >
                Petitions & Actions
              </Button>
            </Link>
            <Link to="/calendar">
              <Button
                variant="secondary"
                size="md"
                className="bg-white/10 hover:bg-white/20 text-white border-white/20 hover:border-white/30"
                icon={Calendar}
              >
                Calendar
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Maturing Soon Urgent Notice if any */}
      {stats?.maturingSoon > 0 && (
        <div className="flex items-center justify-between p-3.5 sm:p-4 bg-amber-50 rounded-xl border border-amber-300/80 shadow-2xs text-amber-900 text-xs sm:text-sm">
          <div className="flex items-start sm:items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5 sm:mt-0" />
            <div>
              <span className="font-bold">Maturity Action Due: </span>
              <span>
                {stats.maturingSoon} security deposit receipt(s) will mature within the next 30 days. Please initiate renewal or release petitions immediately to maintain regulatory compliance.
              </span>
            </div>
          </div>
          <Link
            to="/fdrs"
            className="shrink-0 ml-4 font-semibold text-amber-900 hover:text-amber-950 underline text-xs whitespace-nowrap"
          >
            Review Now &rarr;
          </Link>
        </div>
      )}

      {/* Approved Renewal Petitions Awaiting FDR Receipt */}
      {requests?.some(
        (r) =>
          (r.requestType === 'Renewal' || r.request_type === 'Renewal') &&
          r.status === 'Approved' &&
          !r.renewalSubmittedAt &&
          !r.renewal_submitted_at
      ) && (
        <div className="flex items-center justify-between p-3.5 sm:p-4 bg-emerald-50 rounded-xl border border-emerald-300 shadow-2xs text-emerald-950 text-xs sm:text-sm">
          <div className="flex items-start sm:items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5 sm:mt-0" />
            <div>
              <span className="font-bold">Renewal Petition Approved: </span>
              <span>
                Your FDR renewal petition has been sanctioned by AICTE. Please submit the renewed deposit receipt issued by your bank to update the regulatory maturity date.
              </span>
            </div>
          </div>
          <Link
            to="/requests"
            className="shrink-0 ml-4 font-semibold text-emerald-800 hover:text-emerald-950 underline text-xs whitespace-nowrap"
          >
            Submit Renewed Receipt &rarr;
          </Link>
        </div>
      )}

      {/* Summary Stat Cards */}
      <SummaryCards />

      {/* 2-Column Section: Upcoming Maturities + Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 sm:gap-6">
        <div className="lg:col-span-2">
          <UpcomingMaturitiesTable />
        </div>
        <div className="lg:col-span-1">
          <StatusDistributionChart />
        </div>
      </div>

      {/* 2-Column Section: Recent FDR Records + Notifications Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 sm:gap-6">
        <div className="lg:col-span-2">
          <RecentFDRsTable />
        </div>
        <div className="lg:col-span-1">
          <NotificationsPreview />
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
