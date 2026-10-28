import apiClient from '../api/client'

export const dashboardService = {
  /**
   * Fetch aggregate statistics for summary cards & metrics.
   */
  async getStats(institutionId = null) {
    const params = {}
    if (institutionId) {
      params.institution_id = institutionId
    }
    const response = await apiClient.get('/dashboard/stats', { params })
    return response.data?.data || response.data
  },

  /**
   * Fetch formatted distribution and time-series data for Recharts components.
   */
  async getCharts(institutionId = null) {
    const params = {}
    if (institutionId) {
      params.institution_id = institutionId
    }
    const response = await apiClient.get('/dashboard/charts', { params })
    return response.data?.data || response.data
  },
}

export default dashboardService
