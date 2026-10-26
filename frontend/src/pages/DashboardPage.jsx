import React from 'react'
import { Link } from 'react-router-dom'
import { PlusCircle, ShieldCheck, Download, AlertCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SummaryCards } from '../components/dashboard/SummaryCards'
import { UpcomingMaturitiesTable } from '../components/dashboard/UpcomingMaturitiesTable'
import { StatusDistributionChart } from '../components/dashboard/StatusDistributionChart'
import { RecentFDRsTable } from '../components/dashboard/RecentFDRsTable'
import { NotificationsPreview } from '../components/dashboard/NotificationsPreview'
import { useApp } from '../context/AppContext'

export function DashboardPage() {
  const { profile, stats } = useApp()

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-[#142B4A] via-[#1A3C67] to-[#142B4A] rounded-2xl p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
        {/* Subtle decorative background circle */}
        <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-64 h-64 bg-white/5 rounded-full blur-2xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/10 text-amber-300 text-xs font-medium border border-white/10">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>AICTE Institutional Security Deposit Portal</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Welcome back, College Administrator
            </h1>
            <p className="text-slate-200 text-sm leading-relaxed">
              Managing security deposits for <span className="text-white font-medium">{profile.collegeName}</span> (ID: <span className="font-mono text-amber-200">{profile.aictePermanentId}</span>). Monitor compliance, track maturing receipts, and initiate renewals.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link to="/upload">
              <Button
                variant="primary"
                size="md"
                className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold shadow-md border border-amber-400"
                icon={PlusCircle}
              >
                Upload New FDR
              </Button>
            </Link>
            <Link to="/requests">
              <Button
                variant="secondary"
                size="md"
                className="bg-white/10 hover:bg-white/20 text-white border-white/20"
              >
                Manage Requests
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Maturing Soon Urgent Notice if any */}
      {stats.maturingSoon > 0 && (
        <div className="flex items-center justify-between p-4 bg-amber-50 rounded-xl border border-amber-300/80 shadow-xs text-amber-900 text-xs sm:text-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold">Attention Required:</span> {stats.maturingSoon} FDR record(s) are approaching their maturity date within 30 days. Please verify if renewal or release is required.
            </div>
          </div>
          <Link
            to="/fdrs"
            className="shrink-0 ml-4 font-semibold text-amber-800 hover:text-amber-950 underline text-xs"
          >
            Review Maturities &rarr;
          </Link>
        </div>
      )}

      {/* Summary Cards */}
      <SummaryCards />

      {/* 2-Column Section: Upcoming Maturities + Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <UpcomingMaturitiesTable />
        </div>
        <div className="lg:col-span-1">
          <StatusDistributionChart />
        </div>
      </div>

      {/* 2-Column Section: Recent FDR Records + Notifications Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
