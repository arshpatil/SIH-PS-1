import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell,
  CheckCheck,
  Check,
  AlertTriangle,
  Info,
  Clock,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { formatDate } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'

export function NotificationsPage() {
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useApp()
  const [filterTab, setFilterTab] = useState('ALL') // 'ALL', 'UNREAD', 'URGENCY', 'VERIFICATION'

  const filteredNotifications = useMemo(() => {
    return notifications.filter((notif) => {
      if (filterTab === 'UNREAD') return !notif.isRead
      if (filterTab === 'URGENCY') return notif.category === 'urgency' || notif.category === 'warning'
      if (filterTab === 'VERIFICATION') return notif.type === 'Verification' || notif.type === 'Request Update'
      return true
    })
  }, [notifications, filterTab])

  const getIcon = (type, category) => {
    if (category === 'urgency') return <AlertTriangle className="w-5 h-5 text-amber-600" />
    if (category === 'warning') return <ShieldAlert className="w-5 h-5 text-rose-600" />
    if (type === 'Verification') return <Clock className="w-5 h-5 text-blue-600" />
    return <Info className="w-5 h-5 text-slate-600" />
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Institutional Notifications & Alerts
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Official system notifications regarding upcoming maturities, verification statuses, and action items.
          </p>
        </div>

        {unreadCount > 0 && (
          <Button
            variant="secondary"
            size="sm"
            icon={CheckCheck}
            onClick={markAllAsRead}
          >
            Mark All as Read
          </Button>
        )}
      </div>

      {/* Tabs Filter */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2 overflow-x-auto text-xs sm:text-sm">
        <button
          onClick={() => setFilterTab('ALL')}
          className={`px-3.5 py-1.5 rounded-lg font-medium transition-colors shrink-0 ${
            filterTab === 'ALL'
              ? 'bg-[#142B4A] text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          All Notifications ({notifications.length})
        </button>

        <button
          onClick={() => setFilterTab('UNREAD')}
          className={`px-3.5 py-1.5 rounded-lg font-medium transition-colors shrink-0 flex items-center gap-1.5 ${
            filterTab === 'UNREAD'
              ? 'bg-[#142B4A] text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <span>Unread</span>
          {unreadCount > 0 && (
            <span
              className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                filterTab === 'UNREAD' ? 'bg-amber-400 text-slate-950' : 'bg-rose-600 text-white'
              }`}
            >
              {unreadCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setFilterTab('URGENCY')}
          className={`px-3.5 py-1.5 rounded-lg font-medium transition-colors shrink-0 ${
            filterTab === 'URGENCY'
              ? 'bg-[#142B4A] text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Maturities & Action Alerts
        </button>

        <button
          onClick={() => setFilterTab('VERIFICATION')}
          className={`px-3.5 py-1.5 rounded-lg font-medium transition-colors shrink-0 ${
            filterTab === 'VERIFICATION'
              ? 'bg-[#142B4A] text-white shadow-2xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Verification & Requests
        </button>
      </div>

      {/* Notifications List */}
      <div className="space-y-3">
        {filteredNotifications.length === 0 ? (
          <EmptyState
            icon={Bell}
            title={
              filterTab === 'UNREAD'
                ? 'No unread notifications'
                : 'No notifications in this category'
            }
            description="All notifications in this view have been processed or read."
            actionLabel={filterTab !== 'ALL' ? 'Show All Notifications' : undefined}
            onAction={() => setFilterTab('ALL')}
          />
        ) : (
          filteredNotifications.map((notif) => {
            const isUrgent = notif.category === 'urgency' || notif.category === 'warning'

            return (
              <Card
                key={notif.id}
                className={`p-4 sm:p-5 transition-all ${
                  notif.isRead
                    ? 'bg-white opacity-85 hover:opacity-100'
                    : isUrgent
                    ? 'bg-amber-50/50 border-amber-300/80 shadow-xs ring-1 ring-amber-200/50'
                    : 'bg-blue-50/30 border-blue-200/80 shadow-xs'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div
                      className={`p-2.5 rounded-xl shrink-0 mt-0.5 ${
                        isUrgent
                          ? 'bg-amber-100 text-amber-700'
                          : notif.type === 'Verification'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {getIcon(notif.type, notif.category)}
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-slate-900">
                          {notif.title}
                        </h4>
                        {!notif.isRead && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-slate-950 uppercase tracking-wider">
                            New
                          </span>
                        )}
                      </div>

                      <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                        {notif.message}
                      </p>

                      <div className="flex flex-wrap items-center gap-3 pt-2 text-xs">
                        <span className="text-slate-400 font-mono text-[11px]">
                          {formatDate(notif.timestamp)}
                        </span>

                        {notif.link && (
                          <Link
                            to={notif.link}
                            className="inline-flex items-center gap-1 font-semibold text-[#142B4A] hover:underline"
                          >
                            <span>{notif.linkText || 'View Details'}</span>
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>

                  {!notif.isRead && (
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Check}
                      onClick={() => markAsRead(notif.id)}
                      className="text-slate-400 hover:text-emerald-700 hover:bg-emerald-50 shrink-0"
                    >
                      <span className="hidden sm:inline">Mark as Read</span>
                    </Button>
                  )}
                </div>
              </Card>
            )
          })
        )}
      </div>
    </div>
  )
}
