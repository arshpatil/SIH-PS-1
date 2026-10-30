import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  Search,
  Eye,
  Download,
  RefreshCw,
  Send,
  UserCheck,
  ShieldCheck,
  CalendarClock,
  Inbox,
  FileCheck2,
  Sparkles,
  ArrowRight,
  Filter,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { Badge } from '../components/ui/Badge'
import { RequestStatusBadge } from '../components/requests/RequestStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { formatDate } from '../utils/dateUtils'
import { formatCurrency } from '../utils/formatters'
import { useApp } from '../context/AppContext'
import { dashboardService } from '../services/dashboardService'
import { requestService } from '../services/requestService'

export function PriorityBadge({ priority, reason }) {
  const p = (priority || 'LOW').toUpperCase()
  if (p === 'CRITICAL' || p === 'URGENT') {
    return (
      <span
        title={reason || 'FDR maturity within 7 days — Critical Statutory Priority'}
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-extrabold bg-rose-100 text-rose-800 border border-rose-300 shadow-2xs"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
        CRITICAL
      </span>
    )
  }
  if (p === 'HIGH') {
    return (
      <span
        title={reason || 'FDR maturity within 15 days or Overdue — High Priority'}
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-bold bg-amber-100 text-amber-900 border border-amber-300"
      >
        HIGH
      </span>
    )
  }
  if (p === 'MEDIUM') {
    return (
      <span
        title={reason || 'Standard scrutiny queue'}
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-blue-100 text-blue-800 border border-blue-200"
      >
        MEDIUM
      </span>
    )
  }
  return (
    <span
      title={reason || 'Sufficient time remaining'}
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-medium bg-slate-100 text-slate-700 border border-slate-200"
    >
      LOW
    </span>
  )
}

