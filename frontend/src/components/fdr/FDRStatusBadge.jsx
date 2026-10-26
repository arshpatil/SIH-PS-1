import React from 'react'
import { Badge } from '../ui/Badge'
import {
  CheckCircle,
  Clock,
  RefreshCw,
  AlertTriangle,
  Archive,
  XCircle,
} from 'lucide-react'

export function FDRStatusBadge({ status, size = 'md' }) {
  switch (status) {
    case 'Active':
      return (
        <Badge variant="success" size={size} dot>
          <span className="flex items-center gap-1">
            Active
          </span>
        </Badge>
      )
    case 'Pending Verification':
      return (
        <Badge variant="warning" size={size} dot>
          <span className="flex items-center gap-1">
            Pending Verification
          </span>
        </Badge>
      )
    case 'Renewal Pending':
      return (
        <Badge variant="info" size={size} dot>
          <span className="flex items-center gap-1">
            Renewal Pending
          </span>
        </Badge>
      )
    case 'Matured':
      return (
        <Badge variant="purple" size={size} dot>
          <span className="flex items-center gap-1">
            Matured
          </span>
        </Badge>
      )
    case 'Released':
      return (
        <Badge variant="default" size={size} dot>
          <span className="flex items-center gap-1">
            Released
          </span>
        </Badge>
      )
    case 'Rejected':
      return (
        <Badge variant="danger" size={size} dot>
          <span className="flex items-center gap-1">
            Rejected
          </span>
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
