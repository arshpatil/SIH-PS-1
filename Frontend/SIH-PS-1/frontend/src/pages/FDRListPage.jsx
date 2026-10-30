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
  RefreshCw,
  Building,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { FDRStatusBadge } from '../components/fdr/FDRStatusBadge'
import { EmptyState } from '../components/ui/EmptyState'
import { formatCurrency } from '../utils/formatters'
import { formatDate, getDaysRemaining } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'
import { reportService } from '../services/reportService'

const SCRUTINY_STATUS_OPTIONS = [
  { value: 'ALL', label: 'All Scrutiny Statuses' },
  { value: 'VERIFIED', label: 'Verified & Approved' },
  { value: 'SUBMITTED', label: 'Submitted (Pending Review)' },
  { value: 'PENDING_VERIFICATION', label: 'Under Verification' },
  { value: 'RETURNED', label: 'Returned (Deficiency)' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'REJECTED', label: 'Rejected' },
]

export function FDRListPage() {
  const { fdrs, currentUser, refreshFDRs, fdrLoading, showToast } = useApp()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [maturityFilter, setMaturityFilter] = useState('ALL')
  const [sortBy, setSortBy] = useState('issueDate')
  const [sortDirection, setSortDirection] = useState('desc')
  const [currentPage, setCurrentPage] = useState(1)
  const [exporting, setExporting] = useState(false)
  const pageSize = 8

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' ||
    currentUser?.role === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

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
          (fdr.branchName && fdr.branchName.toLowerCase().includes(query)) ||
          (fdr.institution_name && fdr.institution_name.toLowerCase().includes(query))

        // Scrutiny status filter
        const fdrStatus = (fdr.scrutiny_status || fdr.status || '').toUpperCase()
        const matchesStatus =
          statusFilter === 'ALL' ||
          fdrStatus === statusFilter ||
          (statusFilter === 'VERIFIED' && fdrStatus === 'ACTIVE')

        // Maturity Filter (Non-overlapping smart brackets)
        let matchesMaturity = true
        const daysLeft = getDaysRemaining(fdr.maturityDate)

        if (maturityFilter === '90D') {
          matchesMaturity = daysLeft > 60 && daysLeft <= 90
        } else if (maturityFilter === '60D') {
          matchesMaturity = daysLeft > 30 && daysLeft <= 60
        } else if (maturityFilter === '30D') {
          matchesMaturity = daysLeft > 7 && daysLeft <= 30
        } else if (maturityFilter === '7D') {
          matchesMaturity = daysLeft >= 0 && daysLeft <= 7
        } else if (maturityFilter === 'MATURED') {
          matchesMaturity = daysLeft >= -30 && daysLeft < 0
        } else if (maturityFilter === 'OVERDUE_ACTION') {
          matchesMaturity = daysLeft < -30
        } else if (maturityFilter === 'ACTIVE') {
          matchesMaturity = daysLeft > 90
        }

        return matchesSearch && matchesStatus && matchesMaturity
      })
      .sort((a, b) => {
        const valA = a[sortBy]
        const valB = b[sortBy]

        if (sortBy === 'depositAmount' || sortBy === 'amount') {
          const numA = parseFloat(valA) || 0
          const numB = parseFloat(valB) || 0
          return sortDirection === 'desc' ? numB - numA : numA - numB
        }

        const dateA = new Date(valA).getTime() || 0
        const dateB = new Date(valB).getTime() || 0
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
      setSortDirection((prev) => (prev === 'desc' ? 'asc' : 'desc'))
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

  const handleExportCSV = async () => {
    setExporting(true)
    try {
      const params = {}
      if (statusFilter !== 'ALL') {
        params.scrutiny_status = statusFilter
      }
      if (maturityFilter !== 'ALL') {
        params.maturity_bracket = maturityFilter
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim()
      }
      const res = await reportService.downloadReportCSV(params)
      showToast(`Exported ${res.filename} successfully!`, 'success')
    } catch (err) {
      showToast(err.message || 'CSV export failed', 'error')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Header and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            {isOfficerOrAdmin ? 'AICTE FDR Scrutiny & Regulatory Repository' : 'Fixed Deposit Receipts (FDRs)'}
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {isOfficerOrAdmin
              ? `Review, verify, and scrutinize institutional FDRs across accredited technical colleges. Total records: ${fdrs.length}`
              : `Official repository of all security deposits submitted and pledged jointly to AICTE. Total: ${fdrs.length} records.`}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="secondary"
            size="md"
            icon={RefreshCw}
            loading={fdrLoading}
            onClick={() => refreshFDRs()}
            title="Refresh from server"
          >
            Refresh
          </Button>

          <Button
            variant="outline"
            size="md"
            icon={Download}
            loading={exporting}
            onClick={handleExportCSV}
          >
            Export CSV
          </Button>

          {!isOfficerOrAdmin && (
            <Link to="/upload">
              <Button variant="warning" size="md" icon={PlusCircle} className="font-semibold shadow-xs">
                Deposit New FDR
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Filter and Search Bar Card */}
      <Card className="p-3.5 sm:p-4.5">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5 sm:gap-3 items-center">
          {/* Search Box */}
          <div className="md:col-span-5 relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder={isOfficerOrAdmin ? 'Search by FDR ref, bank, or institution name...' : 'Search by FDR number or bank name...'}
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full pl-8.5 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20 focus:border-[#142B4A] bg-white text-slate-900 placeholder:text-slate-400"
            />
          </div>

          {/* Scrutiny Status Filter */}
          <div className="md:col-span-3 relative">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full pl-7 pr-7 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              {SCRUTINY_STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <Filter className="w-3 h-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Maturity Period Filter */}
          <div className="md:col-span-3 relative">
            <select
              value={maturityFilter}
              onChange={(e) => {
                setMaturityFilter(e.target.value)
                setCurrentPage(1)
              }}
              className="w-full pl-7 pr-7 py-1.5 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
            >
              <option value="ALL">All Maturity Horizons</option>
              <option value="90D">Expiring in 61–90 Days</option>
              <option value="60D">Expiring in 31–60 Days</option>
              <option value="30D">Expiring in 8–30 Days</option>
              <option value="7D">Critical (&le;7 Days Left)</option>
              <option value="MATURED">Matured (0–30 Days Grace)</option>
              <option value="OVERDUE_ACTION">Overdue Action (&gt;30d Past)</option>
              <option value="ACTIVE">Active (&gt;90 Days Remaining)</option>
            </select>
            <Calendar className="w-3 h-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Reset Action */}
          <div className="md:col-span-1 text-right">
            <button
              type="button"
              onClick={resetFilters}
              className="text-2xs font-semibold text-slate-500 hover:text-navy-800 underline transition-colors"
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
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-2xs font-semibold text-slate-500 uppercase tracking-wider bg-slate-50/70">
                    <th className="py-2.5 px-4">
                      <button
                        onClick={() => handleSort('fdrNumber')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>FDR Ref Number</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    {isOfficerOrAdmin && <th className="py-2.5 px-4">Institution</th>}
                    <th className="py-2.5 px-4">Bank & Branch</th>
                    <th className="py-2.5 px-4">
                      <button
                        onClick={() => handleSort('depositAmount')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>Deposit Amount</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-4">
                      <button
                        onClick={() => handleSort('issueDate')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>Issue Date</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-4">
                      <button
                        onClick={() => handleSort('maturityDate')}
                        className="flex items-center gap-1.5 hover:text-slate-900"
                      >
                        <span>Maturity Date</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </button>
                    </th>
                    <th className="py-2.5 px-4">Scrutiny Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {paginatedFDRs.map((fdr) => {
                    const daysLeft = getDaysRemaining(fdr.maturityDate)
                    const isMaturityUrgent =
                      fdr.status !== 'Matured' &&
                      fdr.status !== 'Released' &&
                      fdr.scrutiny_status !== 'REJECTED' &&
                      daysLeft >= 0 &&
                      daysLeft <= 30

                    return (
                      <tr
                        key={fdr.id}
                        className={`hover:bg-slate-50/80 transition-colors ${
                          isMaturityUrgent ? 'bg-amber-50/20' : ''
                        }`}
                      >
                        <td className="py-3 px-4">
                          <Link
                            to={`/fdrs/${fdr.id}`}
                            className="font-mono font-semibold text-navy-800 hover:underline"
                          >
                            {fdr.fdrNumber}
                          </Link>
                          {fdr.validity_status && fdr.validity_status !== 'ACTIVE' && (
                            <p className="text-[10px] font-semibold text-amber-800 mt-0.5">
                              Validity: {fdr.validity_status}
                            </p>
                          )}
                        </td>
                        {isOfficerOrAdmin && (
                          <td className="py-3 px-4">
                            <p className="font-semibold text-slate-800 text-xs truncate max-w-xs flex items-center gap-1">
                              <Building className="w-3 h-3 text-slate-400 shrink-0" />
                              <span>{fdr.institution_name || 'Affiliated College'}</span>
                            </p>
                          </td>
                        )}
                        <td className="py-3 px-4">
                          <p className="font-medium text-slate-800 text-xs">
                            {fdr.bankName}
                          </p>
                          {fdr.branchName && (
                            <p className="text-2xs text-slate-400 truncate max-w-xs mt-0.5">
                              {fdr.branchName}
                            </p>
                          )}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-900 tabular-nums">
                          {formatCurrency(fdr.depositAmount)}
                        </td>
                        <td className="py-3 px-4 text-slate-600 tabular-nums whitespace-nowrap">
                          {formatDate(fdr.issueDate)}
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <p className="text-xs text-slate-700 font-medium tabular-nums">
                            {formatDate(fdr.maturityDate)}
                          </p>
                          {isMaturityUrgent && (
                            <span className="inline-flex items-center gap-1 text-[11px] text-amber-800 font-semibold mt-0.5">
                              <AlertCircle className="w-3 h-3 text-amber-600 shrink-0" />
                              {daysLeft} days left
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <FDRStatusBadge status={fdr.scrutiny_status || fdr.status} size="sm" />
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <Link
                            to={`/fdrs/${fdr.id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-2xs font-medium text-navy-700 hover:bg-navy-50 rounded border border-slate-200 transition-colors"
                          >
                            <Eye className="w-3 h-3" />
                            <span>{isOfficerOrAdmin ? 'Scrutinize' : 'Details'}</span>
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-col sm:flex-row items-center justify-between p-3.5 border-t border-slate-100 bg-slate-50/50 gap-2.5 text-xs text-slate-600">
              <div>
                Showing{' '}
                <span className="font-semibold text-slate-800 tabular-nums">
                  {Math.min(filteredFDRs.length, (currentPage - 1) * pageSize + 1)}
                </span>{' '}
                to{' '}
                <span className="font-semibold text-slate-800 tabular-nums">
                  {Math.min(filteredFDRs.length, currentPage * pageSize)}
                </span>{' '}
                of <span className="font-semibold text-slate-800 tabular-nums">{filteredFDRs.length}</span> records
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="xs"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                >
                  Previous
                </Button>
                <span className="px-2 text-2xs font-medium tabular-nums">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="xs"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
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

export default FDRListPage
