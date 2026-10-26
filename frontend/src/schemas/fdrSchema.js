import { z } from 'zod'

const MAX_FILE_SIZE_MB = 10
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const ACCEPTED_FILE_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/jpg',
  'image/png',
]

export const fdrUploadSchema = z.object({
  fdrNumber: z
    .string()
    .min(3, 'FDR Reference Number must be at least 3 characters')
    .max(50, 'FDR Reference Number cannot exceed 50 characters')
    .regex(/^[A-Za-z0-9\-_/]+$/, 'Only alphanumeric characters, dashes, and slashes allowed'),
  bankName: z
    .string()
    .min(2, 'Bank name is required'),
  branchName: z
    .string()
    .min(2, 'Branch name and IFSC details are recommended')
    .optional()
    .or(z.literal('')),
  depositAmount: z
    .coerce
    .number({ invalid_type_error: 'Deposit amount must be a valid number' })
    .positive('Deposit amount must be greater than zero')
    .min(10000, 'Minimum deposit amount for AICTE FDR is ₹10,000'),
  issueDate: z
    .string()
    .min(1, 'Issue date is required'),
  maturityDate: z
    .string()
    .min(1, 'Maturity date is required'),
  interestRate: z
    .string()
    .optional()
    .or(z.literal('')),
  remarks: z
    .string()
    .max(500, 'Remarks cannot exceed 500 characters')
    .optional()
    .or(z.literal('')),
}).refine(data => {
  if (!data.issueDate || !data.maturityDate) return true
  const issue = new Date(data.issueDate)
  const maturity = new Date(data.maturityDate)
  return maturity > issue
}, {
  message: 'Maturity date must be later than the issue date',
  path: ['maturityDate'],
})

export const validateFdrFile = (file) => {
  if (!file) {
    return { valid: false, error: 'Supporting FDR document is required' }
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: `File size exceeds ${MAX_FILE_SIZE_MB}MB limit` }
  }
  if (!ACCEPTED_FILE_TYPES.includes(file.type)) {
    return { valid: false, error: 'Only PDF, JPEG, and PNG formats are accepted' }
  }
  return { valid: true, error: null }
}
