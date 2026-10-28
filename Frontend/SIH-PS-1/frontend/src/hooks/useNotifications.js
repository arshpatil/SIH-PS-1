import { useApp } from '../context/AppContext'

export function useNotifications() {
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useApp()

  return {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
  }
}
