import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Search, Filter, Eye, ArrowUpDown, ArrowRight, FileText } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { FDRStatusBadge } from '../fdr/FDRStatusBadge'
import { formatCurrency } from '../../utils/formatters'
import { formatDate } from '../../utils/dateUtils'
import { FDR_STATUS_LIST } from '../../constants/statusConstants'
import { useApp } from '../../context/AppContext'

export function RecentFDRsTable() {
  const { fdrs } = useApp()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [sortOrder, setSortOrder] = useState('desc') // desc = latest first

  // Filter and sort without mutating original
  const filteredFDRs = useMemo(() => {
    return fdrs
      .filter((fdr) => {
        const matchesSearch =
          fdr.fdrNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
          fdr.bankName.toLowerCase().includes(searchQuery.toLowerCase())

        const matchesStatus =
          statusFilter === 'ALL' || fdr.status === statusFilter

        return matchesSearch && matchesStatus
      })
      .sort((a, b) => {
        const dateA = new Date(a.issueDate).getTime()
        const dateB = new Date(b.issueDate).getTime()
        return sortOrder === 'desc' ? dateB - dateA : dateA - dateB
      })
  }, [fdrs, searchQuery, statusFilter, sortOrder])

  // Show top 6 in recent table
  const displayedFDRs = filteredFDRs.slice(0, 6)

  return (
    <Card className="flex flex-col">
      <CardHeader
        title="Recent FDR Records"
        subtitle="Institutions official security deposits submitted and registered with AICTE"
        icon={FileText}
        action={
          <Link
            to="/fdrs"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-navy-700 hover:text-navy-900 hover:underline"
          >
            <span>View All ({fdrs.length})</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 mb-3.5">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by FDR number or bank name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8.5 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20 focus:border-[#142B4A] bg-white text-slate-900"
          />
        </div>

        {/* Status Dropdown Filter */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="pl-7 pr-7 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="ALL">All Statuses</option>
              {FDR_STATUS_LIST.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
            <Filter className="w-3 h-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Sort Toggle */}
          <button
            type="button"
            onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
            className="p-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-600 transition-colors"
            title={`Sort by issue date (${sortOrder === 'desc' ? 'newest first' : 'oldest first'})`}
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Table */}
      {displayedFDRs.length === 0 ? (
        <div className="p-8 text-center text-slate-500 border border-dashed border-slate-200 rounded-lg">
          <p className="text-xs sm:text-sm font-semibold text-slate-700">No records match your criteria.</p>
          <button
            onClick={() => {
              setSearchQuery('')
              setStatusFilter('ALL')
            }}
            className="mt-2 text-2xs font-semibold text-navy-700 hover:underline"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto -mx-4 sm:mx-0">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-2xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50/70">
                <th className="py-2.5 px-3 sm:px-4">FDR Ref Number</th>
                <th className="py-2.5 px-3 sm:px-4">Bank Name</th>
                <th className="py-2.5 px-3 sm:px-4">Deposit Amount</th>
                <th className="py-2.5 px-3 sm:px-4">Issue Date</th>
                <th className="py-2.5 px-3 sm:px-4">Maturity Date</th>
                <th className="py-2.5 px-3 sm:px-4">Status</th>
                <th className="py-2.5 px-3 sm:px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {displayedFDRs.map((fdr) => (
                <tr key={fdr.id} className="hover:bg-slate-50/80 transition-colors">
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
                    {formatDate(fdr.issueDate)}
                  </td>
                  <td className="py-2.5 px-3 sm:px-4 text-slate-600 tabular-nums whitespace-nowrap">
                    {formatDate(fdr.maturityDate)}
                  </td>
                  <td className="py-2.5 px-3 sm:px-4 whitespace-nowrap">
                    <FDRStatusBadge status={fdr.status} size="sm" />
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export default RecentFDRsTable
