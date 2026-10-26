import React from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowRight, Eye, CalendarClock } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { FDRStatusBadge } from '../fdr/FDRStatusBadge'
import { formatCurrency } from '../../utils/formatters'
import { formatDate } from '../../utils/dateUtils'
import { useApp } from '../../context/AppContext'

export function UpcomingMaturitiesTable() {
  const { upcomingMaturities } = useApp()

  return (
    <Card className="flex flex-col h-full">
      <CardHeader
        title="Upcoming Maturities"
        subtitle="Fixed deposits maturing in the near future requiring renewal or release review"
        action={
          <Link
            to="/fdrs"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#142B4A] hover:text-[#0E1E34] hover:underline"
          >
            <span>View All FDRs</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {upcomingMaturities.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
          <CalendarClock className="w-8 h-8 text-slate-400 mb-2" />
          <p className="text-sm font-medium">No upcoming maturities within the next 30 days.</p>
          <p className="text-xs text-slate-400 mt-1">All active FDRs are in compliance.</p>
        </div>
      ) : (
        <div className="overflow-x-auto -mx-5 sm:mx-0">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider bg-slate-50/70">
                <th className="py-2.5 px-4">FDR Ref #</th>
                <th className="py-2.5 px-4">Bank Name</th>
                <th className="py-2.5 px-4">Amount</th>
                <th className="py-2.5 px-4">Maturity Date</th>
                <th className="py-2.5 px-4">Days Left</th>
                <th className="py-2.5 px-4">Status</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {upcomingMaturities.map((fdr) => {
                const isUrgent = fdr.daysRemaining <= 15

                return (
                  <tr
                    key={fdr.id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      isUrgent ? 'bg-amber-50/40' : ''
                    }`}
                  >
                    <td className="py-3 px-4 font-mono font-medium text-slate-900 text-xs">
                      {fdr.fdrNumber}
                    </td>
                    <td className="py-3 px-4 text-slate-700 text-xs font-medium">
                      {fdr.bankName}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900 text-xs">
                      {formatCurrency(fdr.depositAmount)}
                    </td>
                    <td className="py-3 px-4 text-slate-600 text-xs whitespace-nowrap">
                      {formatDate(fdr.maturityDate)}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                          fdr.daysRemaining <= 10
                            ? 'bg-rose-100 text-rose-800 border border-rose-200'
                            : fdr.daysRemaining <= 30
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }`}
                      >
                        {fdr.daysRemaining <= 15 && (
                          <AlertCircle className="w-3 h-3 text-amber-600" />
                        )}
                        {fdr.daysRemaining} days
                      </span>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <FDRStatusBadge status={fdr.status} size="sm" />
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <Link
                        to={`/fdrs/${fdr.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-[#142B4A] hover:bg-[#142B4A]/10 rounded-md transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Details</span>
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
