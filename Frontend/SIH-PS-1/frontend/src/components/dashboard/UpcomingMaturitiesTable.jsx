import React from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowRight, Eye, CalendarClock } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { formatCurrency } from '../../utils/formatters'
import { formatDate } from '../../utils/dateUtils'
import { useApp } from '../../context/AppContext'

export function UpcomingMaturitiesTable() {
  const { upcomingMaturities, requests } = useApp()

  const renderPetitionStatus = (fdr) => {
    const petition =
      fdr.latestRequest ||
      fdr.latest_request ||
      requests.find((r) => String(r.fdrId || r.fdr_id) === String(fdr.id))

    if (!petition) {
      return (
        <span className="text-2xs text-slate-400 italic">
          No petition submitted
        </span>
      )
    }

    const status = petition.status || 'Submitted'
    const hasReceipt = Boolean(
      petition.renewalSubmittedAt ||
      petition.renewal_submitted_at ||
      petition.renewalDocument ||
      petition.renewal_document
    )

    if (petition.requestType === 'Renewal' || petition.request_type === 'Renewal') {
      if (status === 'Submitted') {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            Renewal submitted
          </span>
        )
      }
      if (status === 'Under Review') {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
            Under review
          </span>
        )
      }
      if (status === 'Approved' && !hasReceipt) {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-amber-50 text-amber-900 border border-amber-300">
            Approved — upload receipt
          </span>
        )
      }
      if (status === 'Pending Verification' || (status === 'Approved' && hasReceipt)) {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-purple-50 text-purple-800 border border-purple-200">
            Awaiting verification
          </span>
        )
      }
      if (status === 'Closed') {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            Verified
          </span>
        )
      }
      if (status === 'Documents Required') {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-orange-50 text-orange-800 border border-orange-200">
            Deficiency notice
          </span>
        )
      }
      if (status === 'Rejected') {
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-rose-50 text-rose-800 border border-rose-200">
            Rejected
          </span>
        )
      }
    }

    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold bg-slate-100 text-slate-700">
        {petition.requestType || petition.request_type}: {status}
      </span>
    )
  }

  return (
    <Card className="flex flex-col h-full">
      <CardHeader
        title="Upcoming Maturities"
        subtitle="Fixed deposits maturing in the near term requiring renewal or release review"
        icon={CalendarClock}
        action={
          <Link
            to="/fdrs"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-navy-700 hover:text-navy-900 hover:underline"
          >
            <span>View All FDRs</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {upcomingMaturities.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
          <CalendarClock className="w-8 h-8 text-slate-400 mb-2" />
          <p className="text-xs sm:text-sm font-semibold text-slate-700">No upcoming maturities within 30 days.</p>
          <p className="text-2xs sm:text-xs text-slate-500 mt-0.5">All active security receipts remain fully compliant.</p>
        </div>
      ) : (
        <div className="overflow-x-auto -mx-4 sm:mx-0">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-2xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50/70">
                <th className="py-2.5 px-3 sm:px-4">FDR Ref #</th>
                <th className="py-2.5 px-3 sm:px-4">Bank Name</th>
                <th className="py-2.5 px-3 sm:px-4">Amount</th>
                <th className="py-2.5 px-3 sm:px-4">Maturity Date</th>
                <th className="py-2.5 px-3 sm:px-4">Status</th>
                <th className="py-2.5 px-3 sm:px-4">Petition</th>
                <th className="py-2.5 px-3 sm:px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {upcomingMaturities.map((fdr) => {
                const isUrgent = fdr.daysRemaining <= 15

                return (
                  <tr
                    key={fdr.id}
                    className={`hover:bg-slate-50/80 transition-colors ${
                      isUrgent ? 'bg-amber-50/30' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 sm:px-4 font-mono font-medium text-slate-900 text-xs">
                      {fdr.fdrNumber}
                    </td>
                    <td className="py-2.5 px-3 sm:px-4 text-slate-700 font-medium">
                      {fdr.bankName}
                    </td>
                    <td className="py-2.5 px-3 sm:px-4 font-bold text-slate-900 tabular-nums">
                      {formatCurrency(fdr.depositAmount)}
                    </td>
                    <td className="py-2.5 px-3 sm:px-4 text-slate-600 tabular-nums whitespace-nowrap">
                      {formatDate(fdr.maturityDate)}
                    </td>
                    <td className="py-2.5 px-3 sm:px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold ${
                          fdr.daysRemaining <= 10
                            ? 'bg-rose-100 text-rose-800 border border-rose-200'
                            : fdr.daysRemaining <= 30
                            ? 'bg-amber-100 text-amber-900 border border-amber-300'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }`}
                      >
                        {fdr.daysRemaining <= 15 && (
                          <AlertCircle className="w-3 h-3 text-amber-700 shrink-0" />
                        )}
                        {fdr.daysRemaining} days left
                      </span>
                    </td>
                    <td className="py-2.5 px-3 sm:px-4 whitespace-nowrap">
                      {renderPetitionStatus(fdr)}
                    </td>
                    <td className="py-2.5 px-3 sm:px-4 text-right whitespace-nowrap">
                      <Link
                        to={`/fdrs/${fdr.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-2xs font-medium text-navy-700 hover:bg-navy-50 rounded border border-slate-200 transition-colors"
                      >
                        <Eye className="w-3 h-3" />
                        <span>View</span>
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

export default UpcomingMaturitiesTable
