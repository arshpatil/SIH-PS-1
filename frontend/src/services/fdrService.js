import { initialFDRs } from '../data/mock/mockFDRs'

export const fdrService = {
  getInitialFDRs: () => {
    return [...initialFDRs]
  },

  calculateStats: (fdrs) => {
    const total = fdrs.length
    const active = fdrs.filter(f => f.status === 'Active').length
    
    // Maturing soon: next 30 days & not already matured or released or rejected
    const now = new Date()
    now.setHours(0, 0, 0, 0)

    const maturingSoon = fdrs.filter(f => {
      if (f.status === 'Matured' || f.status === 'Released' || f.status === 'Rejected') {
        return false
      }
      const maturity = new Date(f.maturityDate)
      maturity.setHours(0, 0, 0, 0)
      const diffDays = Math.ceil((maturity.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
      return diffDays >= 0 && diffDays <= 30
    }).length

    const pending = fdrs.filter(f => f.status === 'Pending Verification' || f.status === 'Renewal Pending').length

    return { total, active, maturingSoon, pending }
  },

  getStatusDistribution: (fdrs) => {
    const counts = {}
    fdrs.forEach(f => {
      counts[f.status] = (counts[f.status] || 0) + 1
    })

    const statusColors = {
      'Active': '#10B981',             // emerald-500
      'Pending Verification': '#F59E0B',// amber-500
      'Renewal Pending': '#3B82F6',    // blue-500
      'Matured': '#8B5CF6',            // purple-500
      'Released': '#64748B',           // slate-500
      'Rejected': '#EF4444',           // red-500
    }

    return Object.keys(counts).map(status => ({
      name: status,
      value: counts[status],
      color: statusColors[status] || '#94A3B8',
    }))
  },

  getUpcomingMaturities: (fdrs, limit = 5) => {
    const now = new Date()
    now.setHours(0, 0, 0, 0)

    return fdrs
      .filter(f => f.status !== 'Matured' && f.status !== 'Released' && f.status !== 'Rejected')
      .map(f => {
        const maturity = new Date(f.maturityDate)
        maturity.setHours(0, 0, 0, 0)
        const daysRemaining = Math.ceil((maturity.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
        return { ...f, daysRemaining }
      })
      .filter(f => f.daysRemaining >= 0)
      .sort((a, b) => a.daysRemaining - b.daysRemaining)
      .slice(0, limit)
  },
}
