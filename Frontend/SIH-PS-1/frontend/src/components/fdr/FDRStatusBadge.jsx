import React from 'react'
import { Badge } from '../ui/Badge'

export function FDRStatusBadge({ status, size = 'md' }) {
  const normalized = String(status || '').toUpperCase().trim()

  switch (normalized) {
    case 'VERIFIED':
    case 'ACTIVE':
      return (
        <Badge variant="success" size={size} dot>
          <span>Verified / Active</span>
        </Badge>
      )
    case 'SUBMITTED':
      return (
        <Badge variant="info" size={size} dot>
          <span>Submitted</span>
        </Badge>
      )
    case 'PENDING_VERIFICATION':
    case 'PENDING VERIFICATION':
      return (
        <Badge variant="warning" size={size} dot>
          <span>Pending Verification</span>
        </Badge>
      )
    case 'DRAFT':
      return (
        <Badge variant="default" size={size} dot>
          <span>Draft</span>
        </Badge>
      )
    case 'RETURNED':
      return (
        <Badge variant="danger" size={size} dot>
          <span>Returned (Deficiency)</span>
        </Badge>
      )
    case 'REJECTED':
      return (
        <Badge variant="danger" size={size} dot>
          <span>Rejected</span>
        </Badge>
      )
    case 'EXPIRING_SOON':
      return (
        <Badge variant="warning" size={size} dot>
          <span>Expiring Soon</span>
        </Badge>
      )
    case 'MATURED':
      return (
        <Badge variant="purple" size={size} dot>
          <span>Matured</span>
        </Badge>
      )
    case 'OVERDUE_ACTION':
      return (
        <Badge variant="danger" size={size} dot>
          <span>Overdue Action</span>
        </Badge>
      )
    case 'RENEWAL PENDING':
    case 'RENEWAL_PENDING':
      return (
        <Badge variant="info" size={size} dot>
          <span>Renewal Pending</span>
        </Badge>
      )
    case 'RELEASED':
      return (
        <Badge variant="default" size={size} dot>
          <span>Released</span>
        </Badge>
      )
    default:
      return (
        <Badge variant="default" size={size}>
          {status || 'Unknown'}
        </Badge>
      )
  }
}
