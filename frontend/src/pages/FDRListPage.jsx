import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Search,
  Filter,
  PlusCircle,
  Eye,
  ArrowUpDown,
  Download,
  Calendar,
  AlertCircle,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { FDRStatusBadge } from '../components/fdr/FDRStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { formatCurrency } from '../utils/formatters'
import { formatDate, getDaysRemaining } from '../utils/dateUtils'
import { FDR_STATUS_LIST } from '../constants/statusConstants'
import { useApp } from '../context/AppContext'

export function FDRListPage() {
  const { fdrs } = useApp()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [maturityFilter, setMaturityFilter] = useState('ALL')
  const [sortBy, setSortBy] = useState('issueDate')
  const [sortDirection, setSortDirection] = useState('desc')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 8

  // Filtered and sorted records
  const filteredFDRs = useMemo(() => {
    return fdrs
      .filter((fdr) => {
        // Search
        const query = searchQuery.toLowerCase().trim()
        const matchesSearch =
          !query ||
          fdr.fdrNumber.toLowerCase().includes(query) ||
          fdr.bankName.toLowerCase().includes(query) ||
          (fdr.branchName && fdr.branchName.toLowerCase().includes(query))

        // Status filter
        const matchesStatus =
          statusFilter === 'ALL' || fdr.status === statusFilter

        // Maturity Filter
        let matchesMaturity = true
        const daysLeft = getDaysRemaining(fdr.maturityDate)

        if (maturityFilter === 'MATURING_SOON') {
          // Next 30 days and not closed
          matchesMaturity =
            fdr.status !== 'Matured' &&
            fdr.status !== 'Released' &&
            fdr.status !== 'Rejected' &&
            daysLeft >= 0 &&
            daysLeft <= 30
        } else if (maturityFilter === 'OVERDUE') {
          matchesMaturity =
            fdr.status !== 'Released' &&
            fdr.status !== 'Rejected' &&
            daysLeft < 0
        } else if (maturityFilter === 'FUTURE') {
          matchesMaturity = daysLeft > 30
        }

        return matchesSearch && matchesStatus && matchesMaturity
      })
      .sort((a, b) => {
        let valA = a[sortBy]
        let valB = b[sortBy]

        if (sortBy === 'depositAmount') {
          return sortDirection === 'desc' ? valB - valA : valA - valB
        }

        const dateA = new Date(valA).getTime()
        const dateB = new Date(valB).getTime()
        return sortDirection === 'desc' ? dateB - dateA : dateA - dateB
      })
  }, [fdrs, searchQuery, statusFilter, maturityFilter, sortBy, sortDirection])

  // Pagination
  const totalPages = Math.ceil(filteredFDRs.length / pageSize) || 1
  const paginatedFDRs = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredFDRs.slice(start, start + pageSize)
  }, [filteredFDRs, currentPage, pageSize])

  const handleSort = (column) => {
    if (sortBy === column) {
      setSortDirection(prev => (prev === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortBy(column)
      setSortDirection('desc')
    }
    setCurrentPage(1)
  }

  const resetFilters = () => {
    setSearchQuery('')
    setStatusFilter('ALL')
    setMaturityFilter('ALL')
    setCurrentPage(1)
  }

  return (
    <div className="space-y-6">
      {/* Header and Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Institutional Fixed Deposit Receipts
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Official repository of all security deposits submitted to AICTE. Total: {fdrs.length} records.
          </p>
        </div>

        <Link to="/upload">
          <Button variant="primary" icon={PlusCircle}>
            Upload New FDR
          </Button>
        </Link>
      </div>

      {/* Filter and Search Bar Card */}
      <Card className="p-4 sm:p-5">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          {/* Search Box */}
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by FDR number or bank name..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full pl-9 pr-3.5 py-2.5 text-xs sm:text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20 focus:border-[#142B4A] bg-white text-slate-900 placeholder:text-slate-400"
            />
          </div>

          {/* Status Filter */}
          <div className="md:col-span-3 relative">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full pl-8 pr-7 py-2.5 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="ALL">All Statuses</option>
              {FDR_STATUS_LIST.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
            <Filter className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Maturity Period Filter */}
          <div className="md:col-span-3 relative">
            <select
              value={maturityFilter}
              onChange={(e) => {
                setMaturityFilter(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full pl-8 pr-7 py-2.5 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="ALL">All Maturity Timelines</option>
              <option value="MATURING_SOON">Maturing Soon (Next 30 Days)</option>
              <option value="FUTURE">Active / Long Term (&gt; 30 Days)</option>
              <option value="OVERDUE">Overdue / Past Maturity</option>
            </select>
            <Calendar className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Reset Action */}
          <div className="md:col-span-1 text-right">
            <button
              type="button"
              onClick={resetFilters}
              className="text-xs font-semibold text-slate-500 hover:text-slate-800 underline transition-colors"
            >
              Reset
            </button>
          </div>
        </div>
      </Card>

      {/* Main Records Table */}
      <Card className="p-0 overflow-hidden">
        {filteredFDRs.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No FDR records match the specified filters"
              description="Adjust your search keywords or clear status filters to view the complete list of institutional receipts."
              actionLabel="Reset All Filters"
              onAction={resetFilters}
            />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider bg-slate-50">
                    <th className="py-3 px-5">
                      <button
                        onClick={() => handleSort('fdrNumber')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>FDR Ref Number</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-3 px-5">Bank & Branch</th>
                    <th className="py-3 px-5">
                      <button
                        onClick={() => handleSort('depositAmount')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>Deposit Amount</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-3 px-5">
                      <button
                        onClick={() => handleSort('issueDate')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>Issue Date</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-3 px-5">
                      <button
                        onClick={() => handleSort('maturityDate')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>Maturity Date</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-3 px-5">Status</th>
                    <th className="py-3 px-5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm">
                  {paginatedFDRs.map((fdr) => {
                    const daysLeft = getDaysRemaining(fdr.maturityDate)
                    const isMaturityUrgent =
                      fdr.status !== 'Matured' &&
                      fdr.status !== 'Released' &&
                      daysLeft >= 0 &&
                      daysLeft <= 30

                    return (
                      <tr
                        key={fdr.id}
                        className={`hover:bg-slate-50/80 transition-colors ${
                          isMaturityUrgent ? 'bg-amber-50/20' : ''
                        }`}
                      >
                        <td className="py-4 px-5">
                          <Link
                            to={`/fdrs/${fdr.id}`}
                            className="font-mono font-semibold text-[#142B4A] hover:underline"
                          >
                            {fdr.fdrNumber}
                          </Link>
                          {fdr.jointHolder && (
                            <p className="text-2xs text-slate-600 truncate max-w-xs mt-0.5">
                              Lien: {fdr.jointHolder}
                            </p>
                          )}
                        </td>
                        <td className="py-4 px-5">
                          <p className="font-medium text-slate-800 text-xs sm:text-sm">
                            {fdr.bankName}
                          </p>
                          {fdr.branchName && (
                            <p className="text-2xs text-slate-600 truncate max-w-xs mt-0.5">
                              {fdr.branchName}
                            </p>
                          )}
                        </td>
                        <td className="py-4 px-5 font-bold text-slate-900 text-sm">
                          {formatCurrency(fdr.depositAmount)}
                        </td>
                        <td className="py-4 px-5 text-slate-600 text-xs whitespace-nowrap">
                          {formatDate(fdr.issueDate)}
                        </td>
                        <td className="py-4 px-5 whitespace-nowrap">
                          <p className="text-xs text-slate-700 font-medium">
                            {formatDate(fdr.maturityDate)}
                          </p>
                          {isMaturityUrgent && (
                            <span className="inline-flex items-center gap-1 text-[11px] text-amber-700 font-semibold mt-0.5">
                              <AlertCircle className="w-3 h-3 text-amber-600" />
                              {daysLeft} days left
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-5 whitespace-nowrap">
                          <FDRStatusBadge status={fdr.status} size="sm" />
                        </td>
                        <td className="py-4 px-5 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-2">
                            <Link
                              to={`/fdrs/${fdr.id}`}
                              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-[#142B4A] bg-slate-100 hover:bg-[#142B4A] hover:text-white rounded-lg transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              <span>View Details</span>
                            </Link>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-col sm:flex-row items-center justify-between p-4 border-t border-slate-100 bg-slate-50/50 gap-3 text-xs text-slate-600">
              <div>
                Showing{' '}
                <span className="font-semibold text-slate-800">
                  {Math.min(filteredFDRs.length, (currentPage - 1) * pageSize + 1)}
                </span>{' '}
                to{' '}
                <span className="font-semibold text-slate-800">
                  {Math.min(filteredFDRs.length, currentPage * pageSize)}
                </span>{' '}
                of <span className="font-semibold text-slate-800">{filteredFDRs.length}</span> records
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                >
                  Previous
                </Button>
                <span className="px-2 font-medium">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
