import apiClient from '../api/client'
import { initialFDRs } from '../data/mock/mockFDRs'

export function normalizeFDR(f) {
  if (!f) return f
  const numAmount =
    f.amount !== undefined ? parseFloat(f.amount) : (parseFloat(f.depositAmount) || 0)

  return {
    ...f,
    id: f.id,
    fdrNumber: f.fdr_number || f.fdrNumber || '',
    fdr_number: f.fdr_number || f.fdrNumber || '',
    bankName: f.bank_name || f.bankName || '',
    bank_name: f.bank_name || f.bankName || '',
    branchName: f.branch_name || f.branchName || '',
    branch_name: f.branch_name || f.branchName || '',
    depositAmount: numAmount,
    amount: numAmount,
    issueDate: f.issue_date || f.issueDate || '',
    issue_date: f.issue_date || f.issueDate || '',
    maturityDate: f.maturity_date || f.maturityDate || '',
    maturity_date: f.maturity_date || f.maturityDate || '',
    scrutiny_status: f.scrutiny_status || f.status || 'DRAFT',
    validity_status: f.validity_status || 'ACTIVE',
    status: f.scrutiny_status || f.status || 'DRAFT',
    interestRate: f.interestRate || '7.10% p.a.',
    jointHolder: f.jointHolder || 'Regional Officer, AICTE',
    activityHistory: f.activityHistory || [],
    documents: f.documents || [],
  }
}

