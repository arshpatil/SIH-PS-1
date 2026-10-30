import apiClient from '../api/client'

export const bankService = {
  /**
   * Retrieve active bank integration provider info, demo mode flag, and disclaimers.
   */
  getBankStatus: async () => {
    const res = await apiClient.get('/bank/status')
    return res.data?.data || {}
  },

  /**
   * Request a bank verification check for an FDR record.
   * In DEMO mode, supports specifying simulation_scenario ('MATCHED', 'MISMATCH', 'NOT_FOUND', 'UNAVAILABLE').
   */
  verifyFDR: async (fdrId, scenario = null) => {
    const payload = scenario ? { scenario } : {}
    const res = await apiClient.post(`/bank/verify-fdr/${fdrId}`, payload)
    return res.data
  },

  /**
   * Retrieve previous bank verification queries for an FDR record.
   */
  getVerificationHistory: async (fdrId) => {
    const res = await apiClient.get(`/bank/history/${fdrId}`)
    return res.data?.data || []
  },

  /**
   * Check renewal status against the bank provider for a pending renewal petition.
   */
  checkRenewalStatus: async (requestId, bankReference = null) => {
    const payload = bankReference ? { bank_reference: bankReference } : {}
    const res = await apiClient.post(`/bank/check-renewal/${requestId}`, payload)
    return res.data
  },
}
