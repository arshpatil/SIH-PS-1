import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Users,
  ShieldCheck,
  Building2,
  AlertCircle,
  CheckCircle2,
  Search,
  RefreshCw,
  UserCheck,
  Send,
  Download,
  CalendarClock,
  Inbox,
  History,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { RequestStatusBadge } from '../components/requests/RequestStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { PriorityBadge } from './OfficerDashboardPage'
import { formatDate } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'
import { dashboardService } from '../services/dashboardService'
import { requestService } from '../services/requestService'
import { reportService } from '../services/reportService'

export function AdminDashboardPage() {
  const { currentUser, showToast } = useApp()

  const [loading, setLoading] = useState(true)
  const [adminData, setAdminData] = useState(null)
  const [activeTab, setActiveTab] = useState('queue') // 'queue' | 'officers' | 'audit' | 'monitoring'

  // Assignment Queue filters
  const [queueSearch, setQueueSearch] = useState('')
  const [queueTypeFilter, setQueueTypeFilter] = useState('ALL')
  const [queuePriorityFilter, setQueuePriorityFilter] = useState('ALL')

  // Assignment Modal
  const [assignModalOpen, setAssignModalOpen] = useState(false)
  const [selectedPetition, setSelectedPetition] = useState(null)
  const [selectedOfficerId, setSelectedOfficerId] = useState('')
  const [isAssigning, setIsAssigning] = useState(false)

  // Officer Status Toggle Modal
  const [officerStatusModal, setOfficerStatusModal] = useState({
    isOpen: false,
    officer: null,
    targetStatus: false,
  })
  const [isUpdatingOfficer, setIsUpdatingOfficer] = useState(false)

  // Export state
  const [isExporting, setIsExporting] = useState(false)

  // Load Admin Data
  const loadAdminDashboard = useCallback(async (isRefresh = false) => {
    if (!isRefresh) setLoading(true)
    try {
      const data = await dashboardService.getAdminDashboard()
      if (data) {
        setAdminData(data)
      }
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to load administrative overview', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadAdminDashboard()
  }, [loadAdminDashboard])

  // Open Assignment Modal
  const handleOpenAssignModal = (petition) => {
    setSelectedPetition(petition)
    setSelectedOfficerId(petition.assigned_to ? String(petition.assigned_to) : '')
    setAssignModalOpen(true)
  }

  // Submit Assignment
  const handleAssignPetition = async (e) => {
    e.preventDefault()
    if (!selectedOfficerId) {
      showToast('Please select an active officer for assignment.', 'error')
      return
    }

    setIsAssigning(true)
    const rawId = selectedPetition.raw_id || selectedPetition.id

    try {
      await requestService.assignRequest(rawId, parseInt(selectedOfficerId, 10))
      showToast(`Petition ${selectedPetition.id} assigned successfully!`, 'success')
      setAssignModalOpen(false)
      loadAdminDashboard(true)
    } catch (err) {
      showToast(err.response?.data?.error || err.message || 'Failed to assign petition', 'error')
    } finally {
      setIsAssigning(false)
    }
  }

  // Handle Officer Account Status Toggle
  const handleConfirmOfficerStatus = async () => {
    const { officer, targetStatus } = officerStatusModal
    if (!officer) return

    setIsUpdatingOfficer(true)
    try {
      await dashboardService.updateOfficerStatus(officer.officer_id || officer.id, targetStatus)
      showToast(
        `Officer '${officer.officer_name || officer.full_name}' account ${
          targetStatus ? 'activated' : 'deactivated'
        } successfully.`,
        'success'
      )
      setOfficerStatusModal({ isOpen: false, officer: null, targetStatus: false })
      loadAdminDashboard(true)
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to update officer status', 'error')
    } finally {
      setIsUpdatingOfficer(false)
    }
  }

  // Export CSV Reports
  const handleExportPetitions = async () => {
    setIsExporting(true)
    try {
      await reportService.downloadPetitionsCSV()
      showToast('Petitions report exported successfully.', 'success')
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to export petitions report', 'error')
    } finally {
      setIsExporting(false)
    }
  }

  const metrics = adminData?.metrics || {}
  const unassignedQueue = adminData?.unassigned_queue || []
  const officerWorkloads = adminData?.officer_workloads || []
  const recentAudits = adminData?.recent_audit_events || []

  // Active officers available for assignment
  const activeOfficers = useMemo(() => {
    return officerWorkloads.filter((o) => o.is_active)
  }, [officerWorkloads])

  // Filtered Unassigned Queue
  const filteredQueue = useMemo(() => {
    return unassignedQueue.filter((p) => {
      const q = queueSearch.toLowerCase().trim()
      const reqId = String(p.id || '').toLowerCase()
      const fdrNum = String(p.fdrNumber || p.fdr_number || '').toLowerCase()
      const instName = String(p.institutionName || p.institution_name || '').toLowerCase()

      const matchesSearch = !q || reqId.includes(q) || fdrNum.includes(q) || instName.includes(q)
      const matchesType = queueTypeFilter === 'ALL' || p.requestType === queueTypeFilter || p.request_type === queueTypeFilter
      const matchesPriority =
        queuePriorityFilter === 'ALL' || (p.priority || 'LOW').toUpperCase() === queuePriorityFilter.toUpperCase()

      return matchesSearch && matchesType && matchesPriority
    })
  }, [unassignedQueue, queueSearch, queueTypeFilter, queuePriorityFilter])

  return (
    <div className="space-y-6">
      {/* Admin Operations Welcome Banner */}
      <div className="bg-gradient-to-r from-[#142B4A] via-[#1A3C67] to-[#142B4A] rounded-2xl p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
        <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-64 h-64 bg-white/5 rounded-full blur-2xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/10 text-amber-300 text-xs font-medium border border-white/10">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>AICTE Central Administration Oversight Bureau</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Administrator Oversight Workspace
            </h1>
            <p className="text-slate-200 text-sm leading-relaxed">
              Central management dashboard for assigning statutory petitions, balancing officer workloads, enforcing review SLA deadlines, and auditing system-wide FDR operations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              size="md"
              className="bg-white/10 hover:bg-white/20 text-white border-white/20"
              icon={RefreshCw}
              onClick={() => loadAdminDashboard(true)}
            >
              Refresh Data
            </Button>
            <Button
              variant="primary"
              size="md"
              loading={isExporting}
              icon={Download}
              className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold shadow-md border border-amber-400"
              onClick={handleExportPetitions}
            >
              Export Petitions CSV
            </Button>
          </div>
        </div>
      </div>

      {/* Unassigned Workload Alert Banner if any */}
      {metrics.unassigned_petitions_count > 0 && (
        <div className="flex items-center justify-between p-4 bg-amber-50 rounded-xl border border-amber-300 text-amber-900 text-xs sm:text-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold">Pending Officer Assignment:</span> There are{' '}
              <span className="font-bold underline">{metrics.unassigned_petitions_count} unassigned petition(s)</span> in the institutional queue awaiting desk scrutiny allocation.
            </div>
          </div>
          <button
            onClick={() => setActiveTab('queue')}
            className="shrink-0 ml-4 font-semibold text-amber-800 hover:text-amber-950 underline text-xs"
          >
            Review Assignment Queue &rarr;
          </button>
        </div>
      )}

      {/* SECTION A: System-Wide Real Database-Backed Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Registered Institutions */}
        <Card className="p-4 border-slate-200 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-2xs font-semibold text-slate-600 uppercase tracking-wider block">
                Registered Institutions
              </span>
              <span className="text-3xl font-bold text-slate-900 mt-1 block">
                {metrics.total_institutions ?? 0}
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-blue-50 text-blue-700">
              <Building2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Approved AICTE Colleges</span>
            <span className="font-semibold text-blue-700">Central Directory</span>
          </div>
        </Card>

        {/* Metric 2: Active FDR Records */}
        <Card className="p-4 border-slate-200 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-2xs font-semibold text-slate-600 uppercase tracking-wider block">
                Active Security Deposits
              </span>
              <span className="text-3xl font-bold text-emerald-950 mt-1 block">
                {metrics.total_active_fdrs ?? 0}
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Upcoming Maturing: {metrics.upcoming_maturities_count ?? 0}</span>
            <span className="font-semibold text-emerald-700">In Good Standing</span>
          </div>
        </Card>

        {/* Metric 3: Total Petitions & Unassigned Queue */}
        <Card className="p-4 border-slate-200 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-2xs font-semibold text-slate-600 uppercase tracking-wider block">
                Unassigned Petitions
              </span>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-3xl font-bold text-amber-700">
                  {metrics.unassigned_petitions_count ?? 0}
                </span>
                <span className="text-2xs text-slate-400">
                  / {metrics.total_petitions ?? 0} total
                </span>
              </div>
            </div>
            <div className="p-2.5 rounded-xl bg-amber-50 text-amber-700">
              <Inbox className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Awaiting officer allocation</span>
            <span className="font-semibold text-amber-700">Assignment Queue</span>
          </div>
        </Card>

        {/* Metric 4: Active Officers & Overdue Backlog */}
        <Card className="p-4 border-slate-200 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-2xs font-semibold text-slate-600 uppercase tracking-wider block">
                Scrutiny Officers Active
              </span>
              <span className="text-3xl font-bold text-slate-900 mt-1 block">
                {metrics.active_officers_count ?? 0}
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-700">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-100 text-2xs text-slate-500 flex items-center justify-between">
            <span>Overdue (&gt;14d): {metrics.overdue_cases_count ?? 0}</span>
            <span className={`font-semibold ${metrics.overdue_cases_count > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
              {metrics.overdue_cases_count > 0 ? 'SLA Alert' : 'On Track'}
            </span>
          </div>
        </Card>
      </div>

      {/* Admin Tab Navigation */}
      <div className="flex border-b border-slate-200 gap-4">
        <button
          onClick={() => setActiveTab('queue')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'queue'
              ? 'border-[#142B4A] text-[#142B4A]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Inbox className="w-4 h-4" />
          <span>Petition Assignment Queue ({unassignedQueue.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('officers')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'officers'
              ? 'border-[#142B4A] text-[#142B4A]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Officer Management & Workload ({officerWorkloads.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('monitoring')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'monitoring'
              ? 'border-[#142B4A] text-[#142B4A]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <CalendarClock className="w-4 h-4" />
          <span>Workflow & SLA Monitoring</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === 'audit'
              ? 'border-[#142B4A] text-[#142B4A]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <History className="w-4 h-4" />
          <span>System Audit Trail</span>
        </button>
      </div>

      {/* SECTION B: Petition Assignment Queue */}
      {activeTab === 'queue' && (
        <Card className="p-5 border-slate-200">
          <CardHeader
            title="Unassigned Petition Assignment Queue"
            subtitle="Allocate submitted renewal and release petitions to authorized AICTE scrutiny officers"
          />

          {/* Filters */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 my-4">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search by ID, FDR number, or institution..."
                value={queueSearch}
                onChange={(e) => setQueueSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={queueTypeFilter}
                onChange={(e) => setQueueTypeFilter(e.target.value)}
                className="text-xs px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none"
              >
                <option value="ALL">All Request Types</option>
                <option value="Renewal">Renewal Only</option>
                <option value="Release">Release Only</option>
              </select>

              <select
                value={queuePriorityFilter}
                onChange={(e) => setQueuePriorityFilter(e.target.value)}
                className="text-xs px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none"
              >
                <option value="ALL">All Priorities</option>
                <option value="URGENT">Urgent Only</option>
                <option value="HIGH">High Priority</option>
                <option value="MEDIUM">Medium Priority</option>
                <option value="LOW">Low Priority</option>
              </select>
            </div>
          </div>

          {/* Queue Table */}
          {loading ? (
            <div className="py-12 text-center text-xs text-slate-500">Loading assignment queue...</div>
          ) : filteredQueue.length === 0 ? (
            <EmptyState
              title="No unassigned petitions in queue"
              description="All submitted institutional requests are currently assigned to active scrutiny officers."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-2xs uppercase text-slate-500 font-semibold bg-slate-50">
                    <th className="py-2.5 px-3">Petition ID</th>
                    <th className="py-2.5 px-3">Institution</th>
                    <th className="py-2.5 px-3">FDR Ref #</th>
                    <th className="py-2.5 px-3">Maturity Date</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Priority</th>
                    <th className="py-2.5 px-3">Submitted</th>
                    <th className="py-2.5 px-3 text-right">Assign Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredQueue.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3 font-mono font-bold text-[#142B4A]">
                        {p.id}
                      </td>
                      <td className="py-3 px-3">
                        <span className="font-semibold text-slate-900 block truncate max-w-[200px]">
                          {p.institutionName || p.institution_name || 'Technical College'}
                        </span>
                        <span className="text-2xs text-slate-400 font-mono">
                          {p.institutionCode || p.institution_code || 'ID: 1-439281'}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-700">
                        <div>{p.fdrNumber || p.fdr_number}</div>
                        <div className="text-2xs text-slate-400">{p.bankName || p.bank_name}</div>
                      </td>
                      <td className="py-3 px-3">
                        <div>{formatDate(p.maturityDate || p.maturity_date)}</div>
                        <span className="text-2xs text-slate-500">
                          {p.daysRemaining !== null && p.daysRemaining !== undefined
                            ? `${p.daysRemaining} days left`
                            : ''}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-2xs font-semibold ${
                            p.requestType === 'Release' || p.request_type === 'Release'
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          {p.requestType || p.request_type}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <PriorityBadge priority={p.priority} />
                      </td>
                      <td className="py-3 px-3 text-2xs text-slate-500">
                        {formatDate(p.submissionDate || p.created_at)}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Button
                          variant="primary"
                          size="xs"
                          icon={UserCheck}
                          onClick={() => handleOpenAssignModal(p)}
                        >
                          Assign Officer
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

      {/* SECTION C: Officer Management & Workload */}
      {activeTab === 'officers' && (
        <Card className="p-5 border-slate-200">
          <CardHeader
            title="Scrutiny Officer Directory & Caseloads"
            subtitle="Manage officer accounts, monitor active workload distribution, and enforce case review balance"
          />

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-2xs uppercase text-slate-500 font-semibold bg-slate-50">
                  <th className="py-2.5 px-3">Officer Name</th>
                  <th className="py-2.5 px-3">Role</th>
                  <th className="py-2.5 px-3 text-center">Active Cases</th>
                  <th className="py-2.5 px-3 text-center">Resolved Cases</th>
                  <th className="py-2.5 px-3 text-center">Overdue (&gt;14d)</th>
                  <th className="py-2.5 px-3">Account Status</th>
                  <th className="py-2.5 px-3 text-right">Admin Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {officerWorkloads.map((off) => {
                  const isSelf = off.officer_id === currentUser?.id || off.id === currentUser?.id

                  return (
                    <tr key={off.officer_id || off.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3">
                        <div className="font-semibold text-slate-900">
                          {off.officer_name || off.full_name} {isSelf && '(You)'}
                        </div>
                        <div className="text-2xs text-slate-400 font-mono">{off.officer_email || off.email}</div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="inline-block px-2 py-0.5 rounded text-2xs font-semibold bg-slate-100 text-slate-700">
                          {off.role}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center font-bold text-slate-900">
                        {off.active_assigned_cases ?? off.active_cases ?? 0}
                      </td>
                      <td className="py-3 px-3 text-center font-medium text-emerald-700">
                        {off.resolved_cases ?? 0}
                      </td>
                      <td className="py-3 px-3 text-center font-semibold text-rose-700">
                        {off.overdue_cases ?? 0}
                      </td>
                      <td className="py-3 px-3">
                        {off.is_active ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-slate-100 text-slate-500 border border-slate-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                            Deactivated
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right">
                        {isSelf ? (
                          <span className="text-2xs text-slate-400 italic">Self Account</span>
                        ) : off.is_active ? (
                          <Button
                            variant="secondary"
                            size="xs"
                            className="text-rose-700 border-rose-200 hover:bg-rose-50"
                            onClick={() =>
                              setOfficerStatusModal({
                                isOpen: true,
                                officer: off,
                                targetStatus: false,
                              })
                            }
                          >
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            size="xs"
                            className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                            onClick={() =>
                              setOfficerStatusModal({
                                isOpen: true,
                                officer: off,
                                targetStatus: true,
                              })
                            }
                          >
                            Activate
                          </Button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* SECTION D: Workflow & SLA Monitoring */}
      {activeTab === 'monitoring' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Petitions by Status Breakdown */}
          <Card className="p-5 border-slate-200">
            <CardHeader
              title="Petition Workflow Distribution"
              subtitle="All statutory renewal and release petitions across regulatory review stages"
            />
            <div className="space-y-3 mt-4">
              {Object.entries(metrics.petitions_by_status || {}).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="flex items-center gap-3">
                    <RequestStatusBadge status={status} size="sm" />
                  </div>
                  <span className="text-sm font-bold text-slate-900">{count}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Workload SLA Analysis */}
          <Card className="p-5 border-slate-200">
            <CardHeader
              title="Bureau SLA & Regulatory Compliance"
              subtitle="Statutory scrutiny timeline compliance overview"
            />
            <div className="space-y-4 mt-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-medium">Overdue Petition Cases (&gt; 14 Days)</span>
                  <span className="font-bold text-rose-700">{metrics.overdue_cases_count ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-medium">Unassigned Workload Ratio</span>
                  <span className="font-bold text-amber-700">
                    {metrics.total_petitions > 0
                      ? `${Math.round((metrics.unassigned_petitions_count / metrics.total_petitions) * 100)}%`
                      : '0%'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-medium">FDR Deposits Maturing in &lt;= 30 Days</span>
                  <span className="font-bold text-slate-900">{metrics.upcoming_maturities_count ?? 0}</span>
                </div>
              </div>

              <div className="p-3.5 bg-blue-50/70 rounded-xl border border-blue-200 text-blue-900 text-2xs leading-relaxed">
                <span className="font-bold block mb-1">Administrative Scrutiny Note:</span>
                Under AICTE regulatory guidelines, all statutory petitions submitted by institutions must be allocated to an officer within 3 business days of submission. Decisions must be issued prior to the linked FDR's maturity date to avoid deposit lien encashment.
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* SECTION E: System Audit Trail */}
      {activeTab === 'audit' && (
        <Card className="p-5 border-slate-200">
          <CardHeader
            title="System-Wide Cryptographic Audit Trail"
            subtitle="Immutable activity ledger of administrative allocations, scrutiny actions, and officer updates"
          />

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-2xs uppercase text-slate-500 font-semibold bg-slate-50">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Actor</th>
                  <th className="py-2.5 px-3">Entity</th>
                  <th className="py-2.5 px-3">Details / Audit Memo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentAudits.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-3 font-mono text-2xs text-slate-500 whitespace-nowrap">
                      {formatDate(a.timestamp)}
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-mono font-bold text-slate-800 text-2xs px-2 py-0.5 rounded bg-slate-100">
                        {a.action}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-semibold text-slate-900 block">{a.actor_name}</span>
                      <span className="text-2xs text-slate-400">{a.actor_role}</span>
                    </td>
                    <td className="py-3 px-3 font-mono text-2xs text-slate-600">
                      {a.entity_type} #{a.entity_id}
                    </td>
                    <td className="py-3 px-3 text-slate-700 max-w-md">
                      {a.details}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* MODAL: Assign Petition to Officer */}
      {assignModalOpen && selectedPetition && (
        <Modal
          isOpen={assignModalOpen}
          onClose={() => setAssignModalOpen(false)}
          title={`Assign Petition ${selectedPetition.id}`}
          subtitle={`Institution: ${selectedPetition.institutionName || selectedPetition.institution_name} • FDR ${selectedPetition.fdrNumber || selectedPetition.fdr_number}`}
          maxWidth="max-w-md"
        >
          <form onSubmit={handleAssignPetition} className="space-y-4 text-xs text-slate-700">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500">Request Type:</span>
                <span className="font-semibold text-slate-900">{selectedPetition.requestType || selectedPetition.request_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Maturity Date:</span>
                <span className="font-semibold text-slate-900">{formatDate(selectedPetition.maturityDate || selectedPetition.maturity_date)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Priority:</span>
                <PriorityBadge priority={selectedPetition.priority} />
              </div>
            </div>

            <div>
              <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                Select Scrutiny Officer <span className="text-rose-500">*</span>
              </label>
              <select
                value={selectedOfficerId}
                onChange={(e) => setSelectedOfficerId(e.target.value)}
                required
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              >
                <option value="">Choose an active officer...</option>
                {activeOfficers.map((off) => (
                  <option key={off.officer_id || off.id} value={off.officer_id || off.id}>
                    {off.officer_name || off.full_name} ({off.active_assigned_cases ?? off.active_cases ?? 0} active cases)
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={isAssigning}
                onClick={() => setAssignModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                loading={isAssigning}
                icon={Send}
              >
                Confirm Assignment
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* MODAL: Officer Account Status Toggle Confirmation */}
      {officerStatusModal.isOpen && officerStatusModal.officer && (
        <Modal
          isOpen={officerStatusModal.isOpen}
          onClose={() => setOfficerStatusModal({ isOpen: false, officer: null, targetStatus: false })}
          title={`${officerStatusModal.targetStatus ? 'Activate' : 'Deactivate'} Officer Account`}
          maxWidth="max-w-md"
        >
          <div className="space-y-4 text-xs text-slate-700">
            <p>
              Are you sure you want to{' '}
              <strong className={officerStatusModal.targetStatus ? 'text-emerald-700' : 'text-rose-700'}>
                {officerStatusModal.targetStatus ? 'activate' : 'deactivate'}
              </strong>{' '}
              the officer account for{' '}
              <strong>{officerStatusModal.officer.officer_name || officerStatusModal.officer.full_name}</strong> (
              <span className="font-mono">{officerStatusModal.officer.officer_email || officerStatusModal.officer.email}</span>)?
            </p>

            {!officerStatusModal.targetStatus && (
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-amber-900 text-2xs leading-relaxed">
                <strong>Important:</strong> Deactivating an officer prevents future portal logins and stops new case allocations. All historical reviews, approval stamps, and audit records remain intact and preserved in accordance with regulatory compliance standards.
              </div>
            )}

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={isUpdatingOfficer}
                onClick={() => setOfficerStatusModal({ isOpen: false, officer: null, targetStatus: false })}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant={officerStatusModal.targetStatus ? 'primary' : 'danger'}
                size="sm"
                loading={isUpdatingOfficer}
                onClick={handleConfirmOfficerStatus}
              >
                Confirm {officerStatusModal.targetStatus ? 'Activation' : 'Deactivation'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default AdminDashboardPage
