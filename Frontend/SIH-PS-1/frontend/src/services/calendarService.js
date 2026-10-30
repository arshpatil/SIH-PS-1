import apiClient from '../api/client'

export const calendarService = {
  /**
   * Fetch calendar events from the authoritative backend endpoint.
   * Supports: start, end, event_type, status, priority, institution_id
   */
  async getEvents(params = {}) {
    const response = await apiClient.get('/calendar/events', { params })
    return response.data?.events || []
  },
}

export default calendarService
