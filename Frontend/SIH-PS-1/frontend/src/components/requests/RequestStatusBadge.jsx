import React from 'react'
import { Badge } from '../ui/Badge'

export function RequestStatusBadge({ status, size = 'md' }) {
  const normalized = (status || '').trim().toLowerCase()

  if (normalized === 'approved') {
    return (
      <Badge variant="success" size={size} dot>
        Approved
      </Badge>
    )
  }

  if (normalized === 'under review') {
    return (
      <Badge variant="info" size={size} dot>
        Under Review
      </Badge>
    )
  }

  if (normalized === 'submitted') {
    return (
      <Badge variant="warning" size={size} dot>
        Submitted
      </Badge>
    )
  }

  if (normalized === 'documents required') {
    return (
      <Badge variant="danger" size={size} dot>
        Documents Required
      </Badge>
    )
  }

  if (normalized === 'resubmitted / awaiting review' || normalized === 'resubmitted') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
        Resubmitted / Awaiting Review
      </span>
    )
  }

  if (normalized === 'pending verification') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
        <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
        Pending Verification
      </span>
    )
  }

  if (normalized === 'closed' || normalized === 'processed') {
    return (
      <Badge variant="default" size={size} dot>
        {status || 'Closed'}
      </Badge>
    )
  }

  if (normalized === 'rejected') {
    return (
      <Badge variant="danger" size={size} dot>
        Rejected
      </Badge>
    )
  }

  return (
    <Badge variant="default" size={size}>
      {status || 'Pending'}
    </Badge>
  )
}
