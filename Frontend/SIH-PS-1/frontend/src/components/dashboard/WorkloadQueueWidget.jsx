import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Users,
  Clock,
  CheckCircle2,
  FileText,
  ArrowRight,
  ShieldAlert,
  Loader2,
  Inbox,
} from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { Button } from '../ui/Button'
import { dashboardService } from '../../services/dashboardService'
import { formatDate } from '../../utils/dateUtils'

export function WorkloadQueueWidget() {
  const [workload, setWorkload] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let isMounted = true
    async function fetchWorkload() {
      try {
        const data = await dashboardService.getWorkload()
        if (isMounted && data) {
          setWorkload(data)
        }
      } catch (err) {
        console.error('Failed to load workload data:', err)
      } finally {
        if (isMounted) setLoading(false)
      }
    }
    fetchWorkload()
    return () => {
      isMounted = false
    }
  }, [])

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center py-6 gap-2 text-slate-500 text-xs">
          <Loader2 className="w-4 h-4 animate-spin text-[#142B4A]" />
          <span>Loading Bureau Workload & Escalation Queue...</span>
        </div>
      </Card>
    )
  }

  if (!workload) return null

  const {
    pending_petitions = 0,
    overdue_petitions_count = 0,
    pending_fdrs_scrutiny = 0,
    overdue_petitions = [],
    officers_workload = [],
  } = workload

  return (
    <Card className="p-5 border-slate-200">
      <CardHeader
        title="Bureau Workload & Escalation Queue"
        subtitle="Operational metrics for AICTE scrutiny officers and regulatory petition backlogs"
        action={
          <Link to="/requests">
            <Button variant="secondary" size="sm" icon={ArrowRight}>
              All Petitions
            </Button>
          </Link>
        }
      />

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mt-4">
        <div className="p-3.5 rounded-xl bg-blue-50/60 border border-blue-200 flex items-center justify-between">
          <div>
            <span className="text-2xs font-semibold text-blue-800 uppercase tracking-wider block">
              Pending FDR Scrutiny
            </span>
            <span className="text-2xl font-bold text-blue-950 mt-1 block">
              {pending_fdrs_scrutiny}
            </span>
            <span className="text-2xs text-blue-700">Awaiting officer verification</span>
          </div>
          <Inbox className="w-8 h-8 text-blue-500/40" />
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
          <div>
            <span className="text-2xs font-semibold text-slate-600 uppercase tracking-wider block">
              Active Petitions Queue
            </span>
            <span className="text-2xl font-bold text-slate-900 mt-1 block">
              {pending_petitions}
            </span>
            <span className="text-2xs text-slate-500">Under renewal / release desk review</span>
          </div>
          <FileText className="w-8 h-8 text-slate-400/40" />
        </div>

        <div className={`p-3.5 rounded-xl border flex items-center justify-between ${
          overdue_petitions_count > 0
            ? 'bg-rose-50 border-rose-300 text-rose-950'
            : 'bg-emerald-50 border-emerald-200 text-emerald-950'
        }`}>
          <div>
            <span className="text-2xs font-semibold uppercase tracking-wider block">
              Overdue Cases (&gt;14 Days)
            </span>
            <span className="text-2xl font-bold mt-1 block">
              {overdue_petitions_count}
            </span>
            <span className="text-2xs">
              {overdue_petitions_count > 0 ? 'Requires priority clearance' : 'No SLA breaches'}
            </span>
          </div>
          {overdue_petitions_count > 0 ? (
            <ShieldAlert className="w-8 h-8 text-rose-500/60 animate-pulse" />
          ) : (
            <CheckCircle2 className="w-8 h-8 text-emerald-500/40" />
          )}
        </div>
      </div>

      {/* Two sub-sections: Overdue Petitions Queue & Officer Caseload */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-5 pt-4 border-t border-slate-100 text-xs">
        {/* Overdue Petitions List */}
        <div>
          <div className="flex items-center gap-2 mb-2 font-bold text-slate-800">
            <Clock className="w-4 h-4 text-amber-600" />
            <span>Overdue Petitions Requiring Action</span>
          </div>
          {overdue_petitions.length === 0 ? (
            <p className="text-slate-400 italic py-3 text-center bg-slate-50 rounded-lg">
              No overdue statutory petitions currently pending review.
            </p>
          ) : (
            <div className="space-y-2">
              {overdue_petitions.slice(0, 4).map((op) => (
                <div
                  key={op.id}
                  className="p-2.5 rounded-lg border border-amber-200 bg-amber-50/40 flex items-center justify-between"
                >
                  <div>
                    <span className="font-mono font-bold text-slate-900">{op.id}</span>
                    <span className="text-2xs text-slate-500 ml-2">
                      FDR: {op.fdrNumber || op.fdr_number} ({op.requestType || op.request_type})
                    </span>
                    <div className="text-2xs text-amber-800 mt-0.5">
                      Submitted on {formatDate(op.submissionDate || op.created_at)}
                    </div>
                  </div>
                  <Link to="/requests">
                    <Button variant="secondary" size="xs">
                      Scrutinize
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Officer Caseload Distribution */}
        <div>
          <div className="flex items-center gap-2 mb-2 font-bold text-slate-800">
            <Users className="w-4 h-4 text-[#142B4A]" />
            <span>Officer Caseload Distribution</span>
          </div>
          {officers_workload.length === 0 ? (
            <p className="text-slate-400 italic py-3 text-center bg-slate-50 rounded-lg">
              No officer assignment metrics available.
            </p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <table className="w-full text-left">
                <thead className="bg-slate-50 text-2xs uppercase text-slate-500 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2 px-3">Officer</th>
                    <th className="py-2 px-3 text-center">Active Cases</th>
                    <th className="py-2 px-3 text-right">Resolved</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-2xs">
                  {officers_workload.map((off) => (
                    <tr key={off.officer_id} className="hover:bg-slate-50">
                      <td className="py-2 px-3">
                        <span className="font-semibold text-slate-800 block">
                          {off.officer_name || `Officer #${off.officer_id}`}
                        </span>
                        <span className="text-slate-400 text-[10px]">{off.officer_email}</span>
                      </td>
                      <td className="py-2 px-3 text-center font-bold text-slate-900">
                        {off.active_assigned_cases}
                      </td>
                      <td className="py-2 px-3 text-right font-medium text-emerald-700">
                        {off.resolved_cases}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

export default WorkloadQueueWidget
