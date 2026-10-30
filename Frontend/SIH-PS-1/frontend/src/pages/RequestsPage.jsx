import React, { useState, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  PlusCircle,
  Search,
  Eye,
  AlertCircle,
  FileText,
  Download,
  Loader2,
  Upload,
  UserCheck,
  Clock,
  History,
  FileSpreadsheet,
  AlertTriangle,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { RequestStatusBadge } from '../components/requests/RequestStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { formatCurrency } from '../utils/formatters'
import { formatDate } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'
import { requestService } from '../services/requestService'
import { reportService } from '../services/reportService'
import { PriorityBadge } from './OfficerDashboardPage'

const ALL_REQUEST_STATUSES = [
  'ALL',
  'Submitted',
  'Under Review',
  'Documents Required',
  'Resubmitted / Awaiting Review',
  'Approved',
  'Pending Verification',
  'Rejected',
  'Closed',
]

const PENDING_STATUSES = [
  'submitted',
  'under review',
  'documents required',
  'resubmitted / awaiting review',
  'resubmitted',
  'pending verification',
]

export function RequestsPage() {
  const { requests, fdrs, addRequest, showToast, currentUser, refreshRequests } = useApp()

  // Filters state
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [showOverdueOnly, setShowOverdueOnly] = useState(false)
  const [exportingCsv, setExportingCsv] = useState(false)

  // New Request Modal state
  const [newModalOpen, setNewModalOpen] = useState(false)
  const [selectedFdrId, setSelectedFdrId] = useState('')
  const [requestType, setRequestType] = useState('Renewal')
  const [reason, setReason] = useState('')
  const [supportingFile, setSupportingFile] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Details Modal state
  const [selectedRequest, setSelectedRequest] = useState(null)
  const [detailedRequest, setDetailedRequest] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [downloadingId, setDownloadingId] = useState(null)

  // Resubmission state (Institution)
  const [resubmitFile, setResubmitFile] = useState(null)
  const [resubmitRemarks, setResubmitRemarks] = useState('')
  const [isResubmitting, setIsResubmitting] = useState(false)

  // Officer Action state
  const [officerStatus, setOfficerStatus] = useState('')
  const [officerRemarks, setOfficerRemarks] = useState('')
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)

  // Case Assignment state (Admin)
  const [assignOfficerId, setAssignOfficerId] = useState('')
  const [isAssigning, setIsAssigning] = useState(false)

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' ||
    currentUser?.role === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

  const isAdmin = currentUser?.role === 'ADMIN'

  // Helper: check if a request is overdue (> 14 days pending)
  const checkIsOverdue = useCallback((req) => {
    if (req.is_overdue !== undefined) return Boolean(req.is_overdue)
    const normStatus = (req.status || '').toLowerCase().trim()
    if (!PENDING_STATUSES.includes(normStatus)) return false
    const subDate = req.submissionDate || req.created_at
    if (!subDate) return false
    const diffDays = (Date.now() - new Date(subDate).getTime()) / (1000 * 60 * 60 * 24)
    return diffDays > 14
  }, [])

  // Count overdue requests
  const overdueCount = useMemo(() => {
    return requests.filter(checkIsOverdue).length
  }, [requests, checkIsOverdue])

  // Filtered requests
  const filteredRequests = useMemo(() => {
    return requests.filter((r) => {
      const q = searchQuery.toLowerCase().trim()
      const reqId = String(r.id || '').toLowerCase()
      const fdrNum = String(r.fdrNumber || r.fdr_number || '').toLowerCase()
      const bankName = String(r.bankName || r.bank_name || '').toLowerCase()

      const matchesSearch = !q || reqId.includes(q) || fdrNum.includes(q) || bankName.includes(q)

      const matchesType = typeFilter === 'ALL' || r.requestType === typeFilter || r.request_type === typeFilter

      const currentStatus = (r.status || '').toLowerCase().trim()
      const matchesStatus =
        statusFilter === 'ALL' || currentStatus === statusFilter.toLowerCase().trim()

      const matchesOverdue = !showOverdueOnly || checkIsOverdue(r)

      return matchesSearch && matchesType && matchesStatus && matchesOverdue
    })
  }, [requests, searchQuery, typeFilter, statusFilter, showOverdueOnly, checkIsOverdue])

  // Eligible FDRs for creating a new request
  const eligibleFDRs = useMemo(() => {
    return fdrs.filter((f) => f.status !== 'Released')
  }, [fdrs])

  // Fetch full details when opening a request
  const handleOpenDetail = async (req) => {
    setSelectedRequest(req)
    setDetailedRequest(null)
    setOfficerStatus('')
    setOfficerRemarks('')
    setResubmitRemarks('')
    setResubmitFile(null)
    setAssignOfficerId('')

    const rawId = req.raw_id || req.id
    setDetailLoading(true)
    try {
      const detail = await requestService.getRequestDetail(rawId)
      if (detail) {
        setDetailedRequest(detail)
        if (detail.assigned_to) {
          setAssignOfficerId(String(detail.assigned_to))
        }
      }
    } catch {
      // Fall back to existing request summary
    } finally {
      setDetailLoading(false)
    }
  }

  const handleCreateRequest = async (e) => {
    e.preventDefault()
    if (!selectedFdrId) {
      showToast('Please select an eligible FDR record.', 'error')
      return
    }
    if (!reason.trim()) {
      showToast('Please provide an institutional justification.', 'error')
      return
    }

    const targetFDR = fdrs.find((f) => String(f.id) === String(selectedFdrId))
    if (!targetFDR) {
      showToast('Selected FDR record could not be found.', 'error')
      return
    }

    setIsSubmitting(true)
    try {
      await addRequest({
        fdrId: targetFDR.id,
        fdrNumber: targetFDR.fdrNumber,
        bankName: targetFDR.bankName,
        depositAmount: targetFDR.depositAmount,
        requestType,
        reason: reason.trim(),
        supportingFile: supportingFile || null,
        supportingDocument: supportingFile ? supportingFile.name : `${targetFDR.fdrNumber}_SupportingDoc.pdf`,
        documentSize: supportingFile ? supportingFile.size : 1750000,
        remarks: 'Administrative request submitted through institutional portal.',
      })

      setNewModalOpen(false)
      setSelectedFdrId('')
      setReason('')
      setSupportingFile(null)
      showToast('Petition submitted successfully to AICTE Regional Bureau.', 'success')
      if (refreshRequests) refreshRequests()
    } catch (err) {
      showToast(err.message || 'Failed to submit request. Please verify and try again.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle Resubmission by Institution
  const handleResubmit = async (e) => {
    e.preventDefault()
    if (!resubmitRemarks.trim()) {
      showToast('Please provide an explanation of the rectified documents.', 'error')
      return
    }

    const rawId = selectedRequest?.raw_id || selectedRequest?.id
    setIsResubmitting(true)
    try {
      await requestService.resubmitRequest(rawId, {
        file: resubmitFile,
        remarks: resubmitRemarks.trim(),
      })
      showToast('Rectified documents and response submitted successfully.', 'success')
      if (refreshRequests) await refreshRequests()
      // Refresh detail view
      const updated = await requestService.getRequestDetail(rawId)
      setDetailedRequest(updated)
      setSelectedRequest((prev) => ({ ...prev, status: 'Resubmitted / Awaiting Review' }))
      setResubmitFile(null)
      setResubmitRemarks('')
    } catch (err) {
      showToast(err.message || 'Failed to resubmit request.', 'error')
    } finally {
      setIsResubmitting(false)
    }
  }

  // Handle Officer Status Update
  const handleOfficerUpdateStatus = async (e) => {
    e.preventDefault()
    if (!officerStatus) {
      showToast('Please select a target status.', 'error')
      return
    }
    const needsRemarks = officerStatus === 'Documents Required' || officerStatus === 'Rejected'
    if (needsRemarks && !officerRemarks.trim()) {
      showToast(`Remarks are mandatory when marking ${officerStatus}.`, 'error')
      return
    }

    const rawId = selectedRequest?.raw_id || selectedRequest?.id
    setIsUpdatingStatus(true)
    try {
      await requestService.updateRequestStatus(rawId, officerStatus, officerRemarks.trim())
      showToast(`Request transitioned to ${officerStatus}.`, 'success')
      if (refreshRequests) await refreshRequests()
      const updated = await requestService.getRequestDetail(rawId)
      setDetailedRequest(updated)
      setSelectedRequest((prev) => ({ ...prev, status: officerStatus }))
      setOfficerRemarks('')
      setOfficerStatus('')
    } catch (err) {
      showToast(err.message || 'Failed to update request status.', 'error')
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  // Handle Case Assignment by Admin
  const handleAssignOfficer = async (e) => {
    e.preventDefault()
    if (!assignOfficerId) {
      showToast('Please specify an officer ID to assign.', 'error')
      return
    }

    const rawId = selectedRequest?.raw_id || selectedRequest?.id
    setIsAssigning(true)
    try {
      await requestService.assignRequest(rawId, assignOfficerId)
      showToast('Petition successfully assigned to scrutiny officer.', 'success')
      if (refreshRequests) await refreshRequests()
      const updated = await requestService.getRequestDetail(rawId)
      setDetailedRequest(updated)
    } catch (err) {
      showToast(err.message || 'Failed to assign petition.', 'error')
    } finally {
      setIsAssigning(false)
    }
  }

  const handleDownloadAttachment = async (req) => {
    if (!req || !req.supportingDocument) {
      showToast('No supporting document attached to this request.', 'warning')
      return
    }

    const reqId = req.raw_id || req.id
    setDownloadingId(req.id)
    try {
      await requestService.downloadAttachment(reqId, req.supportingDocument)
      showToast(`Downloaded ${req.supportingDocument}`, 'success')
    } catch (err) {
      showToast(err.message || 'Failed to download attachment from server.', 'error')
    } finally {
      setDownloadingId(null)
    }
  }

  const handleExportCSV = async () => {
    setExportingCsv(true)
    try {
      const params = {}
      if (statusFilter !== 'ALL') params.status = statusFilter
      if (typeFilter !== 'ALL') params.type = typeFilter
      if (showOverdueOnly) params.overdue_only = 'true'

      await reportService.downloadPetitionsCSV(params)
      showToast('Petitions report CSV exported successfully.', 'success')
    } catch (err) {
      showToast(err.message || 'Failed to export petitions report.', 'error')
    } finally {
      setExportingCsv(false)
    }
  }

  const activeReq = detailedRequest || selectedRequest

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            FDR Renewal & Release Petitions
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Track statutory petitions submitted to the AICTE Regional Bureau for term renewal or lien release.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="secondary"
            icon={FileSpreadsheet}
            loading={exportingCsv}
            onClick={handleExportCSV}
          >
            Export CSV
          </Button>

          {!isOfficerOrAdmin && (
            <Button
              variant="primary"
              icon={PlusCircle}
              onClick={() => setNewModalOpen(true)}
            >
              Create New Request
            </Button>
          )}
        </div>
      </div>

      {/* Overdue Escalation Banner if any pending > 14 days */}
      {overdueCount > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-amber-50 rounded-xl border border-amber-300 text-amber-950 text-xs sm:text-sm shadow-xs">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-100 text-amber-800">
              <Clock className="w-5 h-5 text-amber-700 animate-pulse" />
            </div>
            <div>
              <span className="font-bold">Overdue Bureau Backlog:</span> {overdueCount} statutory petition(s) have been pending review for over 14 days without final decision.
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowOverdueOnly(!showOverdueOnly)}
            className="shrink-0 px-3 py-1.5 rounded-lg bg-amber-200/80 hover:bg-amber-300 font-semibold text-amber-900 text-xs transition-colors"
          >
            {showOverdueOnly ? 'Show All Petitions' : 'Filter Overdue (>14 Days)'}
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Request ID, FDR Number, or Bank..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            />
          </div>

          <div className="md:col-span-3">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="ALL">All Petition Types</option>
              <option value="Renewal">Renewal Petitions</option>
              <option value="Release">Release Petitions</option>
            </select>
          </div>

          <div className="md:col-span-4 flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              {ALL_REQUEST_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {st === 'ALL' ? 'All Lifecycle Stages' : st}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => setShowOverdueOnly(!showOverdueOnly)}
              title="Toggle Overdue >14d"
              className={`px-3 py-2 text-xs font-semibold rounded-lg border transition-colors whitespace-nowrap flex items-center gap-1.5 ${
                showOverdueOnly
                  ? 'bg-amber-500 text-white border-amber-600 shadow-xs'
                  : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Overdue</span>
            </button>
          </div>
        </div>
      </Card>

      {/* Requests Table */}
      <Card className="p-0 overflow-hidden">
        {filteredRequests.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No renewal or release requests match your criteria"
              description="You can file a new request for any active or maturing institutional fixed deposit."
              actionLabel={!isOfficerOrAdmin ? "Create New Request" : undefined}
              onAction={!isOfficerOrAdmin ? () => setNewModalOpen(true) : undefined}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider bg-slate-50">
                  <th className="py-3 px-5">Petition ID</th>
                  {isOfficerOrAdmin && <th className="py-3 px-5">Institution</th>}
                  <th className="py-3 px-5">Related FDR</th>
                  <th className="py-3 px-5">Type</th>
                  <th className="py-3 px-5">Deposit Amount</th>
                  <th className="py-3 px-5">Priority</th>
                  <th className="py-3 px-5">Submitted Date</th>
                  <th className="py-3 px-5">Lifecycle Status</th>
                  <th className="py-3 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredRequests.map((req) => {
                  const isReqOverdue = checkIsOverdue(req)
                  return (
                    <tr key={req.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-4 px-5">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono font-semibold text-slate-900 text-xs">
                            {req.id}
                          </span>
                          {isReqOverdue && (
                            <span
                              title="Overdue (>14 days pending)"
                              className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300"
                            >
                              Overdue
                            </span>
                          )}
                        </div>
                      </td>
                      {isOfficerOrAdmin && (
                        <td className="py-4 px-5">
                          <span className="font-semibold text-slate-900 block text-xs truncate max-w-[180px]">
                            {req.institutionName || req.institution_name || 'Technical College'}
                          </span>
                          <span className="text-2xs text-slate-400 font-mono">
                            {req.institutionCode || req.institution_code || ''}
                          </span>
                        </td>
                      )}
                      <td className="py-4 px-5">
                        <Link
                          to={`/fdrs/${req.fdrId || req.fdr_id}`}
                          className="font-mono text-xs font-semibold text-[#142B4A] hover:underline"
                        >
                          {req.fdrNumber || req.fdr_number}
                        </Link>
                        <p className="text-2xs text-slate-500 mt-0.5">{req.bankName || req.bank_name}</p>
                      </td>
                      <td className="py-4 px-5 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                            (req.requestType || req.request_type) === 'Renewal'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-purple-100 text-purple-800'
                          }`}
                        >
                          {req.requestType || req.request_type}
                        </span>
                      </td>
                      <td className="py-4 px-5 font-bold text-slate-900 text-xs">
                        {formatCurrency(req.depositAmount || req.deposit_amount)}
                      </td>
                      <td className="py-4 px-5 whitespace-nowrap">
                        <PriorityBadge priority={req.priority} />
                      </td>
                      <td className="py-4 px-5 text-xs text-slate-600 whitespace-nowrap">
                        {formatDate(req.submissionDate || req.created_at)}
                      </td>
                      <td className="py-4 px-5">
                        <RequestStatusBadge status={req.status} size="sm" />
                      </td>
                      <td className="py-4 px-5 text-right whitespace-nowrap">
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={Eye}
                          onClick={() => handleOpenDetail(req)}
                        >
                          Details
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

      {/* New Request Modal */}
      <Modal
        isOpen={newModalOpen}
        onClose={() => setNewModalOpen(false)}
        title="Submit New Renewal or Release Request"
        subtitle="Forwarded to AICTE Regional Bureau Scrutiny Committee"
        maxWidth="max-w-xl"
      >
        <form onSubmit={handleCreateRequest} className="space-y-4">
          <div className="p-3 bg-blue-50 rounded-xl border border-blue-200 text-blue-900 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-[#142B4A] shrink-0 mt-0.5" />
            <span>
              Official institutional petition for term renewal or lien release. All submissions are formally logged and audited by the AICTE Regional Bureau.
            </span>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Select Related FDR <span className="text-rose-500">*</span>
            </label>
            <select
              required
              value={selectedFdrId}
              onChange={(e) => setSelectedFdrId(e.target.value)}
              className="w-full px-3.5 py-2.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="">Choose an eligible FDR record...</option>
              {eligibleFDRs.map((fdr) => (
                <option key={fdr.id} value={fdr.id}>
                  {fdr.fdrNumber} — {fdr.bankName} ({formatCurrency(fdr.depositAmount)})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Request Type <span className="text-rose-500">*</span>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label
                className={`flex items-center justify-center p-3 rounded-lg border cursor-pointer text-xs font-semibold ${
                  requestType === 'Renewal'
                    ? 'border-[#142B4A] bg-[#142B4A]/5 text-[#142B4A]'
                    : 'border-slate-200 bg-white text-slate-600'
                }`}
              >
                <input
                  type="radio"
                  name="requestType"
                  value="Renewal"
                  checked={requestType === 'Renewal'}
                  onChange={() => setRequestType('Renewal')}
                  className="hidden"
                />
                Renewal (Term Extension)
              </label>

              <label
                className={`flex items-center justify-center p-3 rounded-lg border cursor-pointer text-xs font-semibold ${
                  requestType === 'Release'
                    ? 'border-[#142B4A] bg-[#142B4A]/5 text-[#142B4A]'
                    : 'border-slate-200 bg-white text-slate-600'
                }`}
              >
                <input
                  type="radio"
                  name="requestType"
                  value="Release"
                  checked={requestType === 'Release'}
                  onChange={() => setRequestType('Release')}
                  className="hidden"
                />
                Release (Lien Discharge)
              </label>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Justification & Compliance Notes <span className="text-rose-500">*</span>
            </label>
            <textarea
              required
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="State the institutional justification, validity dates, or regulatory reasons for this renewal/release request..."
              className="w-full p-3 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            />
          </div>

          {/* Supporting Document */}
          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Attach Supporting Undertaking / Bank Letter
            </label>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={(e) => setSupportingFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button
              variant="secondary"
              size="md"
              disabled={isSubmitting}
              onClick={() => setNewModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={isSubmitting}
            >
              Submit Request
            </Button>
          </div>
        </form>
      </Modal>

      {/* View Request Details Modal */}
      {selectedRequest && (
        <Modal
          isOpen={!!selectedRequest}
          onClose={() => {
            setSelectedRequest(null)
            setDetailedRequest(null)
          }}
          title={`Petition Details: ${selectedRequest.id}`}
          subtitle={`${selectedRequest.requestType || selectedRequest.request_type} Petition for ${selectedRequest.fdrNumber || selectedRequest.fdr_number}`}
          maxWidth="max-w-2xl"
        >
          <div className="space-y-5 text-xs max-h-[80vh] overflow-y-auto pr-1">
            {detailLoading && (
              <div className="flex items-center justify-center py-4 text-slate-500 gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-[#142B4A]" />
                <span>Loading latest petition audit trail...</span>
              </div>
            )}

            {/* Status and Officer Bar */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200 gap-2">
              <div>
                <span className="text-slate-400 block font-medium">Lifecycle Status</span>
                <div className="mt-1">
                  <RequestStatusBadge status={activeReq?.status} />
                </div>
              </div>
              <div className="sm:text-right">
                <span className="text-slate-400 block font-medium">Assigned Scrutiny Officer</span>
                <span className="font-semibold text-slate-800">
                  {activeReq?.assigned_officer?.full_name || (activeReq?.assigned_to ? `Officer #${activeReq.assigned_to}` : 'Unassigned (Bureau Pool)')}
                </span>
              </div>
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-2 border-y border-slate-100">
              <div>
                <span className="text-slate-400 font-medium block">Related FDR</span>
                <Link
                  to={`/fdrs/${activeReq?.fdrId || activeReq?.fdr_id}`}
                  className="font-mono font-bold text-[#142B4A] hover:underline"
                >
                  {activeReq?.fdrNumber || activeReq?.fdr_number}
                </Link>
              </div>

              <div>
                <span className="text-slate-400 font-medium block">Deposit Amount</span>
                <span className="font-bold text-slate-800">
                  {formatCurrency(activeReq?.depositAmount || activeReq?.deposit_amount)}
                </span>
              </div>

              <div>
                <span className="text-slate-400 font-medium block">Submitted Date</span>
                <span className="text-slate-700">
                  {formatDate(activeReq?.submissionDate || activeReq?.created_at)}
                </span>
              </div>

              <div>
                <span className="text-slate-400 font-medium block">Overdue Status</span>
                {checkIsOverdue(activeReq) ? (
                  <span className="text-rose-600 font-bold">Overdue (&gt;14 days)</span>
                ) : (
                  <span className="text-emerald-700 font-medium">Within SLA</span>
                )}
              </div>
            </div>

            {/* Justification */}
            <div>
              <span className="text-slate-500 font-semibold uppercase tracking-wider block mb-1">
                Institutional Justification
              </span>
              <p className="p-3 rounded-lg bg-slate-50 border border-slate-100 text-slate-700 leading-relaxed">
                {activeReq?.reason}
              </p>
            </div>

            {/* Supporting Document */}
            {(activeReq?.supportingDocument || activeReq?.supporting_document) && (
              <div>
                <span className="text-slate-500 font-semibold uppercase tracking-wider block mb-1">
                  Attached Statutory Document
                </span>
                <div className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-white">
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                    <span className="font-medium text-slate-800 truncate">
                      {activeReq?.supportingDocument || activeReq?.supporting_document}
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={downloadingId === activeReq?.id}
                    onClick={() => handleDownloadAttachment(activeReq)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#142B4A]/10 text-[#142B4A] hover:bg-[#142B4A]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0 ml-2"
                  >
                    {downloadingId === activeReq?.id ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Downloading...</span>
                      </>
                    ) : (
                      <>
                        <Download className="w-3.5 h-3.5" />
                        <span>Download</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Resubmission Section: for Institution when Documents Required */}
            {!isOfficerOrAdmin && (activeReq?.status === 'Documents Required') && (
              <form onSubmit={handleResubmit} className="p-4 rounded-xl border border-rose-300 bg-rose-50/50 space-y-3">
                <div className="flex items-center gap-2 text-rose-800 font-bold">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <span>Rectified Documents Submission Required</span>
                </div>
                <p className="text-xs text-rose-700">
                  The AICTE Scrutiny Officer flagged missing or deficient documentation for this petition. Please upload the requested revised undertaking or clarification letter.
                </p>

                <div>
                  <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                    Rectification Explanation & Notes <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={resubmitRemarks}
                    onChange={(e) => setResubmitRemarks(e.target.value)}
                    placeholder="Describe how the deficiency was addressed (e.g., uploaded updated bank confirmation letter)..."
                    className="w-full p-2.5 text-xs rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                  />
                </div>

                <div>
                  <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                    Attach Rectified Document (PDF / PNG / JPEG)
                  </label>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    onChange={(e) => setResubmitFile(e.target.files?.[0] || null)}
                    className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-white file:text-slate-700 hover:file:bg-slate-100 border border-slate-200 rounded-lg p-1 bg-white"
                  />
                </div>

                <div className="flex justify-end pt-1">
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    loading={isResubmitting}
                    icon={Upload}
                  >
                    Submit Rectified Documents
                  </Button>
                </div>
              </form>
            )}

            {/* Officer Scrutiny Action Section */}
            {isOfficerOrAdmin && (
              <form onSubmit={handleOfficerUpdateStatus} className="p-4 rounded-xl border border-slate-300 bg-slate-50 space-y-3">
                <div className="flex items-center gap-2 text-slate-900 font-bold">
                  <UserCheck className="w-4 h-4 text-[#142B4A]" />
                  <span>Officer Scrutiny & Bureau Action</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                      Target Decision Status <span className="text-rose-500">*</span>
                    </label>
                    <select
                      required
                      value={officerStatus}
                      onChange={(e) => setOfficerStatus(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                    >
                      <option value="">Select Bureau Decision...</option>
                      <option value="Under Review">Under Review</option>
                      <option value="Documents Required">Documents Required (Deficiency)</option>
                      <option value="Approved">Approved</option>
                      <option value="Rejected">Rejected</option>
                      <option value="Closed">Closed</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                      Scrutiny Remarks {officerStatus === 'Documents Required' || officerStatus === 'Rejected' ? <span className="text-rose-500">*</span> : ''}
                    </label>
                    <input
                      type="text"
                      value={officerRemarks}
                      onChange={(e) => setOfficerRemarks(e.target.value)}
                      placeholder="Enter scrutiny notes or specific deficiency reason..."
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-1">
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    loading={isUpdatingStatus}
                    disabled={!officerStatus}
                  >
                    Record Scrutiny Action
                  </Button>
                </div>
              </form>
            )}

            {/* Admin Case Assignment Section */}
            {isAdmin && (
              <form onSubmit={handleAssignOfficer} className="p-3.5 rounded-xl border border-indigo-200 bg-indigo-50/50 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-indigo-700" />
                  <span className="font-semibold text-indigo-950 text-xs">Assign Scrutiny Officer ID:</span>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <input
                    type="number"
                    placeholder="Officer User ID"
                    value={assignOfficerId}
                    onChange={(e) => setAssignOfficerId(e.target.value)}
                    className="w-32 px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                  />
                  <Button
                    type="submit"
                    variant="secondary"
                    size="sm"
                    loading={isAssigning}
                  >
                    Assign
                  </Button>
                </div>
              </form>
            )}

            {/* Structured Audit & History Timeline */}
            <div>
              <div className="flex items-center gap-2 text-slate-800 font-bold mb-2">
                <History className="w-4 h-4 text-slate-600" />
                <span>Lifecycle Audit Trail & Historical Events</span>
              </div>

              {activeReq?.history && activeReq.history.length > 0 ? (
                <div className="space-y-2 border-l-2 border-slate-200 pl-3 ml-2">
                  {activeReq.history.map((ev, idx) => (
                    <div key={idx} className="relative pb-2">
                      <div className="absolute -left-[19px] top-1 w-2.5 h-2.5 rounded-full bg-[#142B4A] ring-4 ring-white" />
                      <div className="text-2xs text-slate-400 font-medium">
                        {formatDate(ev.created_at)}
                      </div>
                      <div className="text-xs font-semibold text-slate-800">
                        {ev.action} {ev.to_status ? `→ ${ev.to_status}` : ''}
                      </div>
                      {ev.remarks && (
                        <p className="text-2xs text-slate-600 mt-0.5 bg-slate-50 p-2 rounded border border-slate-100">
                          {ev.remarks}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-2xs text-slate-500 italic p-3 bg-slate-50 rounded-lg">
                  Initial submission registered on {formatDate(activeReq?.submissionDate || activeReq?.created_at)}. Awaiting additional audit history entries.
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSelectedRequest(null)
                  setDetailedRequest(null)
                }}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default RequestsPage
