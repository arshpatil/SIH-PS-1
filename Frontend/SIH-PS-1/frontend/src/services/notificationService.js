import apiClient from '../api/client'
import { initialNotifications } from '../data/mock/mockNotifications'

export function normalizeNotification(n) {
  if (!n) return n
  const notifType = n.notification_type || n.type || 'General'
  const isUrgent = notifType === 'MATURITY_REMINDER' || String(n.title).toLowerCase().includes('matur')

  return {
    ...n,
    id: n.id,
    title: n.title,
    message: n.message,
    isRead: n.is_read !== undefined ? n.is_read : (n.isRead ?? false),
    is_read: n.is_read !== undefined ? n.is_read : (n.isRead ?? false),
    timestamp: n.created_at || n.timestamp || new Date().toISOString(),
    type: notifType === 'MATURITY_REMINDER' ? 'Maturity Alert' : (n.type || notifType),
    category: isUrgent ? 'urgency' : (n.category || 'info'),
  }
}

export const notificationService = {
  getInitialNotifications: () => {
    return initialNotifications.map(normalizeNotification)
  },

  getUnreadCount: (notifications) => {
    if (!notifications || !Array.isArray(notifications)) return 0
    return notifications.filter((n) => !(n.is_read || n.isRead)).length
  },

  /**
   * Fetch paginated notifications from backend.
   */
  async listNotifications(params = {}) {
    const response = await apiClient.get('/notifications', { params })
    const items = response.data?.notifications || []
    return {
      notifications: items.map(normalizeNotification),
      pagination: response.data?.pagination,
    }
  },

  /**
   * Fetch unread badge count from backend.
   */
  async fetchUnreadCount() {
    const response = await apiClient.get('/notifications/unread-count')
    return response.data?.unread_count ?? 0
  },

  /**
   * Mark single notification as read.
   */
  async markAsRead(id) {
    const response = await apiClient.patch(`/notifications/${id}/read`)
    return response.data
  },

  /**
   * Mark all user notifications as read.
   */
  async markAllAsRead() {
    const response = await apiClient.patch('/notifications/read-all')
    return response.data
  },
}

export default notificationService
