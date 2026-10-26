/**
 * Date utility helpers for FDR management system
 */

export function formatDate(dateInput) {
  if (!dateInput) return '-'
  const date = new Date(dateInput)
  if (isNaN(date.getTime())) return '-'
  
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function formatDateISO(dateInput) {
  if (!dateInput) return ''
  const date = new Date(dateInput)
  if (isNaN(date.getTime())) return ''
  return date.toISOString().split('T')[0]
}

export function getDaysRemaining(maturityDateStr) {
  if (!maturityDateStr) return 0
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  
  const maturity = new Date(maturityDateStr)
  maturity.setHours(0, 0, 0, 0)
  
  const diffTime = maturity.getTime() - now.getTime()
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
}

export function isMaturingSoon(maturityDateStr, status) {
  // Maturing soon: falls within the next 30 days and has not already matured or been released
  if (status === 'Matured' || status === 'Released' || status === 'Rejected') {
    return false
  }
  const days = getDaysRemaining(maturityDateStr)
  return days >= 0 && days <= 30
}

export function isOverdue(maturityDateStr, status) {
  if (status === 'Released' || status === 'Rejected') return false
  const days = getDaysRemaining(maturityDateStr)
  return days < 0
}
