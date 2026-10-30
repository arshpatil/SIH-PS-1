import React, { useState, useEffect, useCallback } from 'react'
import {
  Calendar as CalendarIcon,
  Clock,
  AlertTriangle,
  FileCheck2,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react'
import { FDRCalendar } from '../components/calendar/FDRCalendar'
import { calendarService } from '../services/calendarService'
import { useApp } from '../context/AppContext'

export function CalendarPage() {
  const { currentUser } = useApp()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch 12-month window for broad calendar visibility
      const today = new Date()
      const start = new Date(today.getFullYear(), today.getMonth() - 2, 1).toISOString().substring(0, 10)
      const end = new Date(today.getFullYear() + 2, today.getMonth(), 28).toISOString().substring(0, 10)

      const fetched = await calendarService.getEvents({ start, end })
      setEvents(fetched || [])
    } catch (err) {
      console.error('Failed to load calendar events:', err)
      setError('Failed to load calendar data from official records. Please verify network connectivity.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchEvents()
  }, [fetchEvents])

  // Aggregate metrics
  const metrics = React.useMemo(() => {
    let maturities = 0
    let receiptsDue = 0
    let verificationPending = 0
    let deadlines = 0

    for (const ev of events) {
      if (ev.category === 'MATURITY') maturities++
      if (ev.type === 'RENEWAL_APPROVED_AWAITING_RECEIPT') receiptsDue++
      if (ev.type === 'RENEWAL_PENDING_VERIFICATION') verificationPending++
      if (ev.category === 'DEADLINE' || ev.type === 'PETITION_REVIEW_DEADLINE') deadlines++
    }

    return { maturities, receiptsDue, verificationPending, deadlines }
  }, [events])

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' ||
    currentUser?.role === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Page Header */}
      <div className="bg-white rounded-xl shadow-card border border-slate-200 p-4 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-2xs font-bold text-slate-500 uppercase tracking-wider mb-1">
            <CalendarIcon className="w-3.5 h-3.5 text-navy-700" />
            <span>AICTE Statutory Operations Timeline</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Compliance & Maturity Calendar
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-3xl leading-relaxed">
            {isOfficerOrAdmin
              ? 'Authorized regulatory schedule of official deposit terms, statutory scrutiny deadlines, renewed receipt verifications, and compliance enforcement.'
              : 'Institutional schedule of your joint FDR deposit maturities, renewal petition milestones, and required renewed bank receipt uploads.'}
          </p>
        </div>

        <button
          type="button"
          onClick={fetchEvents}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-[#142B4A] hover:bg-[#0E1E34] text-white rounded-lg text-xs font-semibold shadow-xs transition-colors shrink-0 self-start md:self-auto"
        >
          <RefreshCw className={loading ? 'w-3.5 h-3.5 animate-spin' : 'w-3.5 h-3.5'} />
          <span>Sync Schedule</span>
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4.5">
        <div className="bg-white rounded-xl border border-slate-200 p-3.5 sm:p-4 shadow-card flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-rose-50 text-rose-700 border border-rose-200/60 flex items-center justify-center shrink-0">
            <Clock className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider truncate">
              Deposit Maturities
            </p>
            <p className="text-xl sm:text-2xl font-bold text-slate-900 tabular-nums">{metrics.maturities}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-3.5 sm:p-4 shadow-card flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200/60 flex items-center justify-center shrink-0">
            <FileCheck2 className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider truncate">
              Renewal Receipts Due
            </p>
            <p className="text-xl sm:text-2xl font-bold text-slate-900 tabular-nums">{metrics.receiptsDue}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-3.5 sm:p-4 shadow-card flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-700 border border-purple-200/60 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider truncate">
              Pending Verification
            </p>
            <p className="text-xl sm:text-2xl font-bold text-slate-900 tabular-nums">{metrics.verificationPending}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-3.5 sm:p-4 shadow-card flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-700 border border-amber-200/60 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider truncate">
              Scrutiny Deadlines
            </p>
            <p className="text-xl sm:text-2xl font-bold text-slate-900 tabular-nums">{metrics.deadlines}</p>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Interactive Calendar Component */}
      <FDRCalendar
        events={events}
        loading={loading}
        onRefresh={fetchEvents}
        currentUser={currentUser}
      />
    </div>
  )
}

export default CalendarPage
