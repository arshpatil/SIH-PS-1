import React from 'react'
import { FileText, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { Card } from '../ui/Card'
import { useApp } from '../../context/AppContext'

export function SummaryCards() {
  const { stats } = useApp()

  const cardItems = [
    {
      title: 'Total Registered FDRs',
      value: stats.totalFdrs,
      description: 'Security deposit receipts on record',
      icon: FileText,
      iconBg: 'bg-navy-50 text-navy-700 border border-navy-200/60',
      badge: 'All Terms',
      badgeColor: 'bg-slate-100 text-slate-700 border-slate-200',
    },
    {
      title: 'Active / Verified FDRs',
      value: stats.activeFdrs,
      description: 'Valid joint security deposits',
      icon: CheckCircle2,
      iconBg: 'bg-emerald-50 text-emerald-700 border border-emerald-200/60',
      badge: 'In Good Standing',
      badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    },
    {
      title: 'Approaching Maturity',
      value: stats.maturingSoon,
      description: 'Maturing within next 30 days',
      icon: AlertCircle,
      iconBg: 'bg-amber-50 text-amber-700 border border-amber-200/60',
      badge: stats.maturingSoon > 0 ? 'Action Due' : 'Up to Date',
      badgeColor: stats.maturingSoon > 0 ? 'bg-amber-100 text-amber-900 border-amber-300' : 'bg-slate-100 text-slate-600 border-slate-200',
    },
    {
      title: 'Pending Petitions',
      value: stats.pendingRequests,
      description: 'Renewal & release scrutiny cases',
      icon: Clock,
      iconBg: 'bg-blue-50 text-blue-700 border border-blue-200/60',
      badge: 'Under Review',
      badgeColor: 'bg-blue-50 text-blue-800 border-blue-200',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4.5">
      {cardItems.map((item, index) => {
        const Icon = item.icon
        return (
          <Card key={index} className="relative overflow-hidden p-4 sm:p-5 flex flex-col justify-between hover:border-slate-300 hover:shadow-subtle transition-all">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  {item.title}
                </p>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight tabular-nums">
                    {item.value}
                  </span>
                </div>
              </div>
              <div className={`p-2.5 rounded-lg ${item.iconBg} shrink-0`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-2xs sm:text-xs">
              <span className="text-slate-500 truncate mr-2">{item.description}</span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border shrink-0 ${item.badgeColor}`}>
                {item.badge}
              </span>
            </div>
          </Card>
        )
      })}
    </div>
  )
}

export default SummaryCards
