import React from 'react'
import { Link } from 'react-router-dom'
import { Bell, ArrowRight, Check, AlertTriangle, Info, Clock } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { formatDate } from '../../utils/dateUtils'
import { useApp } from '../../context/AppContext'

export function NotificationsPreview() {
  const { notifications, unreadCount, markAsRead } = useApp()

  // Display the top 4 notifications
  const recentNotifications = notifications.slice(0, 4)

  const getNotificationIcon = (type, category) => {
    if (category === 'urgency') return <AlertTriangle className="w-4 h-4 text-amber-600" />
    if (category === 'warning') return <AlertTriangle className="w-4 h-4 text-rose-600" />
    if (type === 'Verification') return <Clock className="w-4 h-4 text-blue-600" />
    return <Info className="w-4 h-4 text-slate-600" />
  }

  return (
    <Card className="flex flex-col h-full">
      <CardHeader
        title="Notifications & Alerts"
        subtitle={
          unreadCount > 0
            ? `${unreadCount} unread notification(s) requiring your attention`
            : 'All current notifications are marked as read'
        }
        action={
          <Link
            to="/notifications"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#142B4A] hover:text-[#0E1E34] hover:underline"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {recentNotifications.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
          <Bell className="w-8 h-8 text-slate-300 mb-2" />
          <p className="text-xs font-medium">No alerts at this moment.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {recentNotifications.map((notif) => (
            <div
              key={notif.id}
              className={`p-3 rounded-xl border transition-all text-xs flex items-start justify-between gap-3 ${
                notif.isRead
                  ? 'bg-white border-slate-200/80'
                  : 'bg-amber-50/40 border-amber-200/80 shadow-2xs'
              }`}
            >
              <div className="flex items-start gap-2.5">
                <div
                  className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                    notif.category === 'urgency'
                      ? 'bg-amber-100'
                      : notif.category === 'warning'
                      ? 'bg-rose-100'
                      : 'bg-slate-100'
                  }`}
                >
                  {getNotificationIcon(notif.type, notif.category)}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{notif.title}</span>
                    {!notif.isRead && (
                      <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                    )}
                  </div>
                  <p className="text-slate-600 mt-1 leading-relaxed">{notif.message}</p>
                  <div className="flex items-center gap-3 mt-2 text-2xs text-slate-600">
                    <span>{formatDate(notif.timestamp)}</span>
                    {notif.link && (
                      <Link
                        to={notif.link}
                        className="font-medium text-[#142B4A] hover:underline"
                      >
                        {notif.linkText || 'View Details'}
                      </Link>
                    )}
                  </div>
                </div>
              </div>

              {!notif.isRead && (
                <button
                  type="button"
                  onClick={() => markAsRead(notif.id)}
                  className="p-1 rounded text-slate-400 hover:text-emerald-700 hover:bg-slate-100 transition-colors shrink-0"
                  title="Mark as read"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
