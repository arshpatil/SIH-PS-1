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

  /**
   * Fetch bureau officer workload, overdue cases, and escalation queues.
   */
  async getWorkload() {
    const response = await apiClient.get('/dashboard/workload')
    return response.data?.data || response.data
  },

  /**
   * Fetch dedicated Admin Dashboard system-wide metrics, unassigned queue, and workloads.
   */
  async getAdminDashboard() {
    const response = await apiClient.get('/dashboard/admin')
    return response.data?.data || response.data
  },

  /**
   * Fetch dedicated Officer Dashboard personal workload and assigned cases.
   */
  async getOfficerDashboard() {
    const response = await apiClient.get('/dashboard/officer')
    return response.data?.data || response.data
  },

  /**
   * Fetch all officers for administrative oversight and assignment.
   */
  async getAdminOfficers() {
    const response = await apiClient.get('/dashboard/officers')
    return response.data?.data || response.data
  },

  /**
   * Activate or deactivate an officer account (Admin only).
   */
  async updateOfficerStatus(officerId, isActive) {
    const response = await apiClient.patch(`/dashboard/officers/${officerId}/status`, {
      is_active: isActive,
    })
    return response.data?.data || response.data
  },

  /**
   * Trigger the automated watchdog scanner for critical and overdue petitions.
   */
  async scanAlerts() {
    const response = await apiClient.post('/dashboard/scan-alerts')
    return response.data
  },
}

export default dashboardService
