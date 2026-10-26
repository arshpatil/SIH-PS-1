import React from 'react'
import { Badge } from '../ui/Badge'

export function RequestStatusBadge({ status, size = 'md' }) {
  switch (status) {
    case 'Approved':
      return (
        <Badge variant="success" size={size} dot>
          Approved
        </Badge>
      )
    case 'Under Review':
      return (
        <Badge variant="info" size={size} dot>
          Under Review
        </Badge>
      )
    case 'Submitted':
      return (
        <Badge variant="warning" size={size} dot>
          Submitted
        </Badge>
      )
    case 'Processed':
      return (
        <Badge variant="default" size={size} dot>
          Processed
        </Badge>
      )
    case 'Rejected':
      return (
        <Badge variant="danger" size={size} dot>
          Rejected
        </Badge>
      )
    default:
      return (
        <Badge variant="default" size={size}>
          {status || 'Pending'}
        </Badge>
      )
  }
}
