import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck,
  Lock,
  Mail,
  ArrowRight,
  AlertCircle,
  Building2,
  UserCheck,
  ShieldAlert,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'

export function LoginPage() {
  const navigate = useNavigate()
  const { login, isAuthenticated, authLoading } = useAuth()

  const [email, setEmail] = useState('principal@abcite.edu.in')
  const [password, setPassword] = useState('InstitutionPass123!')
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)

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
    <div className="min-h-screen bg-[#F4F7FB] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Emblem & Branding */}
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-[#142B4A] text-amber-400 flex items-center justify-center shadow-lg mb-4">
            <ShieldCheck className="w-10 h-10" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-amber-700 bg-amber-100 px-3 py-1 rounded-full border border-amber-300 mb-2">
            AICTE Security Deposit Cell
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-[#142B4A] tracking-tight">
            FDR Portal
          </h2>
          <p className="mt-1 text-xs text-slate-500 max-w-xs">
            Fixed Deposit Receipt Management System for Technical Institutions
          </p>
        </div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 sm:px-10 shadow-dropdown rounded-2xl border border-slate-200 space-y-6">
          {/* Error Banner if any */}
          {errorMessage && (
            <div className="p-3.5 bg-rose-50 rounded-xl border border-rose-200 text-rose-900 text-xs flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Authentication Error</p>
                <p className="mt-0.5 leading-relaxed">{errorMessage}</p>
              </div>
            </div>
          )}

          {/* Connected Backend Notice */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-slate-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-[#142B4A] shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-900">Secure Flask Session Authentication</p>
              <p className="mt-0.5 text-2xs text-slate-500 leading-relaxed">
                Connects directly to the backend API with HttpOnly session cookies and CSRF synchronizer tokens.
              </p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
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
              size="lg"
              className="w-full"
              loading={loading}
              icon={ArrowRight}
            >
              Sign In to Portal
            </Button>
          </form>

          {/* Quick Demo Role Selector */}
          <div className="pt-4 border-t border-slate-100 space-y-2">
            <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 text-center">
              Quick Role Sign-In
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
                <Building2 className="w-4 h-4 text-slate-600 group-hover:text-amber-600 mb-1" />
                <span className="font-semibold text-slate-800 text-[11px]">Institution</span>
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
                <UserCheck className="w-4 h-4 text-slate-600 group-hover:text-blue-600 mb-1" />
                <span className="font-semibold text-slate-800 text-[11px]">AICTE Officer</span>
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
                <ShieldCheck className="w-4 h-4 text-slate-600 group-hover:text-purple-600 mb-1" />
                <span className="font-semibold text-slate-800 text-[11px]">Administrator</span>
                <span className="text-[9px] text-slate-400">System Admin</span>
              </button>
            </div>
          </div>

          {/* Institutional metadata footer */}
          <div className="text-center text-2xs text-slate-400 space-y-1">
            <p>Authorized access only under AICTE Approval Process Handbook</p>
            <p className="font-mono">Smart India Hackathon 2024</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