export function OfficerDashboardPage() {
  const { currentUser, showToast } = useApp()

  const [loading, setLoading] = useState(true)
  const [dashboardData, setDashboardData] = useState(null)
  const [activeTab, setActiveTab] = useState('assigned') // 'assigned' | 'claimable'

  // Filter state for assigned cases
  const [categoryFilter, setCategoryFilter] = useState('ALL') // 'ALL' | 'CRITICAL' | 'HIGH' | 'PENDING' | 'OVERDUE' | 'COMPLETED'
  const [sortOrder, setSortOrder] = useState('PRIORITY') // 'PRIORITY' | 'MATURITY' | 'NEWEST' | 'OLDEST'
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')

  // Case Scrutiny Modal state
  const [selectedCase, setSelectedCase] = useState(null)
  const [detailedCase, setDetailedCase] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionStatus, setActionStatus] = useState('')
  const [actionRemarks, setActionRemarks] = useState('')
  const [isSubmittingAction, setIsSubmittingAction] = useState(false)
  const [isClaiming, setIsClaiming] = useState(false)

  // Load officer dashboard data
  const loadDashboard = useCallback(async (isRefresh = false) => {
    if (!isRefresh) setLoading(true)
    try {
      const data = await dashboardService.getOfficerDashboard()
      if (data) {
        setDashboardData(data)
      }
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to load officer dashboard data', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  // Open case scrutiny modal with full details
  const handleOpenCase = async (c) => {
    setSelectedCase(c)
    setDetailedCase(null)
    setActionStatus('')
    setActionRemarks('')
    setDetailLoading(true)

    const rawId = c.raw_id || c.id
    try {
      const detail = await requestService.getRequestDetail(rawId)
      if (detail) {
        setDetailedCase(detail)
      } else {
        setDetailedCase(c)
      }
    } catch {
      setDetailedCase(c)
    } finally {
      setDetailLoading(false)
    }
  }

  // Handle officer processing action
  const handleSubmitDecision = async (e) => {
    e.preventDefault()
    if (!actionStatus) {
      showToast('Please select a decision status.', 'error')
      return
    }

    if ((actionStatus === 'Documents Required' || actionStatus === 'Rejected') && !actionRemarks.trim()) {
      showToast(`Remarks are mandatory when issuing '${actionStatus}'.`, 'error')
      return
    }

    setIsSubmittingAction(true)
    const rawId = selectedCase.raw_id || selectedCase.id

    if (actionStatus === 'VERIFY_RENEWAL') {
      try {
        await requestService.verifyRenewal(rawId, {
          decision: 'VERIFIED',
          remarks: actionRemarks.trim() || 'Verified renewed deposit receipt and extended maturity term.',
        })
        showToast(`Renewal verified and maturity extended for petition ${selectedCase.id}.`, 'success')
        setSelectedCase(null)
        loadDashboard(true)
        return
      } catch (err) {
        showToast(err.response?.data?.error || err.message || 'Failed to verify renewal', 'error')
        return
      } finally {
        setIsSubmittingAction(false)
      }
    }

    try {
      await requestService.updateRequestStatus(rawId, actionStatus, actionRemarks.trim())
      showToast(`Decision '${actionStatus}' recorded for petition ${selectedCase.id}.`, 'success')
      setSelectedCase(null)
      loadDashboard(true)
    } catch (err) {
      showToast(err.response?.data?.error || err.message || 'Failed to record decision', 'error')
    } finally {
      setIsSubmittingAction(false)
    }
  }

  // Handle claiming an unassigned case
  const handleClaimCase = async (caseItem) => {
    setIsClaiming(true)
    const rawId = caseItem.raw_id || caseItem.id
    try {
      await requestService.claimRequest(rawId)
      showToast(`Case ${caseItem.id} claimed successfully and added to your assigned workload!`, 'success')
      loadDashboard(true)
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to claim case', 'error')
    } finally {
      setIsClaiming(false)
    }
  }

  // Download attachment
  const handleDownload = async (reqId, docName) => {
    try {
      await requestService.downloadAttachment(reqId, docName || 'supporting_document.pdf')
      showToast('Document downloaded securely.', 'success')
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to download attachment', 'error')
    }
  }

  const workload = dashboardData?.workload_overview || {}
  const assignedCases = dashboardData?.assigned_cases || []
  const claimableCases = dashboardData?.claimable_cases || []

  // Smart category counts
  const categoryCounts = useMemo(() => {
    let critical = 0
    let high = 0
    let pending = 0
    let overdue = 0
    let completed = 0

    assignedCases.forEach((c) => {
      const p = (c.priority || 'LOW').toUpperCase()
      const st = (c.status || '').toLowerCase().trim()
      const isOverdue = Boolean(c.is_overdue || c.isOverdue)

      if (p === 'CRITICAL' || p === 'URGENT') critical++
      if (p === 'HIGH') high++
      if (['submitted', 'under review', 'resubmitted / awaiting review'].includes(st)) pending++
      if (isOverdue) overdue++
      if (['approved', 'rejected', 'closed'].includes(st)) completed++
    })

    return { critical, high, pending, overdue, completed }
  }, [assignedCases])

  // Filtered and sorted assigned cases
  const filteredAssignedCases = useMemo(() => {
    const list = assignedCases.filter((c) => {
      const q = searchQuery.toLowerCase().trim()
      const reqId = String(c.id || '').toLowerCase()
      const fdrNum = String(c.fdrNumber || c.fdr_number || '').toLowerCase()
      const bankName = String(c.bankName || c.bank_name || '').toLowerCase()
      const instName = String(c.institutionName || c.institution_name || '').toLowerCase()

      const matchesSearch =
        !q || reqId.includes(q) || fdrNum.includes(q) || bankName.includes(q) || instName.includes(q)

      const matchesType = typeFilter === 'ALL' || c.requestType === typeFilter || c.request_type === typeFilter

      const currentStatus = (c.status || '').toLowerCase().trim()
      const matchesStatus =
        statusFilter === 'ALL' || currentStatus === statusFilter.toLowerCase().trim()

      const currentPriority = (c.priority || 'LOW').toUpperCase()
      const matchesPriority =
        priorityFilter === 'ALL' || currentPriority === priorityFilter.toUpperCase()

      // Category Filter (Requirement 3)
      let matchesCategory = true
      if (categoryFilter === 'CRITICAL') {
        matchesCategory = currentPriority === 'CRITICAL' || currentPriority === 'URGENT'
      } else if (categoryFilter === 'HIGH') {
        matchesCategory = currentPriority === 'HIGH'
      } else if (categoryFilter === 'PENDING') {
        matchesCategory = ['submitted', 'under review', 'resubmitted / awaiting review'].includes(currentStatus)
      } else if (categoryFilter === 'OVERDUE') {
        matchesCategory = Boolean(c.is_overdue || c.isOverdue)
      } else if (categoryFilter === 'COMPLETED') {
        matchesCategory = ['approved', 'rejected', 'closed'].includes(currentStatus)
      }

      return matchesSearch && matchesType && matchesStatus && matchesPriority && matchesCategory
    })

    // Dynamic sorting
    const priorityWeight = { CRITICAL: 0, URGENT: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
    return list.sort((a, b) => {
      if (sortOrder === 'PRIORITY') {
        const pa = priorityWeight[(a.priority || 'LOW').toUpperCase()] ?? 4
        const pb = priorityWeight[(b.priority || 'LOW').toUpperCase()] ?? 4
        if (pa !== pb) return pa - pb
        // Secondary sort: days remaining ascending
        return (a.days_remaining ?? 9999) - (b.days_remaining ?? 9999)
      }
      if (sortOrder === 'MATURITY') {
        return (a.days_remaining ?? 9999) - (b.days_remaining ?? 9999)
      }
      if (sortOrder === 'NEWEST') {
        return new Date(b.created_at || b.submissionDate || 0) - new Date(a.created_at || a.submissionDate || 0)
      }
      if (sortOrder === 'OLDEST') {
        return new Date(a.created_at || a.submissionDate || 0) - new Date(b.created_at || b.submissionDate || 0)
      }
      return 0
    })
  }, [assignedCases, searchQuery, typeFilter, statusFilter, priorityFilter, categoryFilter, sortOrder])

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Officer Welcome & Bureau Banner */}
      <div className="bg-[#0B1B3D] border border-[#1E3A63] rounded-xl p-5 sm:p-6 text-white shadow-subtle relative overflow-hidden">
        <div className="absolute right-0 top-0 translate-x-12 -translate-y-8 w-72 h-72 bg-gradient-to-br from-white/10 to-transparent rounded-full blur-2xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-white/10 text-amber-300 text-2xs font-bold uppercase tracking-wider border border-white/15">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
              <span>AICTE Desk Scrutiny Officer Workbench</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Welcome, {currentUser?.full_name || 'Scrutiny Officer'}
            </h1>
            <p className="text-slate-300 text-xs sm:text-sm leading-relaxed">
              Review and scrutinize statutory renewal and lien release petitions, inspect banking covenants, verify supporting documents, and issue regulatory decisions under AICTE Approval Process Handbook (APH) regulations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <Button
              variant="secondary"
              size="md"
              className="bg-white/10 hover:bg-white/20 text-white border-white/20 hover:border-white/30"
              icon={RefreshCw}
              onClick={() => loadDashboard(true)}
            >
              Refresh Workload
            </Button>
            <Link to="/requests">
              <Button
                variant="warning"
                size="md"
                className="font-semibold shadow-xs"
              >
                All Bureau Petitions
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Urgent Warning if Overdue or Approaching Maturity */}
      {workload.overdue_cases > 0 && (
        <div className="flex items-center justify-between p-3.5 sm:p-4 bg-rose-50 rounded-xl border border-rose-300 text-rose-950 text-xs sm:text-sm shadow-2xs">
          <div className="flex items-start sm:items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5 sm:mt-0" />
            <div>
              <span className="font-bold">Overdue Caseload Notice: </span>
              <span>
                You have <span className="font-bold underline">{workload.overdue_cases} assigned petition(s)</span> pending review for more than 14 days. Prompt action is required to avoid regulatory SLA breaches.
              </span>
            </div>
          </div>
          <button
            onClick={() => {
              setActiveTab('assigned')
              setPriorityFilter('URGENT')
            }}
            className="shrink-0 ml-4 font-semibold text-rose-800 hover:text-rose-950 underline text-xs whitespace-nowrap"
          >
            Filter Urgent Cases &rarr;
          </button>
        </div>
      )}

      {/* SECTION A: Personal Workload Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4.5">
        {/* Card 1: Awaiting Review */}
        <Card className="p-4 sm:p-5 flex flex-col justify-between hover:border-slate-300 hover:shadow-subtle transition-all">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Awaiting Scrutiny
              </span>
              <span className="text-2xl sm:text-3xl font-bold text-slate-900 mt-1 block tabular-nums">
                {workload.assigned_awaiting_review ?? 0}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200/60">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Submitted & Under Review</span>
            <span className="font-semibold text-blue-700">Action Required</span>
          </div>
        </Card>

        {/* Card 2: Newly Assigned */}
        <Card className="p-4 sm:p-5 flex flex-col justify-between hover:border-slate-300 hover:shadow-subtle transition-all">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Newly Assigned (7d)
              </span>
              <span className="text-2xl sm:text-3xl font-bold text-slate-900 mt-1 block tabular-nums">
                {workload.newly_assigned ?? 0}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200/60">
              <Inbox className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Allocated recently</span>
            <span className="font-semibold text-indigo-700">New Queue</span>
          </div>
        </Card>

        {/* Card 3: Resubmitted / Corrections */}
        <Card className="p-4 sm:p-5 flex flex-col justify-between hover:border-slate-300 hover:shadow-subtle transition-all">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Resubmitted / Corrections
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl sm:text-3xl font-bold text-slate-900 tabular-nums">
                  {workload.resubmitted_awaiting_review ?? 0}
                </span>
                <span className="text-2xs text-slate-400">
                  ({workload.awaiting_institution_corrections ?? 0} at college)
                </span>
              </div>
            </div>
            <div className="p-2.5 rounded-lg bg-purple-50 text-purple-700 border border-purple-200/60">
              <FileCheck2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Revised documents uploaded</span>
            <span className="font-semibold text-purple-700">Review Ready</span>
          </div>
        </Card>

        {/* Card 4: Approaching Maturity & Completed */}
        <Card className="p-4 sm:p-5 flex flex-col justify-between hover:border-slate-300 hover:shadow-subtle transition-all">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Expiring &lt;= 30 Days
              </span>
              <span className="text-2xl sm:text-3xl font-bold text-slate-900 mt-1 block tabular-nums">
                {workload.approaching_maturity ?? 0}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-amber-50 text-amber-700 border border-amber-200/60">
              <CalendarClock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Resolved: {workload.approved_cases ?? 0} App / {workload.rejected_cases ?? 0} Rej</span>
            <span className="font-semibold text-amber-800">Critical Term</span>
          </div>
        </Card>
      </div>

      {/* Tabs for Assigned Cases vs Claimable Unassigned Cases */}
      <div className="flex border-b border-slate-200 gap-4">
        <button
          onClick={() => setActiveTab('assigned')}
          className={`pb-3 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'assigned'
              ? 'border-navy-700 text-navy-800'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          <span>My Assigned Cases ({assignedCases.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('claimable')}
          className={`pb-3 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'claimable'
              ? 'border-navy-700 text-navy-800'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Inbox className="w-4 h-4" />
          <span>Claimable Unassigned Petitions ({claimableCases.length})</span>
        </button>
      </div>

      {/* SECTION B: My Assigned Cases */}
      {activeTab === 'assigned' && (
        <Card className="p-4 sm:p-5">
          <CardHeader
            title="My Assigned Scrutiny Cases"
            subtitle="Petitions allocated to your desk for documentary verification and regulatory clearance"
            icon={UserCheck}
          />

          {/* Workload Category Filters (Requirement 3) */}
          <div className="flex flex-wrap items-center gap-1.5 pt-3 pb-2 border-b border-slate-100">
            <button
              type="button"
              onClick={() => setCategoryFilter('ALL')}
              className={`px-3 py-1.5 rounded-lg text-2xs font-bold transition-all flex items-center gap-1.5 ${
                categoryFilter === 'ALL'
                  ? 'bg-[#0B1B3D] text-white shadow-xs'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <span>My Assigned Petitions</span>
              <span className={`px-1.5 py-0.2 rounded-full font-mono text-3xs ${
                categoryFilter === 'ALL' ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-800'
              }`}>
                {assignedCases.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter('CRITICAL')}
              className={`px-3 py-1.5 rounded-lg text-2xs font-bold transition-all flex items-center gap-1.5 ${
                categoryFilter === 'CRITICAL'
                  ? 'bg-rose-700 text-white shadow-xs'
                  : 'bg-rose-50 text-rose-800 hover:bg-rose-100 border border-rose-200/80'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
              <span>Critical Cases (&le;7d)</span>
              <span className={`px-1.5 py-0.2 rounded-full font-mono text-3xs ${
                categoryFilter === 'CRITICAL' ? 'bg-white/20 text-white' : 'bg-rose-200 text-rose-900'
              }`}>
                {categoryCounts.critical}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter('HIGH')}
              className={`px-3 py-1.5 rounded-lg text-2xs font-bold transition-all flex items-center gap-1.5 ${
                categoryFilter === 'HIGH'
                  ? 'bg-amber-600 text-white shadow-xs'
                  : 'bg-amber-50 text-amber-900 hover:bg-amber-100 border border-amber-200/80'
              }`}
            >
              <span>High Priority (&le;15d)</span>
              <span className={`px-1.5 py-0.2 rounded-full font-mono text-3xs ${
                categoryFilter === 'HIGH' ? 'bg-white/20 text-white' : 'bg-amber-200 text-amber-900'
              }`}>
                {categoryCounts.high}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter('PENDING')}
              className={`px-3 py-1.5 rounded-lg text-2xs font-bold transition-all flex items-center gap-1.5 ${
                categoryFilter === 'PENDING'
                  ? 'bg-blue-700 text-white shadow-xs'
                  : 'bg-blue-50 text-blue-800 hover:bg-blue-100 border border-blue-200/80'
              }`}
            >
              <span>Pending Review</span>
              <span className={`px-1.5 py-0.2 rounded-full font-mono text-3xs ${
                categoryFilter === 'PENDING' ? 'bg-white/20 text-white' : 'bg-blue-200 text-blue-900'
              }`}>
                {categoryCounts.pending}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter('OVERDUE')}
              className={`px-3 py-1.5 rounded-lg text-2xs font-bold transition-all flex items-center gap-1.5 ${
                categoryFilter === 'OVERDUE'
                  ? 'bg-purple-700 text-white shadow-xs'
                  : 'bg-purple-50 text-purple-800 hover:bg-purple-100 border border-purple-200/80'
              }`}
            >
              <span>Overdue (&gt;14d)</span>
              <span className={`px-1.5 py-0.2 rounded-full font-mono text-3xs ${
                categoryFilter === 'OVERDUE' ? 'bg-white/20 text-white' : 'bg-purple-200 text-purple-900'
              }`}>
                {categoryCounts.overdue}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setCategoryFilter('COMPLETED')}
              className={`px-3 py-1.5 rounded-lg text-2xs font-bold transition-all flex items-center gap-1.5 ${
                categoryFilter === 'COMPLETED'
                  ? 'bg-emerald-700 text-white shadow-xs'
                  : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200/80'
              }`}
            >
              <span>Completed Cases</span>
              <span className={`px-1.5 py-0.2 rounded-full font-mono text-3xs ${
                categoryFilter === 'COMPLETED' ? 'bg-white/20 text-white' : 'bg-emerald-200 text-emerald-900'
              }`}>
                {categoryCounts.completed}
              </span>
            </button>
          </div>

          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 my-3.5">
            <div className="relative flex-1">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search by ID, FDR #, bank, or institution..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8.5 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20 focus:border-[#142B4A] bg-white text-slate-900"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              >
                <option value="PRIORITY">Sort: Priority (Critical &rarr; Low)</option>
                <option value="MATURITY">Sort: Days to Maturity (Asc)</option>
                <option value="NEWEST">Sort: Newest Submissions</option>
                <option value="OLDEST">Sort: Oldest Submissions</option>
              </select>

              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              >
                <option value="ALL">All Request Types</option>
                <option value="Renewal">Renewal Only</option>
                <option value="Release">Release Only</option>
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              >
                <option value="ALL">All Statuses</option>
                <option value="Submitted">Submitted</option>
                <option value="Under Review">Under Review</option>
                <option value="Documents Required">Documents Required</option>
                <option value="Resubmitted / Awaiting Review">Resubmitted</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
              </select>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              >
                <option value="ALL">All Priorities</option>
                <option value="CRITICAL">Critical Only</option>
                <option value="HIGH">High Priority</option>
                <option value="MEDIUM">Medium Priority</option>
                <option value="LOW">Low Priority</option>
              </select>
            </div>
          </div>

          {/* Cases Table */}
          {loading ? (
            <div className="py-12 text-center text-xs text-slate-500">Loading assigned cases...</div>
          ) : filteredAssignedCases.length === 0 ? (
            <EmptyState
              title="No assigned cases matching your filters"
              description="Check the Claimable Unassigned Petitions tab to pick up newly submitted petitions."
            />
          ) : (
            <div className="overflow-x-auto -mx-4 sm:mx-0">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-2xs uppercase text-slate-500 font-semibold bg-slate-50/70">
                    <th className="py-2.5 px-3">Petition ID</th>
                    <th className="py-2.5 px-3">Institution</th>
                    <th className="py-2.5 px-3">FDR Number</th>
                    <th className="py-2.5 px-3">Maturity / Days</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Priority</th>
                    <th className="py-2.5 px-3">Submitted</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredAssignedCases.map((c) => {
                    const days = c.daysRemaining ?? c.days_remaining
                    const isMaturityUrgent = days !== null && days !== undefined && days <= 30

                    return (
                      <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-bold text-navy-800">
                          {c.id}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="font-semibold text-slate-900 block truncate max-w-[180px]">
                            {c.institutionName || c.institution_name || 'Technical College'}
                          </span>
                          <span className="text-2xs text-slate-400 font-mono">
                            {c.institutionCode || c.institution_code || 'ID: 1-439281'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-700">
                          <div>{c.fdrNumber || c.fdr_number}</div>
                          <div className="text-2xs text-slate-400">{c.bankName || c.bank_name}</div>
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-medium text-slate-800 tabular-nums">
                            {formatDate(c.maturityDate || c.maturity_date)}
                          </div>
                          {days !== null && days !== undefined ? (
                            <span
                              className={`text-2xs font-semibold ${
                                isMaturityUrgent ? 'text-rose-700' : 'text-slate-500'
                              }`}
                            >
                              {days < 0 ? `${Math.abs(days)}d Overdue` : `${days} days left`}
                            </span>
                          ) : (
                            <span className="text-2xs text-slate-400">Term N/A</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-2xs font-semibold ${
                              c.requestType === 'Release' || c.request_type === 'Release'
                                ? 'bg-purple-50 text-purple-800 border border-purple-200'
                                : 'bg-blue-50 text-blue-800 border border-blue-200'
                            }`}
                          >
                            {c.requestType || c.request_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <RequestStatusBadge status={c.status} size="sm" />
                        </td>
                        <td className="py-2.5 px-3">
                          <PriorityBadge priority={c.priority} />
                        </td>
                        <td className="py-2.5 px-3 text-2xs text-slate-500 tabular-nums">
                          {formatDate(c.submissionDate || c.created_at)}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <Button
                            variant="primary"
                            size="xs"
                            icon={Eye}
                            onClick={() => handleOpenCase(c)}
                          >
                            Scrutinize
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* SECTION C: Claimable Unassigned Petitions */}
      {activeTab === 'claimable' && (
        <Card className="p-4 sm:p-5">
          <CardHeader
            title="Available Unassigned Petitions"
            subtitle="Statutory requests submitted by institutions that have not yet been assigned to a scrutiny officer"
            icon={Inbox}
          />

          {claimableCases.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500">
              <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
              <p className="font-semibold text-slate-800">Assignment Queue is Clear</p>
              <p className="text-slate-400 mt-0.5">All submitted statutory petitions are currently assigned to officers.</p>
            </div>
          ) : (
            <div className="overflow-x-auto mt-3 -mx-4 sm:mx-0">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-2xs uppercase text-slate-500 font-semibold bg-slate-50/70">
                    <th className="py-2.5 px-3">Petition ID</th>
                    <th className="py-2.5 px-3">Institution</th>
                    <th className="py-2.5 px-3">FDR Number</th>
                    <th className="py-2.5 px-3">Amount</th>
                    <th className="py-2.5 px-3">Maturity Date</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Priority</th>
                    <th className="py-2.5 px-3">Submitted</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {claimableCases.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-2.5 px-3 font-mono font-bold text-navy-800">
                        {c.id}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-semibold text-slate-900 block truncate max-w-[200px]">
                          {c.institutionName || c.institution_name || 'Technical College'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-700">
                        {c.fdrNumber || c.fdr_number}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-slate-900 tabular-nums">
                        {formatCurrency(c.depositAmount || c.deposit_amount)}
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="tabular-nums">{formatDate(c.maturityDate || c.maturity_date)}</div>
                        <span className="text-2xs text-slate-500">
                          {c.daysRemaining !== null && c.daysRemaining !== undefined
                            ? `${c.daysRemaining} days left`
                            : ''}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="inline-block px-2 py-0.5 rounded text-2xs font-semibold bg-blue-50 text-blue-800 border border-blue-200">
                          {c.requestType || c.request_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <PriorityBadge priority={c.priority} />
                      </td>
                      <td className="py-2.5 px-3 text-2xs text-slate-500 tabular-nums">
                        {formatDate(c.submissionDate || c.created_at)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Button
                          variant="secondary"
                          size="xs"
                          loading={isClaiming}
                          onClick={() => handleClaimCase(c)}
                        >
                          Claim Case
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* SECTION D: Case Scrutiny & Decision Modal */}
      {selectedCase && (
        <Modal
          isOpen={Boolean(selectedCase)}
          onClose={() => setSelectedCase(null)}
          title={`Scrutinize Petition: ${selectedCase.id}`}
          subtitle={`${selectedCase.requestType || selectedCase.request_type} Petition • FDR ${selectedCase.fdrNumber || selectedCase.fdr_number}`}
          maxWidth="max-w-3xl"
        >
          {detailLoading ? (
            <div className="py-12 text-center text-xs text-slate-500">
              Loading petition dossier and regulatory history...
            </div>
          ) : (
            <div className="space-y-4 text-xs text-slate-700">
              {/* Summary Dossier Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <span className="text-2xs text-slate-500 uppercase tracking-wider block font-semibold">
                    Institution
                  </span>
                  <span className="font-semibold text-slate-900 block truncate mt-0.5">
                    {detailedCase?.institutionName || detailedCase?.institution_name || 'Technical College'}
                  </span>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase tracking-wider block font-semibold">
                    FDR Reference
                  </span>
                  <span className="font-mono font-bold text-slate-900 block mt-0.5">
                    {detailedCase?.fdrNumber || detailedCase?.fdr_number}
                  </span>
                  <span className="text-2xs text-slate-400">{detailedCase?.bankName || detailedCase?.bank_name}</span>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase tracking-wider block font-semibold">
                    Deposit Amount
                  </span>
                  <span className="font-bold text-slate-900 block mt-0.5 tabular-nums">
                    {formatCurrency(detailedCase?.depositAmount || detailedCase?.deposit_amount)}
                  </span>
                </div>
                <div>
                  <span className="text-2xs text-slate-500 uppercase tracking-wider block font-semibold">
                    Maturity Term
                  </span>
                  <span className="font-semibold text-slate-900 block mt-0.5 tabular-nums">
                    {formatDate(detailedCase?.maturityDate || detailedCase?.maturity_date)}
                  </span>
                  <div className="mt-1">
                    <PriorityBadge priority={detailedCase?.priority} />
                  </div>
                </div>
              </div>

              {/* Dynamic Priority Justification Alert */}
              <div
                className={`p-3 rounded-xl border flex items-start gap-2.5 text-xs ${
                  detailedCase?.priority === 'CRITICAL' || detailedCase?.priority === 'URGENT'
                    ? 'bg-rose-50 border-rose-300 text-rose-950'
                    : detailedCase?.priority === 'HIGH'
                    ? 'bg-amber-50 border-amber-300 text-amber-950'
                    : 'bg-slate-50 border-slate-200 text-slate-800'
                }`}
              >
                <AlertCircle
                  className={`w-4 h-4 shrink-0 mt-0.5 ${
                    detailedCase?.priority === 'CRITICAL' || detailedCase?.priority === 'URGENT'
                      ? 'text-rose-600'
                      : detailedCase?.priority === 'HIGH'
                      ? 'text-amber-600'
                      : 'text-slate-500'
                  }`}
                />
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold uppercase tracking-wider text-2xs">
                      SLA Dynamic Priority: {detailedCase?.priority}
                    </span>
                    <PriorityBadge priority={detailedCase?.priority} />
                  </div>
                  <p className="text-2xs leading-relaxed">
                    {detailedCase?.priority_reason ||
                      detailedCase?.priorityReason ||
                      'Assigned under standard regulatory scrutiny turnaround.'}
                  </p>
                </div>
              </div>

              {/* Justification Provided by College */}
              <div>
                <span className="text-2xs font-semibold uppercase text-slate-600 block mb-1">
                  Institutional Justification & Request Reason:
                </span>
                <div className="p-3 bg-white rounded-lg border border-slate-200 text-slate-800 leading-relaxed font-sans text-xs">
                  {detailedCase?.reason || 'No justification text provided by institution.'}
                </div>
              </div>

              {/* Supporting Document & Attachment */}
              <div className="p-3 bg-blue-50/60 rounded-xl border border-blue-200 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <FileText className="w-6 h-6 text-navy-700 shrink-0" />
                  <div>
                    <span className="font-semibold text-navy-950 block text-xs">
                      {detailedCase?.supportingDocument || detailedCase?.supporting_document || 'Supporting_Application.pdf'}
                    </span>
                    <span className="text-2xs text-slate-500">
                      Mandatory statutory application and endorsement file
                    </span>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="xs"
                  icon={Download}
                  onClick={() =>
                    handleDownload(
                      detailedCase?.raw_id || detailedCase?.id,
                      detailedCase?.supportingDocument || detailedCase?.supporting_document
                    )
                  }
                >
                  Download File
                </Button>
              </div>

              {/* Submitted Renewed FDR Deposit Details (Awaiting Officer Verification) */}
              {(detailedCase?.renewal_fdr_number || detailedCase?.renewal_document || detailedCase?.status === 'Pending Verification') && (
                <div className="p-3.5 rounded-xl bg-amber-50/80 border border-amber-300 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-700" />
                      <span className="text-xs font-bold text-amber-950 uppercase tracking-wide">
                        Submitted Renewed Deposit (Awaiting Verification)
                      </span>
                    </div>
                    <Badge variant="warning" size="xs">
                      Receipt Uploaded
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-2xs">
                    <div className="p-2 rounded bg-white border border-amber-200">
                      <span className="text-slate-500 block">Renewed FDR #</span>
                      <span className="font-bold text-slate-900 font-mono">
                        {detailedCase?.renewal_fdr_number || 'N/A'}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-white border border-amber-200">
                      <span className="text-slate-500 block">New Issue Date</span>
                      <span className="font-semibold text-slate-800">
                        {formatDate(detailedCase?.renewal_issue_date)}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-white border border-amber-200">
                      <span className="text-slate-500 block">New Maturity Date</span>
                      <span className="font-bold text-emerald-800">
                        {formatDate(detailedCase?.renewal_maturity_date)}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-white border border-amber-200">
                      <span className="text-slate-500 block">Renewed Amount</span>
                      <span className="font-bold text-slate-900 font-mono">
                        {formatCurrency(detailedCase?.renewal_amount)}
                      </span>
                    </div>
                  </div>

                  {detailedCase?.renewal_remarks && (
                    <div className="text-2xs text-slate-700 bg-white/70 p-2 rounded border border-amber-200">
                      <span className="font-semibold text-slate-900">Institution Notes: </span>
                      {detailedCase.renewal_remarks}
                    </div>
                  )}

                  {detailedCase?.renewal_document && (
                    <div className="flex items-center justify-between pt-1">
                      <div className="text-2xs text-amber-900">
                        <span className="font-semibold">Receipt File: </span>
                        {detailedCase.renewal_document}
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        size="xs"
                        icon={Download}
                        onClick={() =>
                          handleDownload(
                            detailedCase?.raw_id || detailedCase?.id,
                            detailedCase?.renewal_document
                          )
                        }
                      >
                        Download Renewed Receipt
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* Audit / Decision History */}
              {detailedCase?.history && detailedCase.history.length > 0 && (
                <div>
                  <span className="text-2xs font-semibold uppercase text-slate-500 block mb-1.5">
                    Scrutiny & Decision History:
                  </span>
                  <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                    {detailedCase.history.map((h) => (
                      <div
                        key={h.id}
                        className="p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between text-2xs"
                      >
                        <div>
                          <span className="font-bold text-slate-900">{h.action}</span>
                          <span className="text-slate-500 ml-2">by {h.actor_name} ({h.actor_role})</span>
                          <p className="text-slate-600 mt-0.5">{h.details}</p>
                        </div>
                        <span className="text-slate-400 font-mono shrink-0 ml-3">
                          {formatDate(h.timestamp)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Assignment & Allocation History */}
              {detailedCase?.assignment_history && detailedCase.assignment_history.length > 0 && (
                <div>
                  <span className="text-2xs font-semibold uppercase text-slate-500 block mb-1.5">
                    Officer Assignment & Allocation Trail ({detailedCase.assignment_history.length}):
                  </span>
                  <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                    {detailedCase.assignment_history.map((ah) => (
                      <div
                        key={ah.id}
                        className="p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between text-2xs"
                      >
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-900">{ah.assignment_type}</span>
                            <span className="text-slate-500 text-3xs">
                              {ah.previous_officer_name ? `From ${ah.previous_officer_name} &rarr; ` : ''}
                              To <strong>{ah.new_officer_name || 'Unassigned'}</strong>
                            </span>
                          </div>
                          {ah.reason && (
                            <p className="text-slate-600 mt-0.5 text-3xs italic">
                              Note: {ah.reason}
                            </p>
                          )}
                          <span className="text-3xs text-slate-400 block mt-0.5">
                            By: {ah.assigned_by_name}
                          </span>
                        </div>
                        <span className="text-slate-400 font-mono shrink-0 ml-3 text-3xs">
                          {formatDate(ah.created_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Decision Action Form */}
              <form onSubmit={handleSubmitDecision} className="space-y-3 pt-3 border-t border-slate-200">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                      Scrutiny Decision <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={actionStatus}
                      onChange={(e) => setActionStatus(e.target.value)}
                      required
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                    >
                      <option value="">Select Scrutiny Action...</option>
                      {(detailedCase?.status === 'Pending Verification' || detailedCase?.renewal_fdr_number) && (
                        <option value="VERIFY_RENEWAL" className="font-bold text-emerald-700">
                          Verify Renewal & Endorse New Maturity Date
                        </option>
                      )}
                      <option value="Under Review">Take Under Scrutiny (Under Review)</option>
                      <option value="Documents Required">Request Corrections / Missing Documents</option>
                      <option value="Approved">Approve Petition (Clear for Bureau Release)</option>
                      <option value="Rejected">Reject Petition (Non-Compliant)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                      Current Decision Stage
                    </label>
                    <div className="px-3 py-2 text-xs rounded-lg border border-slate-200 bg-slate-100 text-slate-600 font-medium">
                      {detailedCase?.stage || 'AICTE Desk Scrutiny'}
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                    Scrutiny Notes & Regulatory Remarks{' '}
                    {(actionStatus === 'Documents Required' || actionStatus === 'Rejected') && (
                      <span className="text-rose-500">* (Mandatory for rejection/deficiency)</span>
                    )}
                  </label>
                  <textarea
                    rows={3}
                    value={actionRemarks}
                    onChange={(e) => setActionRemarks(e.target.value)}
                    placeholder="Enter compliance rationale, defect notes, or approval endorsement..."
                    className="w-full p-2.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                  />
                </div>

                <div className="flex justify-end gap-2.5 pt-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={isSubmittingAction}
                    onClick={() => setSelectedCase(null)}
                  >
                    Close
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    loading={isSubmittingAction}
                    icon={Send}
                  >
                    Submit Regulatory Decision
                  </Button>
                </div>
              </form>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}

export default OfficerDashboardPage
