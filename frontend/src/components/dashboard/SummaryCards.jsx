import React from 'react'
import { FileText, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { Card } from '../ui/Card'
import { useApp } from '../../context/AppContext'

export function SummaryCards() {
  const { stats } = useApp()

  const cardItems = [
    {
      title: 'Total FDRs',
      value: stats.totalFdrs,
      description: 'Registered security receipts',
      icon: FileText,
      iconBg: 'bg-[#142B4A]/10 text-[#142B4A]',
      badge: 'All Years',
      badgeColor: 'bg-slate-100 text-slate-700',
    },
    {
      title: 'Active FDRs',
      value: stats.activeFdrs,
      description: 'Valid joint security deposits',
      icon: CheckCircle2,
      iconBg: 'bg-emerald-50 text-emerald-700',
      badge: 'In Good Standing',
      badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    },
    {
      title: 'Maturing Soon',
      value: stats.maturingSoon,
      description: 'Due in the next 30 days',
      icon: AlertCircle,
      iconBg: 'bg-amber-50 text-amber-700',
      badge: 'Action Required',
      badgeColor: stats.maturingSoon > 0 ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-slate-100 text-slate-600',
    },
    {
      title: 'Pending Requests',
      value: stats.pendingRequests,
      description: 'Renewal & release scrutiny',
      icon: Clock,
      iconBg: 'bg-blue-50 text-blue-700',
      badge: 'Under Review',
      badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
      {cardItems.map((item, index) => {
        const Icon = item.icon
        return (
          <Card key={index} className="relative overflow-hidden p-5 flex flex-col justify-between">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  {item.title}
                </p>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-bold text-slate-900 tracking-tight">
                    {item.value}
                  </span>
                </div>
              </div>
              <div className={`p-3 rounded-xl ${item.iconBg} shrink-0`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-slate-600 font-medium">{item.description}</span>
              <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${item.badgeColor}`}>
                {item.badge}
              </span>
            </div>
          </Card>
        )
      })}
    </div>
  )
}
