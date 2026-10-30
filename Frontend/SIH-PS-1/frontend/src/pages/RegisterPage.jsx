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
    <div className="min-h-screen bg-[#F4F7FB] flex flex-col justify-between">
      {/* Official Government Top Bar */}
      <header className="bg-[#0B1B3D] text-slate-300 px-4 sm:px-8 py-2 text-xs border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-white font-semibold tracking-wide">भारत सरकार</span>
          <span className="text-slate-400">|</span>
          <span className="text-slate-200">Government of India</span>
        </div>
        <div className="text-[11px] text-slate-300 hidden sm:block">
          अखिल भारतीय तकनीकी शिक्षा परिषद (AICTE)
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 flex flex-col justify-center py-8 px-4 sm:px-6 lg:px-8 max-w-2xl w-full mx-auto">
        {/* Emblem & Branding Header */}
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-xl bg-[#0B1B3D] text-amber-400 flex items-center justify-center shadow-card mx-auto mb-3 border border-amber-400/30">
            <ShieldCheck className="w-8 h-8 text-amber-400" />
          </div>
          <div className="inline-flex items-center gap-1.5 text-2xs font-bold uppercase tracking-wider text-navy-800 bg-navy-50 px-3 py-0.5 rounded-full border border-navy-200 mb-1.5">
            <span>AICTE Security Deposit Cell</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
            Register New Institution
          </h1>
          <p className="mt-1 text-2xs sm:text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Enroll your technical or educational institute for statutory FDR joint-lien management and AICTE compliance tracking.
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-white py-6 sm:py-8 px-5 sm:px-8 shadow-dropdown rounded-xl border border-slate-200 space-y-5">
          {/* Success Banner */}
          {successMessage && (
            <div className="p-3.5 bg-emerald-50 rounded-lg border border-emerald-300 text-emerald-950 text-xs flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Registration Successful</p>
                <p className="mt-0.5 leading-relaxed">{successMessage}</p>
              </div>
            </div>
          )}

          {/* General Error Banner */}
          {generalError && (
            <div className="p-3.5 bg-rose-50 rounded-lg border border-rose-200 text-rose-950 text-xs flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Registration Error</p>
                <p className="mt-0.5 leading-relaxed">{generalError}</p>
              </div>
            </div>
          )}

          {/* Guidelines Notice */}
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-slate-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-navy-700 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-900">Institutional Portal Registration</p>
              <p className="mt-0.5 text-2xs text-slate-500 leading-relaxed">
                Public registration enrolls primary Technical Institution accounts. Bureau Officer and System Administrator credentials are authorized directly by AICTE Central Administration.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Institution Name */}
            <div>
              <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                Institution Full Legal Name <span className="text-rose-500">*</span>
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
                  className={`w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border ${
                    fieldErrors.name ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                  } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                />
              </div>
              {fieldErrors.name && (
                <p className="text-2xs text-rose-600 mt-1">{fieldErrors.name}</p>
              )}
            </div>

            {/* Grid 1: Official Email & AICTE Permanent ID */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
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
                    className={`w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.email ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.email && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.email}</p>
                )}
              </div>

              <div>
                <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                  AICTE Permanent ID / Approval Code
                </label>
                <div className="relative">
                  <FileBadge className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    name="institution_code"
                    value={formData.institution_code}
                    onChange={handleChange}
                    placeholder="e.g. 1-4392817291"
                    className="w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20 font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Grid 2: Principal / Contact Person & Phone */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                  Principal / Head of Institution <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    name="contact_person"
                    value={formData.contact_person}
                    onChange={handleChange}
                    placeholder="e.g. Dr. Rajesh Sharma"
                    required
                    className={`w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.contact_person ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.contact_person && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.contact_person}</p>
                )}
              </div>

              <div>
                <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                  Contact Phone / Mobile
                </label>
                <div className="relative">
                  <Phone className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="tel"
                    name="contact_phone"
                    value={formData.contact_phone}
                    onChange={handleChange}
                    placeholder="e.g. +91 98765 43210"
                    className={`w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border ${
                      fieldErrors.contact_phone ? 'border-rose-400 ring-1 ring-rose-400' : 'border-slate-300'
                    } bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20`}
                  />
                </div>
                {fieldErrors.contact_phone && (
                  <p className="text-2xs text-rose-600 mt-1">{fieldErrors.contact_phone}</p>
                )}
              </div>
            </div>

            {/* Campus Address */}
            <div>
              <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                Campus Postal Address
              </label>
              <div className="relative">
                <MapPin className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <textarea
                  name="address"
                  rows={2}
                  value={formData.address}
                  onChange={handleChange}
                  placeholder="e.g. Sector 12, Institutional Area, Knowledge Park..."
                  className="w-full pl-9 pr-3.5 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
                />
              </div>
            </div>

            {/* Grid 3: Password & Confirm Password */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
                  Account Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Min 8 characters (letters + numbers)"
                    required
                    className={`w-full pl-9 pr-9 py-2 text-xs sm:text-sm rounded-lg border ${
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
                <label className="block text-2xs font-semibold uppercase text-slate-700 mb-1">
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
                    className={`w-full pl-9 pr-9 py-2 text-xs sm:text-sm rounded-lg border ${
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
              size="md"
              className="w-full mt-3"
              loading={loading}
              icon={ArrowRight}
              iconPosition="right"
            >
              Complete Registration
            </Button>
          </form>

          <div className="pt-3 border-t border-slate-100 text-center text-xs text-slate-600">
            <span>Already have an institutional account? </span>
            <Link to="/login" className="font-semibold text-navy-800 hover:underline">
              Sign In Here &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-3 px-4 text-center text-2xs text-slate-500 border-t border-slate-200 bg-white">
        <span>All India Council for Technical Education (AICTE) — Technical Institutions Registration Gateway</span>
      </footer>
    </div>
  )
}

export default RegisterPage