export const fdrService = {
  getInitialFDRs: () => {
    return initialFDRs.map(normalizeFDR)
  },

  /**
   * Fetch authorized FDR records with filtering and pagination.
   */
  async listFDRs(params = {}) {
    const response = await apiClient.get('/fdr', { params })
    const items = response.data?.data || []
    return {
      data: items.map(normalizeFDR),
      pagination: response.data?.pagination,
    }
  },

  /**
   * Retrieve single FDR record with full metadata.
   */
  async getFDRById(id) {
    const response = await apiClient.get(`/fdr/${id}`)
    return normalizeFDR(response.data?.data)
  },

  /**
   * Create new FDR record in DRAFT status.
   */
  async createFDR(formData) {
    const payload = {
      fdr_number: (formData.fdrNumber || formData.fdr_number || '').trim(),
      bank_name: (formData.bankName || formData.bank_name || '').trim(),
      branch_name: (formData.branchName || formData.branch_name || 'Main Branch').trim(),
      amount: parseFloat(formData.depositAmount || formData.amount),
      issue_date: formData.issueDate || formData.issue_date,
      maturity_date: formData.maturityDate || formData.maturity_date,
    }
    const response = await apiClient.post('/fdr', payload)
    return normalizeFDR(response.data?.data)
  },

  /**
   * Update permitted fields of an existing authorized FDR in DRAFT/RETURNED status.
   */
  async updateFDR(id, formData) {
    const payload = {}
    if (formData.fdrNumber || formData.fdr_number) {
      payload.fdr_number = formData.fdrNumber || formData.fdr_number
    }
    if (formData.bankName || formData.bank_name) {
      payload.bank_name = formData.bankName || formData.bank_name
    }
    if (formData.branchName || formData.branch_name) {
      payload.branch_name = formData.branchName || formData.branch_name
    }
    if (formData.depositAmount !== undefined || formData.amount !== undefined) {
      payload.amount = parseFloat(formData.depositAmount ?? formData.amount)
    }
    if (formData.issueDate || formData.issue_date) {
      payload.issue_date = formData.issueDate || formData.issue_date
    }
    if (formData.maturityDate || formData.maturity_date) {
      payload.maturity_date = formData.maturityDate || formData.maturity_date
    }

    const response = await apiClient.patch(`/fdr/${id}`, payload)
    return normalizeFDR(response.data?.data)
  },

  /**
   * Upload supporting PDF/image receipt and trigger OCR discrepancy detection.
   */
  async uploadDocument(fdrId, file) {
    const data = new FormData()
    data.append('file', file)
    const response = await apiClient.post(`/fdr/${fdrId}/documents`, data, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data?.data || response.data
  },

  /**
   * List all documents attached to an authorized FDR.
   */
  async listDocuments(fdrId) {
    const response = await apiClient.get(`/fdr/${fdrId}/documents`)
    return response.data?.data || []
  },

  /**
   * Retrieve document metadata and latest OCR discrepancy report.
   */
  async getDocumentDetail(fdrId, docId) {
    const response = await apiClient.get(`/fdr/${fdrId}/documents/${docId}`)
    return response.data?.data || response.data
  },

  /**
   * Securely stream attached document file with browser download trigger.
   */
  async downloadDocument(fdrId, docId, fallbackName = 'fdr_document.pdf') {
    const response = await apiClient.get(`/fdr/${fdrId}/documents/${docId}/download`, {
      responseType: 'blob',
    })
    let filename = fallbackName
    const disposition = response.headers['content-disposition']
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match && match[1]) {
        filename = match[1]
      }
    }
    const blob = new Blob([response.data], {
      type: response.headers['content-type'] || 'application/octet-stream',
    })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    return { success: true, filename }
  },

  /**
   * Pre-check whether an FDR number matches an existing or normalized record.
   */
  async checkDuplicate(fdrNumber, institutionId = null) {
    const payload = { fdr_number: fdrNumber }
    if (institutionId) payload.institution_id = institutionId
    const response = await apiClient.post('/fdr/check-duplicate', payload)
    return response.data
  },

  /**
   * AICTE Officer records verification decision on supporting document and/or individual fields.
   */
  async verifyDocumentDecision(fdrId, docId, decision = null, remarks = '', fieldReviews = null) {
    const payload = {}
    if (decision) payload.decision = decision
    if (remarks !== undefined && remarks !== null) payload.remarks = remarks
    if (fieldReviews) payload.field_reviews = fieldReviews
    const response = await apiClient.post(`/fdr/${fdrId}/documents/${docId}/verify`, payload)
    return response.data
  },

  /**
   * Get available synthetic document test scenarios (dev/demo only).
   */
  async getSyntheticScenarios(fdrId) {
    const response = await apiClient.get(`/fdr/${fdrId}/synthetic-documents/scenarios`)
    return response.data
  },

  /**
   * Download a synthetic FDR test document for testing OCR verification.
   */
  async downloadSyntheticDocument(fdrId, scenarioId = 'MATCHING_FDR', format = 'pdf') {
    const response = await apiClient.get(`/fdr/${fdrId}/synthetic-documents/download`, {
      params: { scenario: scenarioId, format },
      responseType: 'blob',
    })
    let filename = `DEMO_${scenarioId}.${format === 'image' ? 'png' : 'pdf'}`
    const disposition = response.headers['content-disposition']
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match && match[1]) {
        filename = match[1]
      }
    }
    const blob = new Blob([response.data], {
      type: response.headers['content-type'] || 'application/octet-stream',
    })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    return { success: true, filename }
  },

  /**
   * Directly generate, upload and process a synthetic test document on the FDR (dev/demo only).
   */
  async loadSyntheticDocument(fdrId, scenarioId = 'MATCHING_FDR', format = 'pdf') {
    const response = await apiClient.post(`/fdr/${fdrId}/synthetic-documents/load`, {
      scenario: scenarioId,
      format,
    })
    return response.data
  },

  // -------------------------------------------------------------
  // Workflow Transition Methods
  // -------------------------------------------------------------

  /**
   * Institution submits DRAFT or resubmits RETURNED FDR.
   */
  async submitFDR(fdrId, remarks = null) {
    const payload = remarks ? { remarks } : {}
    const response = await apiClient.post(`/fdr/${fdrId}/submit`, payload)
    return response.data
  },

  /**
   * AICTE Officer locks deposit for review.
   */
  async startReview(fdrId, remarks = null) {
    const payload = remarks ? { remarks } : {}
    const response = await apiClient.post(`/fdr/${fdrId}/start-review`, payload)
    return response.data
  },

  /**
   * AICTE Officer approves deposit in PENDING_VERIFICATION.
   */
  async verifyFDR(fdrId, remarks = null) {
    const payload = remarks ? { remarks } : {}
    const response = await apiClient.post(`/fdr/${fdrId}/verify`, payload)
    return response.data
  },

  /**
   * AICTE Officer returns deposit with deficiency notice (mandatory remarks).
   */
  async returnFDR(fdrId, remarks) {
    const response = await apiClient.post(`/fdr/${fdrId}/return`, {
      remarks: remarks?.trim(),
      reason: remarks?.trim(),
    })
    return response.data
  },

  /**
   * AICTE Officer rejects deposit with mandatory remarks.
   */
  async rejectFDR(fdrId, remarks) {
    const response = await apiClient.post(`/fdr/${fdrId}/reject`, {
      remarks: remarks?.trim(),
      reason: remarks?.trim(),
    })
    return response.data
  },

  /**
   * Retrieve workflow state, permitted actions, history, and active deficiencies.
   */
  async getWorkflow(fdrId, params = {}) {
    const response = await apiClient.get(`/fdr/${fdrId}/workflow`, { params })
    return response.data?.data || response.data
  },

  // -------------------------------------------------------------
  // Utility Calculations (Fallback / Client-side aggregations)
  // -------------------------------------------------------------

  calculateStats: (fdrs) => {
    if (!fdrs || !Array.isArray(fdrs)) return { total: 0, active: 0, maturingSoon: 0, pending: 0 }
    const total = fdrs.length
    const active = fdrs.filter(f => (f.scrutiny_status === 'VERIFIED' || f.status === 'Active' || f.validity_status === 'ACTIVE')).length

    const now = new Date()
    now.setHours(0, 0, 0, 0)

    const maturingSoon = fdrs.filter(f => {
      if (f.scrutiny_status === 'REJECTED' || f.validity_status === 'MATURED') {
        return false
      }
      const maturity = new Date(f.maturity_date || f.maturityDate)
      maturity.setHours(0, 0, 0, 0)
      const diffDays = Math.ceil((maturity.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
      return diffDays >= 0 && diffDays <= 30
    }).length

    const pending = fdrs.filter(f =>
      f.scrutiny_status === 'SUBMITTED' ||
      f.scrutiny_status === 'PENDING_VERIFICATION' ||
      f.status === 'Pending Verification'
    ).length

    return { total, active, maturingSoon, pending }
  },

  getStatusDistribution: (fdrs) => {
    if (!fdrs || !Array.isArray(fdrs)) return []
    const counts = {}
    fdrs.forEach(f => {
      const st = f.scrutiny_status || f.status || 'DRAFT'
      counts[st] = (counts[st] || 0) + 1
    })

    const statusColors = {
      'VERIFIED': '#10B981',
      'Active': '#10B981',
      'PENDING_VERIFICATION': '#F59E0B',
      'Pending Verification': '#F59E0B',
      'SUBMITTED': '#3B82F6',
      'DRAFT': '#94A3B8',
      'RETURNED': '#E11D48',
      'REJECTED': '#EF4444',
      'Rejected': '#EF4444',
    }

    return Object.keys(counts).map(status => ({
      name: status,
      value: counts[status],
      color: statusColors[status] || '#94A3B8',
    }))
  },

  getUpcomingMaturities: (fdrs, limit = 5) => {
    if (!fdrs || !Array.isArray(fdrs)) return []
    const now = new Date()
    now.setHours(0, 0, 0, 0)

    return fdrs
      .filter(f => f.scrutiny_status !== 'REJECTED' && f.validity_status !== 'MATURED')
      .map(f => {
        const maturity = new Date(f.maturity_date || f.maturityDate)
        maturity.setHours(0, 0, 0, 0)
        const daysRemaining = Math.ceil((maturity.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
        return { ...f, daysRemaining }
      })
      .filter(f => f.daysRemaining >= 0)
      .sort((a, b) => a.daysRemaining - b.daysRemaining)
      .slice(0, limit)
  },
}

export default fdrService
