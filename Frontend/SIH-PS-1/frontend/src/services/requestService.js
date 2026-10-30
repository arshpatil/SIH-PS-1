import apiClient from '../api/client'
import { initialRequests } from '../data/mock/mockRequests'

function normalizeRequestId(id) {
  if (!id) return id
  if (typeof id === 'string' && id.toUpperCase().startsWith('REQ-')) {
    const raw = id.toUpperCase().replace('REQ-', '').trim()
    if (/^\d+$/.test(raw)) return parseInt(raw, 10)
  }
  return id
}

export const requestService = {
  /**
   * Fallback initial requests if backend is unreachable
   */
  getInitialRequests: () => {
    return [...initialRequests]
  },

  /**
   * Fetch all statutory renewal and release petitions from the backend.
   */
  async listRequests(params = {}) {
    const response = await apiClient.get('/requests', { params })
    return response.data?.data || []
  },

  /**
   * Submit a new renewal or release petition to the backend.
   */
  async createRequest(payload) {
    if (payload.supportingFile instanceof File) {
      const formData = new FormData()
      formData.append('fdr_id', payload.fdrId || payload.fdr_id)
      formData.append('request_type', payload.requestType || payload.request_type)
      formData.append('reason', payload.reason)
      if (payload.remarks) formData.append('remarks', payload.remarks)
      formData.append('file', payload.supportingFile)

      const response = await apiClient.post('/requests', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return response.data?.data
    }

    const response = await apiClient.post('/requests', {
      fdr_id: payload.fdrId || payload.fdr_id,
      request_type: payload.requestType || payload.request_type,
      reason: payload.reason,
      supporting_document: payload.supportingDocument || payload.supporting_document || null,
      document_size: payload.documentSize || payload.document_size || null,
      remarks: payload.remarks || null,
    })
    return response.data?.data
  },

  /**
   * Update request status (AICTE Officer / Admin only).
   */
  async updateRequestStatus(requestId, status, remarks = '') {
    const cleanId = normalizeRequestId(requestId)
    const response = await apiClient.patch(`/requests/${cleanId}/status`, {
      status,
      remarks,
    })
    return response.data?.data
  },

  /**
   * Securely stream and download request supporting document as a Blob.
   */
  async downloadAttachment(requestId, filename = 'supporting_document.pdf') {
    const cleanId = normalizeRequestId(requestId)
    try {
      const response = await apiClient.get(`/requests/${cleanId}/download`, {
        responseType: 'blob',
      })

      // Try extracting custom filename from Content-Disposition header
      let downloadFilename = filename
      const disposition = response.headers?.['content-disposition']
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        if (match && match[1]) {
          downloadFilename = match[1].replace(/['"]/g, '').trim()
        }
      }

      // Create Blob URL and trigger native browser download
      const blob = new Blob([response.data], {
        type: response.headers?.['content-type'] || 'application/octet-stream',
      })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.setAttribute('download', downloadFilename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(downloadUrl)

      return { success: true, filename: downloadFilename }
    } catch (error) {
      let errMsg = 'Failed to download attachment.'
      if (error.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text()
          const json = JSON.parse(text)
          errMsg = json.error || json.message || errMsg
        } catch {
          // If response body was not valid JSON, use fallback
        }
      } else if (error.response?.data?.error) {
        errMsg = error.response.data.error
      } else if (error.message) {
        errMsg = error.message
      }
      throw new Error(errMsg, { cause: error })
    }
  },

  /**
   * Resubmit petition with requested missing documents (Institution).
   */
  async resubmitRequest(requestId, { file, remarks }) {
    const cleanId = normalizeRequestId(requestId)
    if (file instanceof File) {
      const formData = new FormData()
      formData.append('file', file)
      if (remarks) formData.append('remarks', remarks)
      const response = await apiClient.post(`/requests/${cleanId}/resubmit`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return response.data?.data
    }
    const response = await apiClient.post(`/requests/${cleanId}/resubmit`, { remarks })
    return response.data?.data
  },

  /**
   * Assign or reassign petition to an officer (Admin).
   */
  async assignRequest(requestId, officerId) {
    const cleanId = normalizeRequestId(requestId)
    const response = await apiClient.patch(`/requests/${cleanId}/assign`, {
      officer_id: officerId,
    })
    return response.data?.data
  },

  /**
   * Self-assign / claim an unassigned petition (Officer / Admin).
   */
  async claimRequest(requestId) {
    const cleanId = normalizeRequestId(requestId)
    const response = await apiClient.patch(`/requests/${cleanId}/claim`)
    return response.data?.data
  },

  /**
   * Fetch aggregate petition statistics including overdue backlog.
   */
  async getRequestStats() {
    const response = await apiClient.get('/requests/stats')
    return response.data?.stats || {}
  },

  /**
   * Fetch detailed petition record and audit history.
   */
  async getRequestDetail(requestId) {
    const cleanId = normalizeRequestId(requestId)
    const response = await apiClient.get(`/requests/${cleanId}`)
    return response.data?.data
  },

  calculatePendingRequests: (requests = []) => {
    return requests.filter(
      (r) =>
        r.status?.toLowerCase() === 'under review' ||
        r.status?.toLowerCase() === 'submitted' ||
        r.status?.toLowerCase() === 'pending verification'
    ).length
  },

  /**
   * Submit renewed FDR receipt and details after petition approval (Institution).
   */
  async submitRenewalDetails(requestId, payload) {
    const cleanId = normalizeRequestId(requestId)
    if (payload instanceof FormData) {
      const response = await apiClient.post(`/requests/${cleanId}/submit-renewal`, payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return response.data?.data
    }

    if (payload.file instanceof File) {
      const formData = new FormData()
      formData.append('new_fdr_number', payload.newFdrNumber || payload.new_fdr_number)
      formData.append('new_issue_date', payload.newIssueDate || payload.new_issue_date)
      formData.append('new_maturity_date', payload.newMaturityDate || payload.new_maturity_date)
      formData.append('new_amount', payload.newAmount || payload.new_amount)
      if (payload.remarks) formData.append('remarks', payload.remarks)
      formData.append('file', payload.file)

      const response = await apiClient.post(`/requests/${cleanId}/submit-renewal`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return response.data?.data
    }

    const response = await apiClient.post(`/requests/${cleanId}/submit-renewal`, {
      new_fdr_number: payload.newFdrNumber || payload.new_fdr_number,
      new_issue_date: payload.newIssueDate || payload.new_issue_date,
      new_maturity_date: payload.newMaturityDate || payload.new_maturity_date,
      new_amount: payload.newAmount || payload.new_amount,
      remarks: payload.remarks || '',
    })
    return response.data?.data
  },

  /**
   * AICTE Officer/Admin verifies and endorses renewed FDR details.
   */
  async verifyRenewal(requestId, { decision, remarks, is_simulated = false }) {
    const cleanId = normalizeRequestId(requestId)
    const response = await apiClient.post(`/requests/${cleanId}/verify-renewal`, {
      decision,
      remarks,
      is_simulated,
    })
    return response.data
  },

  /**
   * Download a synthetic demo FDR renewal receipt for local testing.
   * Restricted to local development/demo environments.
   */
  async downloadSyntheticReceipt(fdrId, filename = null) {
    try {
      const response = await apiClient.get(`/fdr/${fdrId}/demo-renewal-receipt`, {
        responseType: 'blob',
      })
      let downloadFilename = filename || `DEMO_Renewal_Receipt_FDR_${fdrId}.pdf`
      const disposition = response.headers?.['content-disposition']
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        if (match && match[1]) {
          downloadFilename = match[1].replace(/['"]/g, '').trim()
        }
      }
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.setAttribute('download', downloadFilename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(downloadUrl)
      return { success: true, filename: downloadFilename }
    } catch (error) {
      let errMsg = 'Failed to download synthetic demo receipt.'
      if (error.response?.data instanceof Blob) {
        try {
          const text = await error.response.data.text()
          const json = JSON.parse(text)
          errMsg = json.error || json.message || errMsg
        } catch {}
      } else if (error.response?.data?.error) {
        errMsg = error.response.data.error
      } else if (error.message) {
        errMsg = error.message
      }
      throw new Error(errMsg, { cause: error })
    }
  },
}

export default requestService
