export const FDR_STATUSES = {
  PENDING_VERIFICATION: 'Pending Verification',
  ACTIVE: 'Active',
  RENEWAL_PENDING: 'Renewal Pending',
  MATURED: 'Matured',
  RELEASED: 'Released',
  REJECTED: 'Rejected',
}

export const FDR_STATUS_LIST = [
  FDR_STATUSES.ACTIVE,
  FDR_STATUSES.PENDING_VERIFICATION,
  FDR_STATUSES.RENEWAL_PENDING,
  FDR_STATUSES.MATURED,
  FDR_STATUSES.RELEASED,
  FDR_STATUSES.REJECTED,
]

export const REQUEST_STATUSES = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  PROCESSED: 'Processed',
}

export const REQUEST_TYPES = {
  RENEWAL: 'Renewal',
  RELEASE: 'Release',
}

export const NOTIFICATION_TYPES = {
  MATURITY_ALERT: 'Maturity Alert',
  VERIFICATION: 'Verification',
  REQUEST_UPDATE: 'Request Update',
  ACTION_REQUIRED: 'Action Required',
}
