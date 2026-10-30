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
    if (category === 'urgency') return <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
    if (category === 'warning') return <AlertTriangle className="w-3.5 h-3.5 text-rose-700" />
    if (type === 'Verification') return <Clock className="w-3.5 h-3.5 text-blue-700" />
    return <Info className="w-3.5 h-3.5 text-navy-700" />
  }

  return (
    <Card className="flex flex-col h-full">
      <CardHeader
        title="Official Notices & Alerts"
        subtitle={
          unreadCount > 0
            ? `${unreadCount} unread notices requiring scrutiny`
            : 'All notices are acknowledged'
        }
        icon={Bell}
        action={
          <Link
            to="/notifications"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-navy-700 hover:text-navy-900 hover:underline"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {recentNotifications.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
          <Bell className="w-7 h-7 text-slate-300 mb-2" />
          <p className="text-xs font-medium">No alerts at this moment.</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {recentNotifications.map((notif) => (
            <div
              key={notif.id}
              className={`p-2.5 sm:p-3 rounded-lg border transition-all text-xs flex items-start justify-between gap-2.5 ${
                notif.isRead
                  ? 'bg-white border-slate-200'
                  : 'bg-amber-50/40 border-amber-200 shadow-2xs'
              }`}
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <div
                  className={`p-1.5 rounded-md shrink-0 mt-0.5 ${
                    notif.category === 'urgency'
                      ? 'bg-amber-100 text-amber-800'
                      : notif.category === 'warning'
                      ? 'bg-rose-100 text-rose-800'
                      : 'bg-slate-100 text-slate-700'
                  }`}
                >
                  {getNotificationIcon(notif.type, notif.category)}
                </div>

                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-900 truncate">{notif.title}</span>
                    {!notif.isRead && (
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                    )}
                  </div>
                  <p className="text-slate-600 text-2xs mt-0.5 leading-relaxed line-clamp-2">{notif.message}</p>
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500">
                    <span>{formatDate(notif.timestamp)}</span>
                    {notif.link && (
                      <Link
                        to={notif.link}
                        className="font-semibold text-navy-700 hover:underline"
                      >
                        {notif.linkText || 'Details'}
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

export default NotificationsPreview
