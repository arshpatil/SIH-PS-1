import React, { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Building2,
  Calendar,
  CreditCard,
  FileText,
  Clock,
  Download,
  Eye,
  RefreshCw,
  Archive,
  AlertCircle,
  CheckCircle2,
  Share2,
  ShieldCheck,
  History,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { FDRStatusBadge } from '../components/fdr/FDRStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { formatCurrency, formatFileSize } from '../utils/formatters'
import { formatDate, getDaysRemaining } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'

export function FDRDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { getFDRById, addRequest, showToast } = useApp()

  const fdr = getFDRById(id)

  // Modals state
  const [docPreviewOpen, setDocPreviewOpen] = useState(false)
  const [requestModalOpen, setRequestModalOpen] = useState(false)
  const [requestType, setRequestType] = useState('Renewal')
  const [requestReason, setRequestReason] = useState('')
  const [requestSubmitting, setRequestSubmitting] = useState(false)

  if (!fdr) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <EmptyState
          title="FDR Record Not Found"
          description={`No fixed deposit record matching ID "${id}" was found in this institutional session.`}
          actionLabel="Return to FDR Listing"
          onAction={() => navigate('/fdrs')}
        />
      </div>
    )
  }

  const daysLeft = getDaysRemaining(fdr.maturityDate)
  const isMaturityNear =
    fdr.status !== 'Matured' &&
    fdr.status !== 'Released' &&
    daysLeft >= 0 &&
    daysLeft <= 30

  // Open Request Modal (Renewal or Release)
  const handleOpenRequest = (type) => {
    setRequestType(type)
    setRequestReason(
      type === 'Renewal'
        ? `Requesting 3-year term renewal for FDR ${fdr.fdrNumber} to maintain continuous AICTE regulatory compliance.`
        : `Requesting release of FDR ${fdr.fdrNumber} following completion of mandatory lock-in period and approval requirements.`
    )
    setRequestModalOpen(true)
  }

  // Handle Request Submission
  const handleSubmitRequest = (e) => {
    e.preventDefault()
    if (!requestReason.trim()) return

    setRequestSubmitting(true)
    setTimeout(() => {
      addRequest({
        fdrId: fdr.id,
        fdrNumber: fdr.fdrNumber,
        bankName: fdr.bankName,
        depositAmount: fdr.depositAmount,
        requestType,
        reason: requestReason,
        supportingDocument: `${fdr.fdrNumber}_${requestType}_Application.pdf`,
        documentSize: 1850000,
      })

      setRequestSubmitting(false)
      setRequestModalOpen(false)
      showToast(`${requestType} petition submitted for ${fdr.fdrNumber}`, 'success')
    }, 500)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Navigation & Back Link */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            to="/fdrs"
            className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors"
            title="Back to all FDRs"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl sm:text-2xl font-bold font-mono text-slate-900">
                {fdr.fdrNumber}
              </h2>
              <FDRStatusBadge status={fdr.status} />
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Issued by {fdr.bankName} • AICTE Joint Lien Deposit
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {fdr.status !== 'Released' && (
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              onClick={() => handleOpenRequest('Renewal')}
            >
              Request Renewal
            </Button>
          )}

          {fdr.status !== 'Released' && (
            <Button
              variant="outline"
              size="sm"
              icon={Archive}
              onClick={() => handleOpenRequest('Release')}
            >
              Request Release
            </Button>
          )}

          <Button
            variant="primary"
            size="sm"
            icon={Download}
            onClick={() => showToast(`Downloaded simulated document ${fdr.documentName}`, 'info')}
          >
            Download Receipt
          </Button>
        </div>
      </div>

      {/* Alert Banner for Maturing Soon */}
      {isMaturityNear && (
        <div className="p-4 bg-amber-50 rounded-xl border border-amber-300 flex items-center justify-between text-amber-900 text-xs sm:text-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold">Maturity Alert:</span> This FDR matures on{' '}
              <strong>{formatDate(fdr.maturityDate)}</strong> ({daysLeft} days remaining). Initiate renewal or release action if needed.
            </div>
          </div>
          <Button
            variant="primary"
            size="sm"
            className="bg-amber-600 hover:bg-amber-700 text-white shrink-0 ml-3"
            onClick={() => handleOpenRequest('Renewal')}
          >
            Renew Now
          </Button>
        </div>
      )}

      {/* 2-Column Info Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Essential FDR Metadata */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader
              title="Deposit & Financial Details"
              subtitle="Registered values endorsed by the issuing commercial bank"
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 text-sm">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Deposit Principal</span>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {formatCurrency(fdr.depositAmount)}
                </p>
                <span className="text-2xs text-slate-500 mt-0.5 inline-block">
                  Fixed Security Guarantee
                </span>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Contracted Interest</span>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {fdr.interestRate || '7.10% p.a.'}
                </p>
                <span className="text-2xs text-slate-500 mt-0.5 inline-block">
                  Compounded quarterly / term
                </span>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Issuing Bank</span>
                <p className="font-semibold text-slate-800">{fdr.bankName}</p>
                <p className="text-xs text-slate-500">{fdr.branchName || 'Institutional Service Branch'}</p>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Joint Lien Holder</span>
                <p className="font-semibold text-slate-800">{fdr.jointHolder || 'Regional Officer, AICTE'}</p>
                <p className="text-xs text-slate-500">Government of India Regulatory Lien</p>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Issue Date</span>
                <p className="font-semibold text-slate-800">{formatDate(fdr.issueDate)}</p>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Maturity Date</span>
                <p className="font-semibold text-slate-800">{formatDate(fdr.maturityDate)}</p>
                <p className="text-xs text-slate-500">
                  {daysLeft > 0 ? `${daysLeft} days remaining` : 'Matured'}
                </p>
              </div>
            </div>

            {fdr.remarks && (
              <div className="mt-5 pt-4 border-t border-slate-100">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Remarks & Institutional Purpose
                </span>
                <p className="text-xs text-slate-700 mt-1 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100">
                  {fdr.remarks}
                </p>
              </div>
            )}
          </Card>

          {/* Activity History Timeline */}
          <Card>
            <CardHeader
              title="Audit & Activity History"
              subtitle="Log of verifiable events and administrative transitions"
            />

            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {fdr.activityHistory && fdr.activityHistory.length > 0 ? (
                fdr.activityHistory.map((item, idx) => (
                  <div key={item.id || idx} className="relative group">
                    <span className="absolute -left-6 top-1 w-3.5 h-3.5 rounded-full bg-white border-2 border-[#142B4A] ring-4 ring-slate-100" />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-900">{item.title}</span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          {formatDate(item.date)}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                        {item.description}
                      </p>
                      {item.actor && (
                        <p className="text-2xs text-slate-400 mt-1">Logged by: {item.actor}</p>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500">No activity logged yet.</p>
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: Document Details & Compliance Status */}
        <div className="space-y-6">
          {/* Document Card */}
          <Card>
            <CardHeader
              title="Supporting Document"
              subtitle="Endorsed scanned copy of the receipt"
            />

            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 flex flex-col items-center text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-white border border-slate-200 shadow-2xs flex items-center justify-center text-rose-500">
                <FileText className="w-6 h-6" />
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-900 truncate max-w-[200px]" title={fdr.documentName}>
                  {fdr.documentName || 'Official_FDR_Receipt.pdf'}
                </p>
                <p className="text-2xs text-slate-500 mt-0.5">
                  {formatFileSize(fdr.documentSize || 1845200)} • Verified PDF
                </p>
              </div>

              <div className="flex items-center gap-2 w-full pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  icon={Eye}
                  onClick={() => setDocPreviewOpen(true)}
                >
                  Preview
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="flex-1"
                  icon={Download}
                  onClick={() => showToast(`Downloading ${fdr.documentName}...`, 'info')}
                >
                  Download
                </Button>
              </div>
            </div>

            <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-2xs flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>Digital receipt on file with AICTE Verification Bureau</span>
            </div>
          </Card>

          {/* Institutional Compliance Card */}
          <Card>
            <CardHeader
              title="Lien Endorsement"
              subtitle="Statutory AICTE security requirement"
            />

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Deposit Clause:</span>
                <span className="font-medium text-slate-800">Joint Fixed Deposit</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Regulatory Body:</span>
                <span className="font-medium text-slate-800">AICTE New Delhi</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Safe Custody:</span>
                <span className="font-medium text-slate-800">College Treasury / Bank</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-500">Simulated State:</span>
                <span className="font-semibold text-emerald-700">Demonstration Ready</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Document Preview Modal */}
      <Modal
        isOpen={docPreviewOpen}
        onClose={() => setDocPreviewOpen(false)}
        title={`Document Preview: ${fdr.documentName}`}
        subtitle="Simulated scanned copy of the institutional deposit receipt"
        maxWidth="max-w-2xl"
      >
        <div className="space-y-4">
          {/* Simulated document graphic */}
          <div className="border border-slate-200 rounded-xl bg-slate-50 p-6 flex flex-col items-center justify-center space-y-4 min-h-[300px]">
            <div className="w-full bg-white p-6 rounded-lg shadow-sm border border-slate-200 space-y-4 font-serif">
              <div className="text-center border-b pb-3">
                <h4 className="text-base font-bold text-slate-900 uppercase tracking-wide">
                  {fdr.bankName}
                </h4>
                <p className="text-xs text-slate-500 font-sans">{fdr.branchName || 'Commercial Branch'}</p>
                <p className="text-xs font-bold text-amber-800 font-sans mt-1">
                  FIXED DEPOSIT RECEIPT (JOINT SECURITY LIEN)
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs font-sans">
                <div>
                  <span className="text-slate-500 block">Receipt No:</span>
                  <span className="font-mono font-bold text-slate-900">{fdr.fdrNumber}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Deposit Amount:</span>
                  <span className="font-bold text-slate-900">{formatCurrency(fdr.depositAmount)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Date of Issue:</span>
                  <span className="text-slate-800">{formatDate(fdr.issueDate)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Date of Maturity:</span>
                  <span className="text-slate-800">{formatDate(fdr.maturityDate)}</span>
                </div>
                <div className="col-span-2">
                  <span className="text-slate-500 block">In Favor of / Jointly With:</span>
                  <span className="text-slate-800 font-medium">
                    Regional Officer, All India Council for Technical Education (AICTE)
                  </span>
                </div>
              </div>

              <div className="text-[10px] text-slate-400 border-t pt-2 font-sans italic text-center">
                This receipt is held as security deposit under AICTE Approval Process Handbook guidelines.
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" size="sm" onClick={() => setDocPreviewOpen(false)}>
              Close Preview
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Download}
              onClick={() => {
                showToast(`Downloaded ${fdr.documentName}`, 'success')
                setDocPreviewOpen(false)
              }}
            >
              Download PDF
            </Button>
          </div>
        </div>
      </Modal>

      {/* Renewal / Release Request Modal */}
      <Modal
        isOpen={requestModalOpen}
        onClose={() => setRequestModalOpen(false)}
        title={`Initiate ${requestType} Petition`}
        subtitle={`FDR Reference: ${fdr.fdrNumber} • ${formatCurrency(fdr.depositAmount)}`}
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleSubmitRequest} className="space-y-4">
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 text-blue-900 text-xs">
            Submitting this request will update the petition pipeline in the college dashboard and alert the AICTE regional desk.
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Petition Type
            </label>
            <input
              type="text"
              disabled
              value={requestType}
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-slate-100 font-semibold text-slate-700"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
              Justification / Reason <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={4}
              required
              value={requestReason}
              onChange={(e) => setRequestReason(e.target.value)}
              className="w-full p-3 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              placeholder="State institutional reasons, branch endorsement status, or regulatory requirement..."
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button
              variant="secondary"
              size="md"
              disabled={requestSubmitting}
              onClick={() => setRequestModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={requestSubmitting}
            >
              Submit {requestType} Request
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
