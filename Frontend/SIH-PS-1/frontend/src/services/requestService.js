import apiClient from '../api/client'
import { initialRequests } from '../data/mock/mockRequests'

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
    const response = await apiClient.patch(`/requests/${requestId}/status`, {
      status,
      remarks,
    })
    return response.data?.data
  },

  /**
   * Securely stream and download request supporting document as a Blob.
   */
  async downloadAttachment(requestId, filename = 'supporting_document.pdf') {
    try {
      const response = await apiClient.get(`/requests/${requestId}/download`, {
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
      throw new Error(errMsg)
    }
  },

  calculatePendingRequests: (requests = []) => {
    return requests.filter(
      (r) =>
        r.status?.toLowerCase() === 'under review' ||
        r.status?.toLowerCase() === 'submitted'
    ).length
  },
}

export default requestService
