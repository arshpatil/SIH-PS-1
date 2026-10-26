import { z } from 'zod'

export const profileSchema = z.object({
  collegeName: z.string().min(3, 'College name must be at least 3 characters'),
  adminName: z.string().min(2, 'Administrator name is required'),
  designation: z.string().min(2, 'Designation is required'),
  email: z.string().email('Please enter a valid official email address'),
  alternateEmail: z.string().email('Please enter a valid alternate email').optional().or(z.literal('')),
  contactNumber: z.string().min(10, 'Contact number must be at least 10 digits'),
  address: z.string().min(5, 'Institutional address is required'),
  city: z.string().min(2, 'City is required'),
  state: z.string().min(2, 'State is required'),
  pincode: z.string().regex(/^\d{6}$/, 'PIN Code must be a 6-digit number'),
})
