import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  PlusCircle,
  Search,
  Eye,
  AlertCircle,
  FileText,
  Download,
  Loader2,
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

export function RequestsPage() {
  const { requests, fdrs, addRequest, showToast } = useApp()

  // Filters state
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')

  // New Request Modal state
  const [newModalOpen, setNewModalOpen] = useState(false)
  const [selectedFdrId, setSelectedFdrId] = useState('')
  const [requestType, setRequestType] = useState('Renewal')
  const [reason, setReason] = useState('')
  const [supportingFile, setSupportingFile] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Details Modal state
  const [selectedRequest, setSelectedRequest] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)

  // Filtered requests
  const filteredRequests = useMemo(() => {
    return requests.filter((r) => {
      const q = searchQuery.toLowerCase().trim()
      const matchesSearch =
        !q ||
        r.id.toLowerCase().includes(q) ||
        r.fdrNumber.toLowerCase().includes(q) ||
        r.bankName.toLowerCase().includes(q)

      const matchesType = typeFilter === 'ALL' || r.requestType === typeFilter
      const matchesStatus = statusFilter === 'ALL' || r.status === statusFilter

      return matchesSearch && matchesType && matchesStatus
    })
  }, [requests, searchQuery, typeFilter, statusFilter])

  // Eligible FDRs for creating a new request
  const eligibleFDRs = useMemo(() => {
    return fdrs.filter(f => f.status !== 'Released')
  }, [fdrs])

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

    const targetFDR = fdrs.find(f => String(f.id) === String(selectedFdrId))
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
      // Reset form only on success
      setSelectedFdrId('')
      setReason('')
      setSupportingFile(null)
    } catch (err) {
      console.error('Request submission failed:', err)
      showToast(err.message || 'Failed to submit request. Please verify and try again.', 'error')
    } finally {
      setIsSubmitting(false)
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
      console.error('Attachment download failed:', err)
      showToast(err.message || 'Failed to download attachment from server.', 'error')
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            FDR Renewal & Release Requests
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Track statutory petitions submitted to the AICTE Regional Bureau for term renewal or lien release.
          </p>
        </div>

        <Button
          variant="primary"
          icon={PlusCircle}
          onClick={() => setNewModalOpen(true)}
        >
          Create New Request
        </Button>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          <div className="md:col-span-6 relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Request ID or FDR Number..."
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
              <option value="ALL">All Request Types</option>
              <option value="Renewal">Renewal Petitions</option>
              <option value="Release">Release Petitions</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="ALL">All Request Stages</option>
              <option value="Under Review">Under Review</option>
              <option value="Submitted">Submitted</option>
              <option value="Approved">Approved</option>
              <option value="Processed">Processed</option>
              <option value="Rejected">Rejected</option>
            </select>
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
              actionLabel="Create New Request"
              onAction={() => setNewModalOpen(true)}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider bg-slate-50">
                  <th className="py-3 px-5">Request ID</th>
                  <th className="py-3 px-5">Related FDR</th>
                  <th className="py-3 px-5">Type</th>
                  <th className="py-3 px-5">Deposit Amount</th>
                  <th className="py-3 px-5">Submitted Date</th>
                  <th className="py-3 px-5">Status & Stage</th>
                  <th className="py-3 px-5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredRequests.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-4 px-5">
                      <span className="font-mono font-semibold text-slate-900 text-xs">
                        {req.id}
                      </span>
                    </td>
                    <td className="py-4 px-5">
                      <Link
                        to={`/fdrs/${req.fdrId}`}
                        className="font-mono text-xs font-semibold text-[#142B4A] hover:underline"
                      >
                        {req.fdrNumber}
                      </Link>
                      <p className="text-2xs text-slate-500 mt-0.5">{req.bankName}</p>
                    </td>
                    <td className="py-4 px-5 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                          req.requestType === 'Renewal'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-purple-100 text-purple-800'
                        }`}
                      >
                        {req.requestType}
                      </span>
                    </td>
                    <td className="py-4 px-5 font-bold text-slate-900 text-xs">
                      {formatCurrency(req.depositAmount)}
                    </td>
                    <td className="py-4 px-5 text-xs text-slate-600 whitespace-nowrap">
                      {formatDate(req.submissionDate)}
                    </td>
                    <td className="py-4 px-5">
                      <div className="flex flex-col gap-1 items-start">
                        <RequestStatusBadge status={req.status} size="sm" />
                        {req.stage && (
                          <span className="text-[11px] text-slate-500">
                            {req.stage}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-5 text-right whitespace-nowrap">
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={Eye}
                        onClick={() => setSelectedRequest(req)}
                      >
                        Details
                      </Button>
                    </td>
                  </tr>
                ))}
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
        subtitle="Forwarded to AICTE Northern Regional Office Scrutiny Committee"
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
          onClose={() => setSelectedRequest(null)}
          title={`Petition Details: ${selectedRequest.id}`}
          subtitle={`${selectedRequest.requestType} Request for ${selectedRequest.fdrNumber}`}
          maxWidth="max-w-lg"
        >
          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
              <div>
                <span className="text-slate-400 block font-medium">Status</span>
                <div className="mt-1">
                  <RequestStatusBadge status={selectedRequest.status} />
                </div>
              </div>
              <div className="text-right">
                <span className="text-slate-400 block font-medium">Current Review Stage</span>
                <span className="font-semibold text-slate-800">{selectedRequest.stage || 'Desk Review'}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 py-2">
              <div>
                <span className="text-slate-400 font-medium block">Related FDR Ref</span>
                <Link
                  to={`/fdrs/${selectedRequest.fdrId}`}
                  className="font-mono font-bold text-[#142B4A] hover:underline"
                >
                  {selectedRequest.fdrNumber}
                </Link>
              </div>

              <div>
                <span className="text-slate-400 font-medium block">Deposit Amount</span>
                <span className="font-bold text-slate-800">
                  {formatCurrency(selectedRequest.depositAmount)}
                </span>
              </div>

              <div>
                <span className="text-slate-400 font-medium block">Submission Date</span>
                <span className="text-slate-700">{formatDate(selectedRequest.submissionDate)}</span>
              </div>

              <div>
                <span className="text-slate-400 font-medium block">Last Updated</span>
                <span className="text-slate-700">{formatDate(selectedRequest.lastUpdated)}</span>
              </div>
            </div>

            <div>
              <span className="text-slate-400 font-medium block">Institutional Justification</span>
              <p className="mt-1 p-3 rounded-lg bg-slate-50 border border-slate-100 text-slate-700 leading-relaxed">
                {selectedRequest.reason}
              </p>
            </div>

            {selectedRequest.supportingDocument && (
              <div>
                <span className="text-slate-400 font-medium block">Supporting Attachment</span>
                <div className="mt-1 flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-white">
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                    <span className="font-medium text-slate-800 truncate">
                      {selectedRequest.supportingDocument}
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={downloadingId === selectedRequest.id}
                    onClick={() => handleDownloadAttachment(selectedRequest)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#142B4A]/10 text-[#142B4A] hover:bg-[#142B4A]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0 ml-2"
                  >
                    {downloadingId === selectedRequest.id ? (
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

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setSelectedRequest(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
