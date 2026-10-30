import apiClient from '../api/client'

export const reportService = {
  /**
   * Fetch paginated FDR report with criteria filters & aggregate valuation.
   */
  async getReport(params = {}) {
    const response = await apiClient.get('/reports/fdr', { params })
    return response.data
  },

  /**
   * Download filtered FDR records as CSV attachment.
   */
  async downloadReportCSV(params = {}) {
    const response = await apiClient.get('/reports/fdr/export', {
      params,
      responseType: 'blob',
    })

    let filename = 'aicte_fdr_report.csv'
    const disposition = response.headers['content-disposition']
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match && match[1]) {
        filename = match[1]
      }
    }

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
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
   * Download filtered statutory petitions as CSV attachment.
   */
  async downloadPetitionsCSV(params = {}) {
    const response = await apiClient.get('/reports/petitions/export', {
      params,
      responseType: 'blob',
    })

    let filename = 'aicte_petitions_report.csv'
    const disposition = response.headers['content-disposition']
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match && match[1]) {
        filename = match[1]
      }
    }

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
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
   * Fetch audit history events.
   */
  async getAuditLogs(params = {}) {
    const response = await apiClient.get('/reports/audit', { params })
    return response.data
  },
}

export default reportService
