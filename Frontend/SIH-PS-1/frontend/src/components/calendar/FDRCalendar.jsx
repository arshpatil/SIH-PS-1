import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  Clock,
  AlertTriangle,
  FileCheck2,
  CheckCircle2,
  FileText,
  Building2,
  ExternalLink,
  UploadCloud,
  ShieldCheck,
  Filter,
  Eye,
  RefreshCw,
} from 'lucide-react'
import { cn } from '../../utils/cn'

// Color styles and badges by category
const CATEGORY_STYLES = {
  MATURITY: {
    bg: 'bg-rose-50 text-rose-700 border-rose-200',
    dot: 'bg-rose-600',
    badge: 'bg-rose-100 text-rose-800 border-rose-300',
    label: 'FDR Maturity',
  },
  PETITION: {
    bg: 'bg-blue-50 text-blue-700 border-blue-200',
    dot: 'bg-blue-600',
    badge: 'bg-blue-100 text-blue-800 border-blue-300',
    label: 'Petition Submitted',
  },
  DEADLINE: {
    bg: 'bg-amber-50 text-amber-700 border-amber-200',
    dot: 'bg-amber-500',
    badge: 'bg-amber-100 text-amber-800 border-amber-300',
    label: 'Scrutiny Deadline',
  },
  RENEWAL: {
    bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dot: 'bg-emerald-600',
    badge: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    label: 'Renewal Pipeline',
  },
  VERIFICATION: {
    bg: 'bg-purple-50 text-purple-700 border-purple-200',
    dot: 'bg-purple-600',
    badge: 'bg-purple-100 text-purple-800 border-purple-300',
    label: 'Verification Pending',
  },
  DEFICIENCY: {
    bg: 'bg-orange-50 text-orange-700 border-orange-200',
    dot: 'bg-orange-600',
    badge: 'bg-orange-100 text-orange-800 border-orange-300',
    label: 'Correction Due',
  },
}

const PRIORITY_BADGES = {
  URGENT: 'bg-rose-600 text-white font-bold',
  HIGH: 'bg-amber-600 text-white font-semibold',
  MEDIUM: 'bg-blue-600 text-white font-medium',
  LOW: 'bg-slate-500 text-white font-normal',
}

