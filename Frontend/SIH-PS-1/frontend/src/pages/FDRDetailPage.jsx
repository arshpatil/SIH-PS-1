import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  FileText,
  Download,
  Eye,
  RefreshCw,
  Archive,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  XCircle,
  AlertTriangle,
  Upload,
  Send,
  Check,
  Clock,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { FDRStatusBadge } from '../components/fdr/FDRStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { formatCurrency, formatFileSize } from '../utils/formatters'
import { formatDate, getDaysRemaining } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'
import { fdrService } from '../services/fdrService'
import { requestService } from '../services/requestService'
import { BankVerificationCard } from '../components/fdr/BankVerificationCard'

export function FDRDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { currentUser, showToast, addRequest, submitRenewalDetails, verifyRenewal, requests } = useApp()

  const [fdr, setFdr] = useState(null)
  const [loading, setLoading] = useState(true)
  const [documents, setDocuments] = useState([])
  const [workflowData, setWorkflowData] = useState(null)

  // Document modal & OCR report state
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [docDetail, setDocDetail] = useState(null)
  const [docLoading, setDocLoading] = useState(false)
  const [docModalOpen, setDocModalOpen] = useState(false)
  const [docDecision, setDocDecision] = useState('')
  const [docRemarks, setDocRemarks] = useState('')
  const [docVerifying, setDocVerifying] = useState(false)

  // Document upload state
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [newFile, setNewFile] = useState(null)
  const [uploadingDoc, setUploadingDoc] = useState(false)

  // Workflow Action Modals
  const [actionModal, setActionModal] = useState({
    isOpen: false,
    actionType: null, // 'submit', 'start_review', 'verify', 'return', 'reject'
    title: '',
    description: '',
    remarks: '',
    mandatoryRemarks: false,
  })
  const [actionSubmitting, setActionSubmitting] = useState(false)

  // Legacy Renewal / Release request modal
  const [requestModalOpen, setRequestModalOpen] = useState(false)
  const [requestType, setRequestType] = useState('Renewal')
  const [requestReason, setRequestReason] = useState('')
  const [requestSubmitting, setRequestSubmitting] = useState(false)

  // Renewed FDR receipt upload modal (Institution)
  const [renewalUploadModalOpen, setRenewalUploadModalOpen] = useState(false)
  const [renewalForm, setRenewalForm] = useState({
    newFdrNumber: '',
    newIssueDate: '',
    newMaturityDate: '',
    newAmount: '',
    remarks: '',
  })
  const [renewalFile, setRenewalFile] = useState(null)
  const [renewalSubmitting, setRenewalSubmitting] = useState(false)

  // Renewed FDR verification modal (Officer)
  const [renewalVerifyModalOpen, setRenewalVerifyModalOpen] = useState(false)
  const [renewalDecision, setRenewalDecision] = useState('VERIFIED')
  const [renewalVerifyRemarks, setRenewalVerifyRemarks] = useState('')
  const [renewalVerifying, setRenewalVerifying] = useState(false)
  const [isSimulatedVerification, setIsSimulatedVerification] = useState(false)
  const [downloadingDemoReceipt, setDownloadingDemoReceipt] = useState(false)
  const isDevDemoMode = Boolean(
    import.meta.env.DEV ||
    typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  )

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' ||
    currentUser?.role === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

  // -------------------------------------------------------------
  // Data Loaders
  // -------------------------------------------------------------

  const loadFDRDetails = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      const [fdrRes, docsRes, wfRes] = await Promise.allSettled([
        fdrService.getFDRById(id),
        fdrService.listDocuments(id),
        fdrService.getWorkflow(id),
      ])

      if (fdrRes.status === 'fulfilled' && fdrRes.value) {
        setFdr(fdrRes.value)
      } else {
        // Fallback from route param
        setFdr(null)
      }

      if (docsRes.status === 'fulfilled' && Array.isArray(docsRes.value)) {
        setDocuments(docsRes.value)
      }

      if (wfRes.status === 'fulfilled' && wfRes.value) {
        setWorkflowData(wfRes.value)
      }
    } catch (err) {
      console.warn('Error loading FDR details:', err)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    let cancelled = false
    const fetchDetails = async () => {
      try {
        const [fdrRes, docsRes, wfRes] = await Promise.allSettled([
          fdrService.getFDRById(id),
          fdrService.listDocuments(id),
          fdrService.getWorkflow(id),
        ])

        if (cancelled) return

        if (fdrRes.status === 'fulfilled' && fdrRes.value) {
          setFdr(fdrRes.value)
        } else {
          // Fallback from route param
          setFdr(null)
        }

        if (docsRes.status === 'fulfilled' && Array.isArray(docsRes.value)) {
          setDocuments(docsRes.value)
        }

        if (wfRes.status === 'fulfilled' && wfRes.value) {
          setWorkflowData(wfRes.value)
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Error loading FDR details:', err)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchDetails()
    return () => {
      cancelled = true
    }
  }, [id])

  // Open Document Detail & OCR Discrepancy Modal
  const handleOpenDocModal = async (doc) => {
    setSelectedDoc(doc)
    setDocModalOpen(true)
    setDocLoading(true)
    try {
      const detail = await fdrService.getDocumentDetail(id, doc.id)
      setDocDetail(detail)
    } catch {
      setDocDetail(null)
    } finally {
      setDocLoading(false)
    }
  }

  // Handle Document Download
  // Handle Officer Document Verification Decision
  const handleVerifyDocDecision = async (e) => {
    e.preventDefault()
    if (!docDecision) {
      showToast('Please select a verification decision.', 'error')
      return
    }
    if ((docDecision === 'REQUIRES_CORRECTION' || docDecision === 'REJECTED') && !docRemarks.trim()) {
      showToast('Remarks are mandatory for deficiency or rejection.', 'error')
      return
    }
    setDocVerifying(true)
    try {
      await fdrService.verifyDocumentDecision(fdr.id, selectedDoc.id, docDecision, docRemarks.trim())
      showToast(`Document decision recorded: ${docDecision}`, 'success')
      setDocRemarks('')
      setDocDecision('')
      // Refresh documents
      const docs = await fdrService.listFDRDocuments(fdr.id)
      setDocuments(docs)
      setDocModalOpen(false)
    } catch (err) {
      showToast(err.message || 'Failed to record document decision.', 'error')
    } finally {
      setDocVerifying(false)
    }
  }

  const handleDownloadDoc = async (doc) => {
    try {
      showToast(`Downloading ${doc.original_filename || 'document.pdf'}...`, 'info')
      await fdrService.downloadDocument(id, doc.id, doc.original_filename)
      showToast('Download completed', 'success')
    } catch (err) {
      showToast(err.message || 'Download failed', 'error')
    }
  }

  // Handle Document Upload
  const handleUploadDocument = async (e) => {
    e.preventDefault()
    if (!newFile) return
    setUploadingDoc(true)
    try {
      await fdrService.uploadDocument(id, newFile)
      showToast('Document uploaded and OCR processed successfully!', 'success')
      setUploadModalOpen(false)
      setNewFile(null)
      loadFDRDetails()
    } catch (err) {
      const errMsg = err.response?.data?.error || err.message || 'Upload failed'
      showToast(errMsg, 'error')
    } finally {
      setUploadingDoc(false)
    }
  }

  // -------------------------------------------------------------
  // Workflow Action Handlers
  // -------------------------------------------------------------

  const openActionModal = (actionType) => {
    switch (actionType) {
      case 'submit':
        setActionModal({
          isOpen: true,
          actionType: 'submit',
          title: 'Submit FDR for AICTE Verification',
          description:
            'Submitting this FDR locks it for official AICTE scrutiny review. Ensure all required deposit receipts are attached.',
          remarks: '',
          mandatoryRemarks: false,
        })
        break
      case 'start_review':
        setActionModal({
          isOpen: true,
          actionType: 'start_review',
          title: 'Start Scrutiny Review',
          description:
            'Lock this FDR record for active scrutiny review and verification. Status will change to Under Verification.',
          remarks: '',
          mandatoryRemarks: false,
        })
        break
      case 'verify':
        setActionModal({
          isOpen: true,
          actionType: 'verify',
          title: 'Approve & Verify FDR',
          description:
            'Approving this deposit will register it as officially verified and active with AICTE. Optional remarks can be logged.',
          remarks: 'All documents and bank lien clauses verified successfully.',
          mandatoryRemarks: false,
        })
        break
      case 'return':
        setActionModal({
          isOpen: true,
          actionType: 'return',
          title: 'Return FDR with Deficiency Remarks',
          description:
            'Return this submission to the institution for rectification. You MUST provide explicit remarks detailing the deficiencies found.',
          remarks: '',
          mandatoryRemarks: true,
        })
        break
      case 'reject':
        setActionModal({
          isOpen: true,
          actionType: 'reject',
          title: 'Reject FDR Submission',
          description:
            'Terminal rejection of this security deposit. You MUST record the mandatory justification remarks.',
          remarks: '',
          mandatoryRemarks: true,
        })
        break
      default:
        break
    }
  }

  const handleExecuteAction = async (e) => {
    e.preventDefault()
    const { actionType, remarks, mandatoryRemarks } = actionModal
    if (mandatoryRemarks && (!remarks || remarks.trim().length < 5)) {
      showToast('Remarks must be at least 5 characters long.', 'warning')
      return
    }

    setActionSubmitting(true)
    try {
      if (actionType === 'submit') {
        await fdrService.submitFDR(id, remarks)
        showToast('FDR submitted successfully for AICTE verification!', 'success')
      } else if (actionType === 'start_review') {
        await fdrService.startReview(id, remarks)
        showToast('FDR review initiated successfully.', 'success')
      } else if (actionType === 'verify') {
        await fdrService.verifyFDR(id, remarks)
        showToast('FDR verified and approved successfully!', 'success')
      } else if (actionType === 'return') {
        await fdrService.returnFDR(id, remarks)
        showToast('FDR returned to institution with deficiency notice.', 'warning')
      } else if (actionType === 'reject') {
        await fdrService.rejectFDR(id, remarks)
        showToast('FDR submission rejected.', 'error')
      }

      setActionModal({ isOpen: false, actionType: null, title: '', description: '', remarks: '', mandatoryRemarks: false })
      await loadFDRDetails()
    } catch (err) {
      const errMsg = err.response?.data?.error || err.response?.data?.message || err.message || 'Workflow transition failed'
      showToast(errMsg, 'error')
    } finally {
      setActionSubmitting(false)
    }
  }

  // -------------------------------------------------------------
  // Legacy Petition Handlers
  // -------------------------------------------------------------

  const handleOpenRequest = (type) => {
    setRequestType(type)
    setRequestReason(
      type === 'Renewal'
        ? `Requesting 3-year term renewal for FDR ${fdr.fdrNumber} to maintain continuous AICTE regulatory compliance.`
        : `Requesting release of FDR ${fdr.fdrNumber} following completion of mandatory lock-in period and approval requirements.`
    )
    setRequestModalOpen(true)
  }

  const handleSubmitRequest = async (e) => {
    e.preventDefault()
    if (!requestReason.trim()) {
      showToast('Please provide a justification for this petition.', 'error')
      return
    }
    setRequestSubmitting(true)
    try {
      await addRequest({
        fdrId: fdr.id,
        fdrNumber: fdr.fdrNumber,
        bankName: fdr.bankName,
        depositAmount: fdr.depositAmount,
        requestType,
        reason: requestReason.trim(),
        supportingDocument: `${fdr.fdrNumber}_${requestType}_Application.pdf`,
      })
      setRequestModalOpen(false)
      setRequestReason('')
    } catch {
      // Toast error is already handled and displayed inside addRequest
    } finally {
      setRequestSubmitting(false)
    }
  }

  // -------------------------------------------------------------
  // Renewal Workflow Handlers
  // -------------------------------------------------------------

  const handleOpenRenewalUploadModal = (requestObj) => {
    setRenewalForm({
      newFdrNumber: requestObj?.renewalFdrNumber || requestObj?.renewal_fdr_number || fdr?.fdrNumber || '',
      newIssueDate: requestObj?.renewalIssueDate || requestObj?.renewal_issue_date || new Date().toISOString().split('T')[0],
      newMaturityDate: requestObj?.renewalMaturityDate || requestObj?.renewal_maturity_date || '',
      newAmount: requestObj?.renewalAmount || requestObj?.renewal_amount || fdr?.depositAmount || '',
      remarks: requestObj?.renewalRemarks || requestObj?.renewal_remarks || '',
    })
    setRenewalFile(null)
    setRenewalUploadModalOpen(true)
  }

  const handleSubmitRenewalForm = async (e) => {
    e.preventDefault()
    if (!renewalForm.newFdrNumber.trim()) {
      showToast('Please enter the renewed FDR number.', 'warning')
      return
    }
    if (!renewalForm.newIssueDate || !renewalForm.newMaturityDate) {
      showToast('Issue date and maturity date are required.', 'warning')
      return
    }
    if (renewalForm.newMaturityDate <= renewalForm.newIssueDate) {
      showToast('Maturity date must be later than the issue date.', 'warning')
      return
    }
    if (!renewalFile && !linkedRequest?.renewalDocument && !linkedRequest?.renewal_document) {
      showToast('Please upload the renewed bank FDR receipt.', 'warning')
      return
    }

    setRenewalSubmitting(true)
    try {
      await submitRenewalDetails(linkedRequest.id || linkedRequest.raw_id, {
        newFdrNumber: renewalForm.newFdrNumber.trim(),
        newIssueDate: renewalForm.newIssueDate,
        newMaturityDate: renewalForm.newMaturityDate,
        newAmount: renewalForm.newAmount,
        remarks: renewalForm.remarks,
        file: renewalFile,
      })
      setRenewalUploadModalOpen(false)
      await loadFDRDetails()
    } catch {
      // Toast handled inside submitRenewalDetails
    } finally {
      setRenewalSubmitting(false)
    }
  }

  const handleOpenRenewalVerifyModal = () => {
    const isSynthetic = Boolean(linkedRequest?.renewalIsSynthetic || linkedRequest?.renewal_is_synthetic)
    setIsSimulatedVerification(isSynthetic)
    setRenewalDecision('VERIFIED')
    setRenewalVerifyRemarks(
      isSynthetic
        ? 'Verified in simulated demonstration mode. Document was synthetic test receipt.'
        : 'All terms and renewed deposit endorsement clauses verified successfully.'
    )
    setRenewalVerifyModalOpen(true)
  }

  const handleExecuteRenewalVerify = async (e) => {
    e.preventDefault()
    if ((renewalDecision === 'RETURNED' || renewalDecision === 'REJECTED') && (!renewalVerifyRemarks || renewalVerifyRemarks.trim().length < 5)) {
      showToast('Please provide mandatory remarks (at least 5 characters) for this decision.', 'warning')
      return
    }

    setRenewalVerifying(true)
    try {
      await verifyRenewal(linkedRequest.id || linkedRequest.raw_id, {
        decision: renewalDecision,
        remarks: renewalVerifyRemarks.trim(),
        is_simulated: isSimulatedVerification,
      })
      setRenewalVerifyModalOpen(false)
      await loadFDRDetails()
    } catch {
      // Toast handled in verifyRenewal
    } finally {
      setRenewalVerifying(false)
    }
  }

  const handleDownloadDemoReceipt = async () => {
    if (!fdr?.id) return
    setDownloadingDemoReceipt(true)
    try {
      await requestService.downloadSyntheticReceipt(fdr.id, `DEMO_Renewal_Receipt_${fdr.fdrNumber}.pdf`)
      showToast('Synthetic demo receipt downloaded. You can now upload it for testing!', 'success')
    } catch (err) {
      showToast(err.message || 'Failed to download demo receipt', 'error')
    } finally {
      setDownloadingDemoReceipt(false)
    }
  }

  const handleDownloadRenewalReceipt = async (reqId, filename) => {
    try {
      await requestService.downloadAttachment(reqId, filename || 'renewed_fdr_receipt.pdf')
    } catch (err) {
      showToast('Failed to download renewal receipt: ' + (err.message || 'File not found'), 'error')
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-3">
        <RefreshCw className="w-8 h-8 text-[#142B4A] animate-spin" />
        <p className="text-sm font-medium text-slate-600">Loading FDR and verification timeline...</p>
      </div>
    )
  }

  if (!fdr) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <EmptyState
          title="FDR Record Not Found"
          description={`No fixed deposit record matching ID "${id}" was found in this session or access is unauthorized.`}
          actionLabel="Return to FDR Listing"
          onAction={() => navigate('/fdrs')}
        />
      </div>
    )
  }

  const linkedRequest =
    fdr?.latestRequest ||
    fdr?.latest_request ||
    requests?.find((r) => String(r.fdrId || r.fdr_id) === String(fdr?.id))

  const isRenewalActive =
    linkedRequest &&
    (linkedRequest.requestType === 'Renewal' || linkedRequest.request_type === 'Renewal') &&
    ['Submitted', 'Under Review', 'Approved', 'Pending Verification', 'Documents Required'].includes(linkedRequest.status)

  const isRenewalApprovedAwaitingReceipt =
    linkedRequest &&
    (linkedRequest.requestType === 'Renewal' || linkedRequest.request_type === 'Renewal') &&
    linkedRequest.status === 'Approved' &&
    !linkedRequest.renewalSubmittedAt &&
    !linkedRequest.renewal_submitted_at

  const isRenewalPendingVerification =
    linkedRequest &&
    (linkedRequest.requestType === 'Renewal' || linkedRequest.request_type === 'Renewal') &&
    (linkedRequest.status === 'Pending Verification' || Boolean(linkedRequest.renewalSubmittedAt || linkedRequest.renewal_submitted_at)) &&
    linkedRequest.status !== 'Closed'

  const daysLeft = getDaysRemaining(fdr.maturityDate)
  const isMaturityNear =
    fdr.scrutiny_status !== 'REJECTED' &&
    fdr.validity_status !== 'MATURED' &&
    daysLeft >= 0 &&
    daysLeft <= 30

  const availableActions = workflowData?.available_actions || []
  const historyList = workflowData?.workflow_history || []
  const deficienciesList = workflowData?.deficiencies || []

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Header & Navigation */}
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
              <FDRStatusBadge status={fdr.scrutiny_status || fdr.status} />
              {daysLeft < -30 && (
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                  Overdue Action (&gt;30d past maturity)
                </span>
              )}
              {daysLeft >= -30 && daysLeft < 0 && (
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                  Matured (In Grace Period)
                </span>
              )}
              {daysLeft >= 0 && daysLeft <= 7 && (
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-100 text-orange-900 border border-orange-300 animate-pulse">
                  Critical ({daysLeft}d left)
                </span>
              )}
              {daysLeft > 7 && daysLeft <= 30 && (
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">
                  Expiring in {daysLeft}d
                </span>
              )}
              {daysLeft > 30 && daysLeft <= 60 && (
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800">
                  Expiring in {daysLeft}d
                </span>
              )}
              {daysLeft > 60 && daysLeft <= 90 && (
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-cyan-100 text-cyan-800">
                  Expiring in {daysLeft}d
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {fdr.institution_name ? `${fdr.institution_name} • ` : ''}Issued by {fdr.bankName} • AICTE Joint Lien Deposit
            </p>
          </div>
        </div>

        {/* Dynamic Workflow Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Institution User: Submit / Resubmit */}
          {!isOfficerOrAdmin && (availableActions.includes('submit') || fdr.scrutiny_status === 'DRAFT' || fdr.scrutiny_status === 'RETURNED') && (
            <Button
              variant="primary"
              size="sm"
              icon={Send}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={() => openActionModal('submit')}
            >
              {fdr.scrutiny_status === 'RETURNED' ? 'Resubmit Corrected FDR' : 'Submit for Verification'}
            </Button>
          )}

          {/* AICTE Officer: Start Review */}
          {isOfficerOrAdmin && (availableActions.includes('start_review') || fdr.scrutiny_status === 'SUBMITTED') && (
            <Button
              variant="primary"
              size="sm"
              icon={Eye}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => openActionModal('start_review')}
            >
              Start Review
            </Button>
          )}

          {/* AICTE Officer: Verify & Approve */}
          {isOfficerOrAdmin && (availableActions.includes('verify') || fdr.scrutiny_status === 'PENDING_VERIFICATION') && (
            <Button
              variant="primary"
              size="sm"
              icon={Check}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={() => openActionModal('verify')}
            >
              Verify & Approve
            </Button>
          )}

          {/* AICTE Officer: Return with Deficiency */}
          {isOfficerOrAdmin && (availableActions.includes('return') || fdr.scrutiny_status === 'PENDING_VERIFICATION') && (
            <Button
              variant="secondary"
              size="sm"
              icon={AlertTriangle}
              className="border-amber-400 text-amber-800 hover:bg-amber-50"
              onClick={() => openActionModal('return')}
            >
              Return with Remarks
            </Button>
          )}

          {/* AICTE Officer: Reject */}
          {isOfficerOrAdmin && (availableActions.includes('reject') || fdr.scrutiny_status === 'PENDING_VERIFICATION') && (
            <Button
              variant="outline"
              size="sm"
              icon={XCircle}
              className="text-rose-600 border-rose-300 hover:bg-rose-50"
              onClick={() => openActionModal('reject')}
            >
              Reject Deposit
            </Button>
          )}

          {/* Attach Document button if modifiable */}
          {(fdr.scrutiny_status === 'DRAFT' || fdr.scrutiny_status === 'RETURNED' || isOfficerOrAdmin) && (
            <Button
              variant="outline"
              size="sm"
              icon={Upload}
              onClick={() => setUploadModalOpen(true)}
            >
              Upload Doc
            </Button>
          )}

          {/* Institutional Actions: Renewal / Release */}
          {!isOfficerOrAdmin && fdr.scrutiny_status === 'VERIFIED' && (
            <>
              {!isRenewalActive ? (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  onClick={() => handleOpenRequest('Renewal')}
                >
                  Petition Renewal
                </Button>
              ) : isRenewalApprovedAwaitingReceipt ? (
                <Button
                  variant="primary"
                  size="sm"
                  icon={Upload}
                  className="bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-xs"
                  onClick={() => handleOpenRenewalUploadModal(linkedRequest)}
                >
                  Upload Renewed Receipt
                </Button>
              ) : null}
              <Button
                variant="outline"
                size="sm"
                icon={Archive}
                onClick={() => handleOpenRequest('Release')}
              >
                Petition Release
              </Button>
            </>
          )}

          {/* AICTE Officer: Verify Pending Renewal Receipt */}
          {isOfficerOrAdmin && isRenewalPendingVerification && (
            <Button
              variant="primary"
              size="sm"
              icon={CheckCircle2}
              className="bg-purple-600 hover:bg-purple-700 text-white font-semibold shadow-xs"
              onClick={handleOpenRenewalVerifyModal}
            >
              Verify Renewed Deposit
            </Button>
          )}
        </div>
      </div>

      {/* Active Renewal Petition Status Card */}
      {linkedRequest && (linkedRequest.requestType === 'Renewal' || linkedRequest.request_type === 'Renewal') && (
        <div
          className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs ${
            isRenewalApprovedAwaitingReceipt
              ? 'bg-amber-50/90 border-amber-300 text-amber-950'
              : isRenewalPendingVerification
              ? 'bg-purple-50/90 border-purple-300 text-purple-950'
              : linkedRequest.status === 'Closed'
              ? 'bg-emerald-50/90 border-emerald-300 text-emerald-950'
              : 'bg-blue-50/90 border-blue-300 text-blue-950'
          }`}
        >
          <div className="flex items-start gap-3">
            {isRenewalApprovedAwaitingReceipt ? (
              <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            ) : isRenewalPendingVerification ? (
              <Clock className="w-5 h-5 text-purple-600 shrink-0 mt-0.5" />
            ) : linkedRequest.status === 'Closed' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <FileText className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            )}
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-sm">Renewal Petition {linkedRequest.id}:</span>
                <span className="font-semibold px-2 py-0.5 rounded text-xs bg-white/80 border border-current">
                  {linkedRequest.status}
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  Stage: {linkedRequest.stage}
                </span>
              </div>
              <p className="text-xs leading-relaxed">
                {isRenewalApprovedAwaitingReceipt ? (
                  <>
                    <strong className="text-amber-900">Renewal request approved — updated FDR receipt required.</strong>{' '}
                    AICTE Scrutiny Desk has approved this renewal petition. The bank renewed receipt must be submitted and verified before the official maturity date is extended.
                  </>
                ) : isRenewalPendingVerification ? (
                  <>
                    <strong className="text-purple-900">Renewed receipt awaiting verification.</strong>{' '}
                    Renewed details submitted on {formatDate(linkedRequest.renewalSubmittedAt || linkedRequest.renewal_submitted_at)} with proposed new maturity date {formatDate(linkedRequest.renewalMaturityDate || linkedRequest.renewal_maturity_date)}. AICTE officer verification is in progress.
                  </>
                ) : linkedRequest.status === 'Closed' ? (
                  <>
                    <strong className="text-emerald-900">Renewal verified — next maturity: {formatDate(fdr.maturityDate)}.</strong>{' '}
                    The deposit terms have been officially verified and renewed in the AICTE statutory repository.
                  </>
                ) : (
                  <>
                    <strong className="text-blue-900">Renewal request under review.</strong>{' '}
                    AICTE Regional Desk is currently evaluating this statutory petition. The original maturity date remains active until endorsed.
                  </>
                )}
              </p>
              {linkedRequest.remarks && (
                <p className="text-xs text-slate-600 italic">
                  Officer Remarks: {linkedRequest.remarks}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {!isOfficerOrAdmin && (isRenewalApprovedAwaitingReceipt || linkedRequest.status === 'Documents Required') && (
              <Button
                variant="primary"
                size="sm"
                className="bg-amber-600 hover:bg-amber-700 text-white font-semibold"
                onClick={() => handleOpenRenewalUploadModal(linkedRequest)}
              >
                Upload Renewed Receipt
              </Button>
            )}
            {isOfficerOrAdmin && isRenewalPendingVerification && (
              <Button
                variant="primary"
                size="sm"
                className="bg-purple-600 hover:bg-purple-700 text-white font-semibold"
                onClick={handleOpenRenewalVerifyModal}
              >
                Verify Renewal
              </Button>
            )}
            {(linkedRequest.renewalDocument || linkedRequest.renewal_document) && (
              <Button
                variant="secondary"
                size="sm"
                icon={Download}
                onClick={() => handleDownloadRenewalReceipt(linkedRequest.id || linkedRequest.raw_id, linkedRequest.renewalDocument || linkedRequest.renewal_document)}
              >
                Download Receipt
              </Button>
            )}
            {isDevDemoMode && (
              <Button
                variant="secondary"
                size="sm"
                icon={Download}
                loading={downloadingDemoReceipt}
                className="border-dashed border-amber-400 bg-amber-50/70 text-amber-900 hover:bg-amber-100 font-medium"
                onClick={handleDownloadDemoReceipt}
                title="Download synthetic test receipt for local demonstration (Dev/Demo mode only)"
              >
                Download Dummy PDF (Demo)
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Active Deficiency Alert Banner */}
      {deficienciesList.length > 0 && (
        <div className="p-4 bg-rose-50 rounded-xl border border-rose-300 shadow-2xs space-y-2">
          <div className="flex items-center gap-2 text-rose-900 font-bold text-sm">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>Deficiency Notice Issued by AICTE Scrutiny Desk</span>
          </div>
          <div className="space-y-1.5 pl-7">
            {deficienciesList.map((def) => (
              <div key={def.id} className="text-xs text-rose-800">
                <p className="font-semibold">{def.remarks}</p>
                <p className="text-2xs text-rose-600 mt-0.5">
                  Logged on {formatDate(def.created_at)} • Status: {def.resolution_status || 'UNRESOLVED'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Maturing Soon Urgent Notice */}
      {isMaturityNear && (
        <div className="p-4 bg-amber-50 rounded-xl border border-amber-300 flex items-center justify-between text-amber-900 text-xs sm:text-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold">Maturity Alert:</span> This FDR reaches term on{' '}
              <strong>{formatDate(fdr.maturityDate)}</strong> ({daysLeft} days remaining).
              {isRenewalActive && (
                <span className="block text-2xs text-amber-800 mt-0.5">
                  Notice: A statutory renewal petition is in progress ({linkedRequest?.status}). Original maturity date remains effective until verified.
                </span>
              )}
            </div>
          </div>
          {!isOfficerOrAdmin && !isRenewalActive && (
            <Button
              variant="primary"
              size="sm"
              className="bg-amber-600 hover:bg-amber-700 text-white shrink-0 ml-3"
              onClick={() => handleOpenRequest('Renewal')}
            >
              Renew Now
            </Button>
          )}
        </div>
      )}

      {/* Core Banking Integration & Simulated Verification Card */}
      <BankVerificationCard
        fdr={fdr}
        onVerified={() => loadFDRDetails()}
      />

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
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Deposit Principal
                </span>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {formatCurrency(fdr.depositAmount)}
                </p>
                <span className="text-2xs text-slate-500 mt-0.5 inline-block">
                  Fixed Security Guarantee
                </span>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Validity & Status
                </span>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {fdr.validity_status || 'ACTIVE'}
                </p>
                <span className="text-2xs text-slate-500 mt-0.5 inline-block">
                  Scrutiny: {fdr.scrutiny_status || fdr.status}
                </span>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Issuing Bank
                </span>
                <p className="font-semibold text-slate-800">{fdr.bankName}</p>
                <p className="text-xs text-slate-500">{fdr.branchName || 'Main Institutional Branch'}</p>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Institution
                </span>
                <p className="font-semibold text-slate-800">{fdr.institution_name || 'Affiliated College'}</p>
                <p className="text-xs text-slate-500">Registered Entity ID: {fdr.institution_id || 'AICTE'}</p>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Issue Date
                </span>
                <p className="font-semibold text-slate-800">{formatDate(fdr.issueDate)}</p>
              </div>

              <div className="space-y-1">
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">
                  Maturity Date
                </span>
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

          {/* Verified Term Extensions & Renewal History */}
          {((fdr.renewal_history && fdr.renewal_history.length > 0) || (fdr.renewalHistory && fdr.renewalHistory.length > 0)) && (
            <Card>
              <CardHeader
                title="Verified Term Extensions & Renewal History"
                subtitle="Immutable statutory record of all previous and verified renewals"
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
                      <th className="py-2.5 px-3">Verification Date</th>
                      <th className="py-2.5 px-3">Previous Maturity</th>
                      <th className="py-2.5 px-3">Verified New Term</th>
                      <th className="py-2.5 px-3">Renewed Deposit</th>
                      <th className="py-2.5 px-3">Verified By</th>
                      <th className="py-2.5 px-3 text-right">Receipt</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(fdr.renewal_history || fdr.renewalHistory || []).map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50/60">
                        <td className="py-2.5 px-3 whitespace-nowrap text-slate-600 font-mono">
                          {formatDate(item.created_at)}
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 line-through">
                          {formatDate(item.previous_maturity_date)}
                        </td>
                        <td className="py-2.5 px-3 font-semibold text-emerald-700">
                          {formatDate(item.new_maturity_date)}
                        </td>
                        <td className="py-2.5 px-3 font-mono font-medium text-slate-900">
                          {formatCurrency(item.new_amount)}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">
                          {item.verifier_name || 'AICTE Officer'}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {item.renewal_document ? (
                            <button
                              type="button"
                              onClick={() => handleDownloadRenewalReceipt(item.request_id, item.renewal_document)}
                              className="inline-flex items-center gap-1 text-xs text-[#142B4A] hover:underline font-medium"
                            >
                              <Download className="w-3.5 h-3.5" />
                              <span>Receipt</span>
                            </button>
                          ) : (
                            <span className="text-slate-400">N/A</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Structured Scrutiny & Workflow History */}
          <Card>
            <CardHeader
              title="Verifiable Scrutiny Timeline"
              subtitle="Chronological audit trail of all administrative transitions and officer decisions"
            />

            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {historyList.length > 0 ? (
                historyList.map((item) => (
                  <div key={item.id} className="relative group">
                    <span
                      className={`absolute -left-6 top-1 w-3.5 h-3.5 rounded-full bg-white border-2 ${
                        item.is_deficiency ? 'border-rose-600 ring-rose-100' : 'border-[#142B4A] ring-slate-100'
                      } ring-4`}
                    />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-900">
                          {item.from_status || 'START'} &rarr; {item.to_status}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          {formatDate(item.created_at)}
                        </span>
                        {item.is_deficiency && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] bg-rose-100 text-rose-800 font-bold">
                            Deficiency
                          </span>
                        )}
                      </div>
                      {item.remarks && (
                        <p className="text-xs text-slate-700 mt-1 leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                          {item.remarks}
                        </p>
                      )}
                      <p className="text-2xs text-slate-400 mt-1">
                        Transitioned by: <span className="font-semibold text-slate-600">{item.actor_name || 'System'}</span> ({item.actor_role})
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500">
                  No workflow events logged yet. Submit the FDR to start review.
                </p>
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: Attached Documents & OCR Discrepancy Findings */}
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Attached Documents & OCR"
              subtitle="Files verified with automatic discrepancy detection"
            />

            <div className="space-y-3">
              {documents.length > 0 ? (
                documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-slate-50 space-y-2.5 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white border border-slate-200 shadow-2xs flex items-center justify-center text-rose-600 shrink-0">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-slate-900 truncate" title={doc.original_filename}>
                          {doc.original_filename}
                        </p>
                        <p className="text-2xs text-slate-500 mt-0.5">
                          {formatFileSize(doc.file_size)} • {doc.processing_status}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1 border-t border-slate-200/60">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 text-xs"
                        icon={Eye}
                        onClick={() => handleOpenDocModal(doc)}
                      >
                        OCR Findings
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="flex-1 text-xs"
                        icon={Download}
                        onClick={() => handleDownloadDoc(doc)}
                      >
                        Download
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-6 border border-dashed border-slate-200 rounded-xl space-y-2">
                  <FileText className="w-8 h-8 text-slate-300 mx-auto" />
                  <p className="text-xs text-slate-500">No documents attached yet.</p>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={Upload}
                    onClick={() => setUploadModalOpen(true)}
                  >
                    Upload Receipt
                  </Button>
                </div>
              )}
            </div>

            <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-2xs flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>Tamper-resistant local document storage enabled</span>
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
                <span className="font-medium text-slate-800">Nodal Commercial Bank</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-500">AICTE Lien:</span>
                <span className="font-semibold text-emerald-700">Fully Endorsed</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* OCR Discrepancy & Document Report Modal */}
      <Modal
        isOpen={docModalOpen}
        onClose={() => setDocModalOpen(false)}
        title={`OCR & Discrepancy Report: ${selectedDoc?.original_filename || 'Receipt'}`}
        subtitle="Automatic optical character recognition and field mismatch audit"
        maxWidth="max-w-2xl"
      >
        {docLoading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-2">
            <RefreshCw className="w-6 h-6 text-[#142B4A] animate-spin" />
            <p className="text-xs text-slate-500">Loading OCR findings...</p>
          </div>
        ) : (
          <div className="space-y-4 text-xs">
            {docDetail?.discrepancy_report ? (
              <>
                {/* Result Overview Banner */}
                <div
                  className={`p-3.5 rounded-xl border flex items-center justify-between ${
                    docDetail.discrepancy_report.overall_result === 'MATCH'
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                      : docDetail.discrepancy_report.overall_result === 'DISCREPANCY_DETECTED'
                      ? 'bg-rose-50 border-rose-300 text-rose-900'
                      : 'bg-amber-50 border-amber-300 text-amber-900'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    {docDetail.discrepancy_report.overall_result === 'MATCH' ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-amber-600" />
                    )}
                    <div>
                      <span className="font-bold">Result: </span>
                      <span className="font-mono">{docDetail.discrepancy_report.overall_result}</span>
                    </div>
                  </div>
                  <span className="text-2xs font-semibold px-2 py-0.5 rounded bg-white/60">
                    Confidence: {docDetail.discrepancy_report.confidence_score || 'N/A'}
                  </span>
                </div>

                {/* Discrepancies List */}
                {docDetail.discrepancy_report.discrepancies?.length > 0 ? (
                  <div className="space-y-2">
                    <p className="font-bold text-slate-800">Detected Field Discrepancies:</p>
                    <div className="space-y-1.5">
                      {docDetail.discrepancy_report.discrepancies.map((disc, idx) => (
                        <div key={idx} className="p-2.5 bg-rose-50/80 rounded-lg border border-rose-200 text-rose-900">
                          <p className="font-semibold">{disc.field || 'Field Mismatch'}:</p>
                          <p className="text-2xs mt-0.5">{disc.description || disc.message || JSON.stringify(disc)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="p-3 bg-emerald-50/60 rounded-lg border border-emerald-200 text-emerald-900">
                    All scanned receipt details (Institution Name, Amount, Tenure, Joint Clause) match the registered FDR.
                  </div>
                )}

                {/* Extracted Fields Summary */}
                {docDetail.discrepancy_report.extracted_fields && (
                  <div className="space-y-2">
                    <p className="font-bold text-slate-800">Extracted OCR Metadata:</p>
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 font-mono text-2xs space-y-1">
                      {Object.entries(docDetail.discrepancy_report.extracted_fields).map(([k, v]) => (
                        <div key={k} className="flex justify-between py-0.5 border-b border-slate-100 last:border-none">
                          <span className="text-slate-500">{k}:</span>
                          <span className="font-semibold text-slate-800">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-slate-500 py-4 text-center">No OCR discrepancy analysis found for this file.</p>
            )}

            {/* Officer Document Verification Action */}
            {isOfficerOrAdmin && selectedDoc && (
              <form onSubmit={handleVerifyDocDecision} className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2.5 my-3">
                <div className="flex items-center gap-2 font-bold text-slate-800">
                  <ShieldCheck className="w-4 h-4 text-[#142B4A]" />
                  <span>Official Document Scrutiny Decision</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                      Verification Decision <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={docDecision}
                      onChange={(e) => setDocDecision(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                    >
                      <option value="">Choose Officer Finding...</option>
                      <option value="VERIFIED">VERIFIED (Matches Standard APH Rules)</option>
                      <option value="REQUIRES_CORRECTION">REQUIRES_CORRECTION (Deficiency)</option>
                      <option value="REJECTED">REJECTED (Fraud / Ineligible)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                      Scrutiny Notes {(docDecision === 'REQUIRES_CORRECTION' || docDecision === 'REJECTED') ? <span className="text-rose-500">*</span> : ''}
                    </label>
                    <input
                      type="text"
                      value={docRemarks}
                      onChange={(e) => setDocRemarks(e.target.value)}
                      placeholder="e.g. Bank seal illegible, re-upload scan..."
                      className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                    />
                  </div>
                </div>
                <div className="flex justify-end pt-1">
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={!docDecision}
                    loading={docVerifying}
                  >
                    Record Decision
                  </Button>
                </div>
              </form>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setDocModalOpen(false)}>
                Close
              </Button>
              {selectedDoc && (
                <Button
                  variant="primary"
                  size="sm"
                  icon={Download}
                  onClick={() => handleDownloadDoc(selectedDoc)}
                >
                  Download Scanned Receipt
                </Button>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Upload Document Modal */}
      <Modal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Upload Supporting Document"
        subtitle={`Attach official scanned copy for FDR ${fdr.fdrNumber}`}
        maxWidth="max-w-md"
      >
        <form onSubmit={handleUploadDocument} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Select Document (PDF / PNG / JPEG, max 10MB) <span className="text-rose-500">*</span>
            </label>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              required
              onChange={(e) => setNewFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#142B4A] file:text-white hover:file:bg-[#1a385f]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button variant="secondary" size="sm" onClick={() => setUploadModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" loading={uploadingDoc}>
              Upload & Run OCR
            </Button>
          </div>
        </form>
      </Modal>

      {/* Workflow Transition Action Modal */}
      <Modal
        isOpen={actionModal.isOpen}
        onClose={() => setActionModal({ ...actionModal, isOpen: false })}
        title={actionModal.title}
        subtitle={`FDR Ref: ${fdr.fdrNumber}`}
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleExecuteAction} className="space-y-4 text-xs">
          <p className="text-slate-600 leading-relaxed">{actionModal.description}</p>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Decision Remarks / Justification{' '}
              {actionModal.mandatoryRemarks ? (
                <span className="text-rose-500 font-bold">* (Minimum 5 characters)</span>
              ) : (
                <span className="text-slate-400 font-normal">(Optional)</span>
              )}
            </label>
            <textarea
              rows={4}
              required={actionModal.mandatoryRemarks}
              value={actionModal.remarks}
              onChange={(e) => setActionModal({ ...actionModal, remarks: e.target.value })}
              placeholder={
                actionModal.mandatoryRemarks
                  ? 'State specific reasons or missing items that must be rectified...'
                  : 'Add optional notes or compliance remarks...'
              }
              className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="secondary"
              size="sm"
              disabled={actionSubmitting}
              onClick={() => setActionModal({ ...actionModal, isOpen: false })}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant={actionModal.actionType === 'reject' ? 'danger' : 'primary'}
              size="sm"
              loading={actionSubmitting}
            >
              Confirm Transition
            </Button>
          </div>
        </form>
      </Modal>

      {/* Renewal / Release Petition Modal */}
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
            <Button type="submit" variant="primary" size="md" loading={requestSubmitting}>
              Submit {requestType} Request
            </Button>
          </div>
        </form>
      </Modal>

      {/* Upload Renewed FDR Receipt Modal (Institution) */}
      <Modal
        isOpen={renewalUploadModalOpen}
        onClose={() => setRenewalUploadModalOpen(false)}
        title="Upload Renewed FDR Deposit Receipt"
        subtitle={`FDR Ref: ${fdr.fdrNumber} • Petition ${linkedRequest?.id || ''}`}
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleSubmitRenewalForm} className="space-y-4 text-xs">
          <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-amber-900 leading-relaxed">
            <span className="font-semibold">Regulatory Notice:</span> Please enter the renewed certificate details endorsed by your commercial bank and attach the signed receipt document. The new maturity date will become active once verified by an AICTE officer.
          </div>

          {isDevDemoMode && (
            <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-950 flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-2xs">
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-indigo-600 text-white">Dev / Demo Mode</span>
                  <span className="font-semibold text-xs text-indigo-900">Need a dummy receipt for testing?</span>
                </div>
                <p className="text-2xs text-indigo-700">Download a compliant synthetic PDF receipt generated from this FDR's parameters.</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="xs"
                icon={Download}
                loading={downloadingDemoReceipt}
                onClick={handleDownloadDemoReceipt}
                className="border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-100 shrink-0 self-start sm:self-auto font-medium"
              >
                Download Dummy PDF
              </Button>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Renewed FDR Number <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={renewalForm.newFdrNumber}
                onChange={(e) => setRenewalForm({ ...renewalForm, newFdrNumber: e.target.value })}
                placeholder="e.g. FDR-2026-9901"
                className="w-full px-3 py-2 rounded-lg border border-slate-300 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Renewed Deposit Amount (₹) <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                step="0.01"
                min="1"
                required
                value={renewalForm.newAmount}
                onChange={(e) => setRenewalForm({ ...renewalForm, newAmount: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Renewed Issue Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                required
                value={renewalForm.newIssueDate}
                onChange={(e) => setRenewalForm({ ...renewalForm, newIssueDate: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Verified New Maturity Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                required
                value={renewalForm.newMaturityDate}
                onChange={(e) => setRenewalForm({ ...renewalForm, newMaturityDate: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Renewed FDR Receipt Scan (PDF / Image) <span className="text-rose-500">*</span>
            </label>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              required={!linkedRequest?.renewalDocument && !linkedRequest?.renewal_document}
              onChange={(e) => setRenewalFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#142B4A] file:text-white hover:file:bg-[#1a385f]"
            />
            {linkedRequest?.renewalDocument && !renewalFile && (
              <p className="text-2xs text-slate-500 mt-1">
                Previously uploaded: <span className="font-mono">{linkedRequest.renewalDocument}</span>. Leave empty to keep.
              </p>
            )}
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Bank Endorsement Remarks <span className="text-slate-400 font-normal">(Optional)</span>
            </label>
            <textarea
              rows={2}
              value={renewalForm.remarks}
              onChange={(e) => setRenewalForm({ ...renewalForm, remarks: e.target.value })}
              placeholder="e.g. Renewed for 3-year term as per AICTE Lien Endorsement clause..."
              className="w-full p-2.5 rounded-lg border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="secondary"
              size="sm"
              disabled={renewalSubmitting}
              onClick={() => setRenewalUploadModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" loading={renewalSubmitting}>
              Submit Renewed Receipt
            </Button>
          </div>
        </form>
      </Modal>

      {/* Verify Renewed FDR Details Modal (AICTE Officer) */}
      <Modal
        isOpen={renewalVerifyModalOpen}
        onClose={() => setRenewalVerifyModalOpen(false)}
        title="Verify & Endorse Renewed Deposit"
        subtitle={`FDR Ref: ${fdr.fdrNumber} • Petition ${linkedRequest?.id || ''}`}
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleExecuteRenewalVerify} className="space-y-4 text-xs">
          <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-purple-950 space-y-2">
            <span className="font-bold text-xs">Comparison of Deposit Parameters:</span>
            <div className="grid grid-cols-2 gap-2 text-2xs font-mono">
              <div className="p-2 rounded bg-white border border-purple-100">
                <p className="text-slate-400 uppercase font-semibold">Previous Term</p>
                <p className="font-bold text-slate-800">FDR #: {fdr.fdrNumber}</p>
                <p className="text-slate-600">Maturity: {formatDate(fdr.maturityDate)}</p>
                <p className="text-slate-600">Amount: {formatCurrency(fdr.depositAmount)}</p>
              </div>
              <div className="p-2 rounded bg-emerald-50 border border-emerald-200">
                <p className="text-emerald-700 uppercase font-semibold">Proposed Term</p>
                <p className="font-bold text-emerald-950">FDR #: {linkedRequest?.renewalFdrNumber || linkedRequest?.renewal_fdr_number || fdr.fdrNumber}</p>
                <p className="text-emerald-900 font-bold">Maturity: {formatDate(linkedRequest?.renewalMaturityDate || linkedRequest?.renewal_maturity_date)}</p>
                <p className="text-emerald-900">Amount: {formatCurrency(linkedRequest?.renewalAmount || linkedRequest?.renewal_amount || fdr.depositAmount)}</p>
              </div>
            </div>
          </div>

          {(linkedRequest?.renewalDocument || linkedRequest?.renewal_document) && (
            <div className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-slate-50">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-600" />
                <span className="font-semibold text-slate-800 truncate max-w-[220px]">
                  {linkedRequest?.renewalDocument || linkedRequest?.renewal_document}
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleDownloadRenewalReceipt(linkedRequest.id || linkedRequest.raw_id, linkedRequest.renewalDocument || linkedRequest.renewal_document)}
                className="inline-flex items-center gap-1 text-xs text-[#142B4A] hover:underline font-semibold"
              >
                <Download className="w-3.5 h-3.5" />
                <span>View Receipt</span>
              </button>
            </div>
          )}

          {isDevDemoMode && (
            <div className="p-3 rounded-lg border border-purple-200 bg-purple-50/70 space-y-2">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isSimulatedVerification}
                  onChange={(e) => {
                    const checked = e.target.checked
                    setIsSimulatedVerification(checked)
                    if (checked && (!renewalVerifyRemarks || renewalVerifyRemarks.includes('verified successfully'))) {
                      setRenewalVerifyRemarks('Verified in simulated demonstration mode. Document was synthetic test receipt.')
                    }
                  }}
                  className="mt-0.5 rounded border-purple-300 text-purple-600 focus:ring-purple-500"
                />
                <div className="text-xs">
                  <span className="font-bold text-purple-950 flex items-center gap-1.5">
                    <span>Simulated Demo Verification Path</span>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-purple-200 text-purple-900 uppercase">Dev Only</span>
                  </span>
                  <p className="text-2xs text-purple-800 mt-0.5 leading-normal">
                    Visibly marks endorsement as a local simulated verification for synthetic test receipts without claiming authentic bank core endorsement.
                  </p>
                </div>
              </label>

              {(linkedRequest?.renewalIsSynthetic || linkedRequest?.renewal_is_synthetic) && (
                <div className="p-2 rounded bg-amber-50 border border-amber-300 text-amber-900 text-2xs space-y-0.5">
                  <p className="font-bold">⚠️ Synthetic Test Receipt Detected:</p>
                  <p>Watermark "SYNTHETIC DEMO DOCUMENT — NOT ISSUED BY A BANK" was identified. Recommended: use Simulated Demo Verification above.</p>
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Official Scrutiny Decision <span className="text-rose-500">*</span>
            </label>
            <select
              value={renewalDecision}
              onChange={(e) => setRenewalDecision(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white font-semibold text-xs"
            >
              <option value="VERIFIED">VERIFIED (Endorse & Extend Official Maturity Term)</option>
              <option value="RETURNED">RETURNED (Deficiency Notice — Demand Corrected Receipt)</option>
              <option value="REJECTED">REJECTED (Reject Extension & Lien Enforcement)</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Officer Scrutiny Remarks {renewalDecision !== 'VERIFIED' ? <span className="text-rose-500">*</span> : <span className="text-slate-400 font-normal">(Optional)</span>}
            </label>
            <textarea
              rows={3}
              required={renewalDecision !== 'VERIFIED'}
              value={renewalVerifyRemarks}
              onChange={(e) => setRenewalVerifyRemarks(e.target.value)}
              placeholder={
                renewalDecision === 'VERIFIED'
                  ? 'e.g. Joint lien verified, renewed terms approved.'
                  : 'State reasons for deficiency or rejection...'
              }
              className="w-full p-2.5 rounded-lg border border-slate-300 text-xs focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button
              variant="secondary"
              size="sm"
              disabled={renewalVerifying}
              onClick={() => setRenewalVerifyModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant={renewalDecision === 'REJECTED' ? 'danger' : 'primary'}
              size="sm"
              loading={renewalVerifying}
            >
              Confirm Verification
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

export default FDRDetailPage
