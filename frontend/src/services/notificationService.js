import { initialNotifications } from '../data/mock/mockNotifications'

export const notificationService = {
  getInitialNotifications: () => {
    return [...initialNotifications]
  },

  getUnreadCount: (notifications) => {
    return notifications.filter(n => !n.isRead).length
  },
}