const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export function FDRCalendar({
  events = [],
  loading = false,
  onRefresh,
  currentUser,
}) {
  const [currentDate, setCurrentDate] = useState(() => new Date())
  const [viewMode, setViewMode] = useState('month') // 'month' | 'week'
  const [selectedDateStr, setSelectedDateStr] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' ||
    currentUser?.role === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

  // Map events by date (YYYY-MM-DD)
  const eventsByDate = useMemo(() => {
    const map = new Map()
    for (const ev of events) {
      if (!ev.date) continue
      const dateKey = ev.date.substring(0, 10)
      if (!map.has(dateKey)) {
        map.set(dateKey, [])
      }
      map.get(dateKey).push(ev)
    }
    return map
  }, [events])

  // Events on the currently selected date
  const selectedDateEvents = useMemo(() => {
    const list = eventsByDate.get(selectedDateStr) || []
    if (categoryFilter === 'ALL' && priorityFilter === 'ALL') return list
    return list.filter((ev) => {
      if (categoryFilter !== 'ALL' && ev.category !== categoryFilter) return false
      if (priorityFilter !== 'ALL' && ev.priority !== priorityFilter) return false
      return true
    })
  }, [eventsByDate, selectedDateStr, categoryFilter, priorityFilter])

  // Calendar navigation
  const handlePrev = () => {
    if (viewMode === 'month') {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1))
    } else {
      const nextD = new Date(currentDate)
      nextD.setDate(nextD.getDate() - 7)
      setCurrentDate(nextD)
    }
  }

  const handleNext = () => {
    if (viewMode === 'month') {
      setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1))
    } else {
      const nextD = new Date(currentDate)
      nextD.setDate(nextD.getDate() + 7)
      setCurrentDate(nextD)
    }
  }

  const handleToday = () => {
    const today = new Date()
    setCurrentDate(today)
    setSelectedDateStr(
      `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    )
  }

  // Month grid calculations
  const monthDays = useMemo(() => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()

    const firstDayIndex = new Date(year, month, 1).getDay()
    const daysInCurrentMonth = new Date(year, month + 1, 0).getDate()
    const daysInPrevMonth = new Date(year, month, 0).getDate()

    const days = []

    // Previous month filler days
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const dayNum = daysInPrevMonth - i
      const d = new Date(year, month - 1, dayNum)
      const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      days.push({
        dateStr,
        dayNum,
        isCurrentMonth: false,
        dateObj: d,
      })
    }

    // Current month days
    for (let i = 1; i <= daysInCurrentMonth; i++) {
      const d = new Date(year, month, i)
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`
      days.push({
        dateStr,
        dayNum: i,
        isCurrentMonth: true,
        dateObj: d,
      })
    }

    // Next month filler days to complete grid (42 cells: 6 rows of 7)
    const remaining = 42 - days.length
    for (let i = 1; i <= remaining; i++) {
      const d = new Date(year, month + 1, i)
      const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      days.push({
        dateStr,
        dayNum: i,
        isCurrentMonth: false,
        dateObj: d,
      })
    }

    return days
  }, [currentDate])

  // Week days calculation
  const weekDays = useMemo(() => {
    const days = []
    const startOfWeek = new Date(currentDate)
    startOfWeek.setDate(currentDate.getDate() - currentDate.getDay())

    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek)
      d.setDate(startOfWeek.getDate() + i)
      const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      days.push({
        dateStr,
        dayNum: d.getDate(),
        isCurrentMonth: d.getMonth() === currentDate.getMonth(),
        dateObj: d,
      })
    }
    return days
  }, [currentDate])

  const todayStr = useMemo(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  }, [])

  return (
    <div className="space-y-6">
      {/* Top Controls & Filter Bar */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Navigation & Title */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg">
            <button
              type="button"
              onClick={handlePrev}
              className="p-1.5 hover:bg-white rounded-md text-slate-700 transition-colors shadow-2xs"
              title="Previous"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleToday}
              className="px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-white rounded-md transition-colors"
            >
              Today
            </button>
            <button
              type="button"
              onClick={handleNext}
              className="p-1.5 hover:bg-white rounded-md text-slate-700 transition-colors shadow-2xs"
              title="Next"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <CalendarIcon className="w-5 h-5 text-[#142B4A]" />
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              {MONTH_NAMES[currentDate.getMonth()]} {currentDate.getFullYear()}
            </h2>
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-semibold">
            <button
              type="button"
              onClick={() => setViewMode('month')}
              className={cn(
                'px-2.5 py-1 rounded-md transition-all',
                viewMode === 'month' ? 'bg-white text-[#142B4A] shadow-xs' : 'text-slate-600 hover:text-slate-900'
              )}
            >
              Month
            </button>
            <button
              type="button"
              onClick={() => setViewMode('week')}
              className={cn(
                'px-2.5 py-1 rounded-md transition-all',
                viewMode === 'week' ? 'bg-white text-[#142B4A] shadow-xs' : 'text-slate-600 hover:text-slate-900'
              )}
            >
              Week
            </button>
          </div>
        </div>

        {/* Filters & Actions */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Category Filter */}
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#142B4A]"
            >
              <option value="ALL">All Categories</option>
              <option value="MATURITY">FDR Maturity Dates</option>
              <option value="PETITION">Petitions Submitted</option>
              <option value="DEADLINE">Scrutiny Deadlines</option>
              <option value="RENEWAL">Renewal Pipeline</option>
              <option value="VERIFICATION">Verification Pending</option>
              <option value="DEFICIENCY">Deficiency Notices</option>
            </select>
          </div>

          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-[#142B4A]"
          >
            <option value="ALL">All Priorities</option>
            <option value="URGENT">Urgent (Overdue / ≤7d)</option>
            <option value="HIGH">High Priority</option>
            <option value="MEDIUM">Medium Priority</option>
            <option value="LOW">Low / Routine</option>
          </select>

          {/* Refresh Button */}
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="p-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-slate-700 transition-colors"
              title="Refresh Calendar Events"
            >
              <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-[#142B4A]')} />
            </button>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 sm:gap-4 flex-wrap text-2xs font-medium text-slate-600 bg-white/60 p-3 rounded-lg border border-slate-200/60">
        <span className="font-bold text-slate-700 uppercase tracking-wider text-[11px]">Legend:</span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-600" /> FDR Maturity
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-600" /> Petition Submitted
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Scrutiny Deadline (7d APH)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" /> Renewal / Receipt Due
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-purple-600" /> Verification Pending
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-orange-600" /> Deficiencies / Corrections
        </span>
      </div>

      {/* Main Calendar Area: Grid + Details Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left / Center Grid */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
          {/* Day of Week Headers */}
          <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50/75 text-center text-xs font-bold text-slate-600 py-2.5">
            {DAYS_OF_WEEK.map((d) => (
              <div key={d} className="uppercase tracking-wider">
                {d}
              </div>
            ))}
          </div>

          {/* Grid View */}
          <div className="grid grid-cols-7 auto-rows-fr divide-x divide-y divide-slate-100 bg-slate-100">
            {(viewMode === 'month' ? monthDays : weekDays).map((cell) => {
              const cellEvents = eventsByDate.get(cell.dateStr) || []
              const visibleEvents =
                categoryFilter === 'ALL' && priorityFilter === 'ALL'
                  ? cellEvents
                  : cellEvents.filter((ev) => {
                      if (categoryFilter !== 'ALL' && ev.category !== categoryFilter) return false
                      if (priorityFilter !== 'ALL' && ev.priority !== priorityFilter) return false
                      return true
                    })

              const isSelected = selectedDateStr === cell.dateStr
              const isToday = todayStr === cell.dateStr

              return (
                <div
                  key={cell.dateStr}
                  onClick={() => setSelectedDateStr(cell.dateStr)}
                  className={cn(
                    'min-h-[92px] sm:min-h-[110px] p-1.5 sm:p-2 bg-white transition-all cursor-pointer flex flex-col justify-between group hover:bg-blue-50/40',
                    !cell.isCurrentMonth && 'bg-slate-50/60 text-slate-400',
                    isSelected && 'ring-2 ring-[#142B4A] ring-inset bg-blue-50/30'
                  )}
                >
                  {/* Top: Day Number and Badges */}
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className={cn(
                        'text-xs font-bold w-6 h-6 flex items-center justify-center rounded-full transition-colors',
                        isToday
                          ? 'bg-[#142B4A] text-white shadow-xs'
                          : isSelected
                          ? 'bg-blue-100 text-[#142B4A]'
                          : cell.isCurrentMonth
                          ? 'text-slate-800'
                          : 'text-slate-400'
                      )}
                    >
                      {cell.dayNum}
                    </span>

                    {visibleEvents.length > 0 && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-700">
                        {visibleEvents.length}
                      </span>
                    )}
                  </div>

                  {/* Middle: Event preview pills */}
                  <div className="space-y-1 flex-1 overflow-hidden">
                    {visibleEvents.slice(0, 2).map((ev) => {
                      const style = CATEGORY_STYLES[ev.category] || CATEGORY_STYLES.MATURITY
                      return (
                        <div
                          key={ev.id}
                          className={cn(
                            'text-[10px] sm:text-[11px] font-medium px-1.5 py-0.5 rounded truncate border leading-tight flex items-center gap-1',
                            style.bg
                          )}
                          title={`${ev.title} (${ev.priority})`}
                        >
                          <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', style.dot)} />
                          <span className="truncate">{ev.title}</span>
                        </div>
                      )
                    })}

                    {visibleEvents.length > 2 && (
                      <div className="text-[10px] font-semibold text-slate-500 pl-1">
                        +{visibleEvents.length - 2} more
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Selected Date Event Details Panel */}
        <div className="lg:col-span-4 bg-white rounded-xl shadow-xs border border-slate-200 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <p className="text-2xs font-bold text-slate-400 uppercase tracking-wider">
                Selected Date Schedule
              </p>
              <h3 className="text-base font-bold text-slate-900">
                {new Date(selectedDateStr + 'T00:00:00').toLocaleDateString('en-US', {
                  weekday: 'short',
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </h3>
            </div>
            {selectedDateStr === todayStr && (
              <span className="px-2 py-0.5 rounded-full text-2xs font-bold bg-blue-100 text-blue-800">
                Today
              </span>
            )}
          </div>

          {/* Events on selected date */}
          {selectedDateEvents.length === 0 ? (
            <div className="text-center py-10 px-4">
              <CalendarIcon className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-xs font-semibold text-slate-700">No scheduled events</p>
              <p className="text-2xs text-slate-500 mt-0.5">
                There are no FDR maturities, petitions, or scrutiny deadlines on this date.
              </p>
            </div>
          ) : (
            <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
              {selectedDateEvents.map((ev) => {
                const style = CATEGORY_STYLES[ev.category] || CATEGORY_STYLES.MATURITY
                const priorityClass = PRIORITY_BADGES[ev.priority] || PRIORITY_BADGES.MEDIUM

                return (
                  <div
                    key={ev.id}
                    className="p-3.5 rounded-xl border border-slate-200/90 bg-slate-50/60 hover:bg-slate-50 transition-all space-y-2.5 text-xs shadow-2xs"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2">
                      <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-bold border', style.badge)}>
                        {style.label}
                      </span>
                      <span className={cn('px-1.5 py-0.5 rounded text-[10px] tracking-wide', priorityClass)}>
                        {ev.priority}
                      </span>
                    </div>

                    {/* Title & Description */}
                    <div>
                      <h4 className="font-bold text-slate-900 leading-snug">{ev.title}</h4>
                      <p className="text-slate-600 text-2xs leading-relaxed mt-1">
                        {ev.description}
                      </p>
                    </div>

                    {/* Meta Fields */}
                    <div className="space-y-1 text-2xs text-slate-500 pt-1 border-t border-slate-200/60">
                      {ev.institution_name && (
                        <div className="flex items-center gap-1.5 truncate">
                          <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span className="truncate">{ev.institution_name}</span>
                        </div>
                      )}
                      {ev.fdr_number && (
                        <div className="flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>FDR No: <strong className="text-slate-700">{ev.fdr_number}</strong></span>
                        </div>
                      )}
                      {ev.provisional_maturity_date && (
                        <div className="flex items-center gap-1.5 text-amber-700 bg-amber-50 px-2 py-1 rounded">
                          <Clock className="w-3 h-3 text-amber-600 shrink-0" />
                          <span>Provisional Maturity: {ev.provisional_maturity_date} (Awaiting Verification)</span>
                        </div>
                      )}
                      {ev.status && (
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-slate-600">Status:</span>
                          <span className="text-slate-800 font-medium">{ev.status}</span>
                        </div>
                      )}
                    </div>

                    {/* Authorized Action Buttons */}
                    <div className="pt-2 flex items-center gap-2 flex-wrap">
                      {ev.fdr_id && (
                        <Link
                          to={`/fdrs/${ev.fdr_id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg text-2xs font-semibold text-slate-700 shadow-2xs transition-colors"
                        >
                          <Eye className="w-3 h-3" />
                          View FDR
                        </Link>
                      )}

                      {/* Case 1: Institution has Approved Renewal Awaiting Receipt */}
                      {!isOfficerOrAdmin && ev.type === 'RENEWAL_APPROVED_AWAITING_RECEIPT' && ev.fdr_id && (
                        <Link
                          to={`/fdrs/${ev.fdr_id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-2xs font-bold shadow-xs transition-colors"
                        >
                          <UploadCloud className="w-3 h-3" />
                          Upload Renewed Receipt
                        </Link>
                      )}

                      {/* Case 2: Institution has Deficiency to resolve */}
                      {!isOfficerOrAdmin && ev.type === 'DOCUMENTS_REQUIRED' && (
                        <Link
                          to="/requests"
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-2xs font-bold shadow-xs transition-colors"
                        >
                          <FileCheck2 className="w-3 h-3" />
                          Submit Documents
                        </Link>
                      )}

                      {/* Case 3: Officer/Admin has Receipt Awaiting Verification */}
                      {isOfficerOrAdmin && ev.type === 'RENEWAL_PENDING_VERIFICATION' && ev.fdr_id && (
                        <Link
                          to={`/fdrs/${ev.fdr_id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-2xs font-bold shadow-xs transition-colors"
                        >
                          <ShieldCheck className="w-3 h-3" />
                          Verify & Endorse
                        </Link>
                      )}

                      {/* Case 4: Officer/Admin has Petition Review Deadline */}
                      {isOfficerOrAdmin && ev.type === 'PETITION_REVIEW_DEADLINE' && (
                        <Link
                          to="/requests"
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#142B4A] hover:bg-[#0E1E34] text-white rounded-lg text-2xs font-bold shadow-xs transition-colors"
                        >
                          <FileCheck2 className="w-3 h-3" />
                          Scrutinize Petition
                        </Link>
                      )}

                      {/* Case 5: Institution needs to file renewal petition (expiring soon) */}
                      {!isOfficerOrAdmin && ev.type === 'FDR_MATURITY' && ev.days_remaining <= 30 && ev.fdr_id && (
                        <Link
                          to={`/fdrs/${ev.fdr_id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-2xs font-bold shadow-xs transition-colors"
                        >
                          <FileText className="w-3 h-3" />
                          File Renewal Petition
                        </Link>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FDRCalendar
