import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ShieldCheck,
  Lock,
  Mail,
  Building2,
  User,
  Phone,
  MapPin,
  FileBadge,
  ArrowRight,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { authService } from '../services/authService'

export function RegisterPage() {
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    contact_person: '',
    contact_phone: '',
    address: '',
    institution_code: '',
    password: '',
    confirm_password: '',
  })

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState({})
  const [generalError, setGeneralError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    // Clear error on edit
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: null }))
    }
  }

  const validateForm = () => {
    const errors = {}

    if (!formData.name.trim() || formData.name.trim().length < 2) {
      errors.name = 'Institution name is required (min 2 characters).'
    }

    if (!formData.email.trim()) {
      errors.email = 'Official institution email is required.'
    } else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(formData.email.trim())) {
      errors.email = 'Please provide a valid official email address.'
    }

    if (!formData.contact_person.trim() || formData.contact_person.trim().length < 2) {
      errors.contact_person = 'Principal / contact person name is required.'
    }

    if (formData.contact_phone && !/^[0-9+\-\s()]{7,20}$/.test(formData.contact_phone.trim())) {
      errors.contact_phone = 'Please provide a valid contact telephone number.'
    }

    if (!formData.password) {
      errors.password = 'Password is required.'
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters long.'
    } else if (!/[A-Za-z]/.test(formData.password) || !/[0-9]/.test(formData.password)) {
      errors.password = 'Password must contain both letters and at least one number.'
    }

    if (!formData.confirm_password) {
      errors.confirm_password = 'Password confirmation is required.'
    } else if (formData.password !== formData.confirm_password) {
      errors.confirm_password = 'Passwords do not match.'
    }

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setGeneralError(null)
    setSuccessMessage(null)

    if (!validateForm()) {
      return
    }

    setLoading(true)
    try {
      const response = await authService.register({
        name: formData.name.trim(),
        email: formData.email.trim().toLowerCase(),
        contact_person: formData.contact_person.trim(),
        contact_phone: formData.contact_phone.trim() || null,
        address: formData.address.trim() || null,
        institution_code: formData.institution_code.trim() || null,
        password: formData.password,
        confirm_password: formData.confirm_password,
      })

      setSuccessMessage(
        response.message ||
          'Institution registered successfully! Redirecting you to login...'
      )

      // Auto redirect to login after 2 seconds
      setTimeout(() => {
        navigate('/login', {
          state: {
            registeredEmail: formData.email.trim().toLowerCase(),
            justRegistered: true,
          },
        })
      }, 2000)
    } catch (err) {
      const respData = err.response?.data
      if (respData?.details) {
        setFieldErrors(respData.details)
      }
      setGeneralError(
        respData?.error || err.message || 'Registration failed. Please verify the information.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F4F7FB] flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-2xl">
        {/* Emblem & Branding */}
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-[#142B4A] text-amber-400 flex items-center justify-center shadow-lg mb-4">
            <ShieldCheck className="w-10 h-10" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-amber-700 bg-amber-100 px-3 py-1 rounded-full border border-amber-300 mb-2">
            AICTE Security Deposit Cell
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-[#142B4A] tracking-tight">
            Register New Institution
          </h2>
          <p className="mt-1 text-xs sm:text-sm text-slate-500 max-w-md">
            Enroll your technical or educational institute for statutory FDR joint-lien management and AICTE compliance tracking.
          </p>
        </div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-2xl">
        <div className="bg-white py-8 px-6 sm:px-10 shadow-dropdown rounded-2xl border border-slate-200 space-y-6">
          {/* Success Banner */}
          {successMessage && (
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200 text-emerald-900 text-xs sm:text-sm flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Registration Successful</p>
                <p className="mt-0.5 leading-relaxed">{successMessage}</p>
              </div>
            </div>
          )}

          {/* General Error Banner */}
          {generalError && (
            <div className="p-4 bg-rose-50 rounded-xl border border-rose-200 text-rose-900 text-xs sm:text-sm flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Registration Error</p>
                <p className="mt-0.5 leading-relaxed">{generalError}</p>
              </div>
            </div>
          )}

          {/* Guidelines Notice */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-slate-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-[#142B4A] shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-900">Institutional Portal Registration</p>
              <p className="mt-0.5 text-2xs text-slate-500 leading-relaxed">
                Public registration creates primary Institutional Administrator accounts. Bureau Officer and System Administrator credentials are authorized centrally by AICTE.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Institution Name */}
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                Institution Full Name <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Building2 className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder="e.g. Apex Institute of Engineering & Technology"
                  required
                  className={`w-full pl-9 pr-3.5 py-2.5 text-xs sm:text-sm rounded-lg border ${
                    fieldErrors.name ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                  } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                />
              </div>
              {fieldErrors.name && (
                <p className="text-2xs text-rose-600 mt-1">{fieldErrors.name}</p>
              )}
            </div>

            {/* Grid 1: Official Email & AICTE Permanent ID */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Official Institution Email <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="e.g. principal@apexinstitute.edu.in"
                    required
                    className={`w-full pl-9 pr-3.5 py-2.5 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.email ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.email && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.email}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  AICTE Permanent ID / Approval Code
                </label>
                <div className="relative">
                  <FileBadge className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    name="institution_code"
                    value={formData.institution_code}
                    onChange={handleChange}
                    placeholder="e.g. 1-1097213847 (Optional, auto-generated if blank)"
                    className={`w-full pl-9 pr-3.5 py-2.5 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.institution_code ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.institution_code && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.institution_code}</p>
                )}
              </div>
            </div>

            {/* Grid 2: Principal / Contact Person & Phone */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Principal / Authorized Contact Name <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    name="contact_person"
                    value={formData.contact_person}
                    onChange={handleChange}
                    placeholder="e.g. Dr. Rajesh K. Sharma"
                    required
                    className={`w-full pl-9 pr-3.5 py-2.5 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.contact_person ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.contact_person && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.contact_person}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Contact Phone Number
                </label>
                <div className="relative">
                  <Phone className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="tel"
                    name="contact_phone"
                    value={formData.contact_phone}
                    onChange={handleChange}
                    placeholder="e.g. +91 9876543210"
                    className={`w-full pl-9 pr-3.5 py-2.5 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.contact_phone ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.contact_phone && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.contact_phone}</p>
                )}
              </div>
            </div>

            {/* Address */}
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                Campus Postal Address
              </label>
              <div className="relative">
                <MapPin className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <textarea
                  name="address"
                  rows={2}
                  value={formData.address}
                  onChange={handleChange}
                  placeholder="e.g. Plot No. 12, Institutional Area, Sector 62, Noida, Uttar Pradesh 201309"
                  className="w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                />
              </div>
            </div>

            {/* Grid 3: Password & Confirm Password */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Portal Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Min 8 characters (letters & numbers)"
                    required
                    className={`w-full pl-9 pr-10 py-2.5 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.password ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {fieldErrors.password && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.password}</p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">
                  Confirm Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    name="confirm_password"
                    value={formData.confirm_password}
                    onChange={handleChange}
                    placeholder="Re-enter password"
                    required
                    className={`w-full pl-9 pr-10 py-2.5 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.confirm_password ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {fieldErrors.confirm_password && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.confirm_password}</p>
                )}
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full mt-2"
              loading={loading}
              icon={ArrowRight}
            >
              Complete Registration & Create Account
            </Button>
          </form>

          {/* Link back to login */}
          <div className="pt-4 border-t border-slate-100 text-center">
            <p className="text-xs text-slate-600">
              Already have an AICTE institutional account?{' '}
              <Link to="/login" className="font-semibold text-[#142B4A] hover:underline">
                Sign in to FDR Portal
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RegisterPage
