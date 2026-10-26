import { z } from 'zod'

export const requestFormSchema = z.object({
  fdrId: z.string().min(1, 'Please select an eligible FDR record'),
  requestType: z.enum(['Renewal', 'Release'], {
    errorMap: () => ({ message: 'Please select a valid request type' }),
  }),
  reason: z
    .string()
    .min(15, 'Please provide a clear justification of at least 15 characters')
    .max(1000, 'Justification cannot exceed 1000 characters'),
  durationYears: z
    .coerce
    .number()
    .optional(),
  remarks: z.string().optional().or(z.literal('')),
})
