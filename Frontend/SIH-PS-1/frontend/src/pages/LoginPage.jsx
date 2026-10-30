import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import {
  ShieldCheck,
  Lock,
  Mail,
  ArrowRight,
  AlertCircle,
  Building2,
  UserCheck,
  ShieldAlert,
  CheckCircle2,
  Landmark,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, isAuthenticated, authLoading } = useAuth()

  const registeredEmail = location.state?.registeredEmail
  const justRegistered = location.state?.justRegistered

  const [email, setEmail] = useState(registeredEmail || 'principal@abcite.edu.in')
  const [password, setPassword] = useState(registeredEmail ? '' : 'InstitutionPass123!')
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const [registrationNotice] = useState(
    justRegistered ? 'Institution registered successfully! Please enter your password to log in.' : null
  )

  // Redirect to dashboard if session is already active
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, authLoading, navigate])

  const handleLogin = async (e, customEmail = null, customPass = null) => {
    e?.preventDefault()
    setErrorMessage(null)
    setLoading(true)

    const loginEmail = customEmail || email
    const loginPass = customPass || password

    try {
      await login(loginEmail, loginPass)
      navigate('/')
    } catch (err) {
      setErrorMessage(err.message || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  const fillCredentials = (roleEmail, rolePass) => {
    setEmail(roleEmail)
    setPassword(rolePass)
    setErrorMessage(null)
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
      <div className="flex-1 flex flex-col justify-center py-8 px-4 sm:px-6 lg:px-8 max-w-md w-full mx-auto">
        {/* Emblem & Branding Header */}
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-xl bg-[#0B1B3D] text-amber-400 flex items-center justify-center shadow-card mx-auto mb-3 border border-amber-400/30">
            <ShieldCheck className="w-8 h-8 text-amber-400" />
          </div>
          <div className="inline-flex items-center gap-1.5 text-2xs font-bold uppercase tracking-wider text-navy-800 bg-navy-50 px-3 py-0.5 rounded-full border border-navy-200 mb-1.5">
            <span>AICTE Security Deposit Cell</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
            FDR Management Portal
          </h1>
          <p className="mt-1 text-2xs sm:text-xs text-slate-500 max-w-xs mx-auto leading-relaxed">
            Statutory Joint Fixed Deposit Receipt Monitoring & Verification System
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white py-6 sm:py-8 px-5 sm:px-8 shadow-dropdown rounded-xl border border-slate-200 space-y-4 sm:space-y-5">
          {/* Registration Notice if redirected from registration */}
          {registrationNotice && (
            <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-300 text-emerald-950 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Registration Successful</p>
                <p className="mt-0.5 leading-relaxed">{registrationNotice}</p>
              </div>
            </div>
          )}

          {/* Error Banner if any */}
          {errorMessage && (
            <div className="p-3 bg-rose-50 rounded-lg border border-rose-200 text-rose-950 text-xs flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Authentication Error</p>
                <p className="mt-0.5 leading-relaxed">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Connected Backend Notice */}
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-slate-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-navy-700 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-900">Secure Session Authentication</p>
              <p className="mt-0.5 text-2xs text-slate-500 leading-relaxed">
                Protected by encrypted session cookies and role-based access control.
              </p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-3.5">
            <Input
              label="Official Registered Email"
              type="email"
              icon={Mail}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. principal@abcite.edu.in"
              required
            />

            <Input
              label="Password"
              type="password"
              icon={Lock}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full mt-2"
              loading={loading}
              icon={ArrowRight}
              iconPosition="right"
            >
              Sign In to Portal
            </Button>
          </form>

          {/* New Institution Registration Link */}
          <div className="p-3 bg-amber-50/70 rounded-lg border border-amber-200 text-xs flex items-center justify-between gap-2">
            <div>
              <p className="font-bold text-amber-950">New Institution?</p>
              <p className="text-2xs text-amber-800">Register your college to manage statutory FDRs</p>
            </div>
            <Link
              to="/register"
              className="px-2.5 py-1.5 rounded-md bg-[#142B4A] text-white hover:bg-[#0E1E34] text-2xs font-semibold transition-colors shrink-0 shadow-2xs"
            >
              Register &rarr;
            </Link>
          </div>

          {/* Quick Demo Role Selector */}
          <div className="pt-3 border-t border-slate-100 space-y-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 text-center">
              Quick Demonstration Access
            </p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <button
                type="button"
                onClick={() => {
                  fillCredentials('principal@abcite.edu.in', 'InstitutionPass123!')
                  handleLogin(null, 'principal@abcite.edu.in', 'InstitutionPass123!')
                }}
                className="p-2 rounded-lg border border-slate-200 hover:border-amber-400 hover:bg-amber-50/50 flex flex-col items-center text-center transition-all group"
              >
                <Building2 className="w-3.5 h-3.5 text-slate-600 group-hover:text-amber-700 mb-1" />
                <span className="font-semibold text-slate-800 text-2xs">Institution</span>
                <span className="text-[9px] text-slate-400">College User</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  fillCredentials('officer@aicte.gov.in', 'OfficerPass123!')
                  handleLogin(null, 'officer@aicte.gov.in', 'OfficerPass123!')
                }}
                className="p-2 rounded-lg border border-slate-200 hover:border-blue-400 hover:bg-blue-50/50 flex flex-col items-center text-center transition-all group"
              >
                <UserCheck className="w-3.5 h-3.5 text-slate-600 group-hover:text-blue-700 mb-1" />
                <span className="font-semibold text-slate-800 text-2xs">AICTE Officer</span>
                <span className="text-[9px] text-slate-400">Scrutiny Desk</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  fillCredentials('admin@aicte.gov.in', 'AdminPass123!')
                  handleLogin(null, 'admin@aicte.gov.in', 'AdminPass123!')
                }}
                className="p-2 rounded-lg border border-slate-200 hover:border-purple-400 hover:bg-purple-50/50 flex flex-col items-center text-center transition-all group"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-slate-600 group-hover:text-purple-700 mb-1" />
                <span className="font-semibold text-slate-800 text-2xs">Administrator</span>
                <span className="text-[9px] text-slate-400">Central Admin</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-3 px-4 text-center text-2xs text-slate-500 border-t border-slate-200 bg-white">
        <span>All India Council for Technical Education (AICTE) — Fixed Deposit Receipt Portal</span>
      </footer>
    </div>
  )
}

export default LoginPage
