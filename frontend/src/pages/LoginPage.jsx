import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck,
  Building,
  Lock,
  Mail,
  ArrowRight,
  AlertCircle,
  Sparkles,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { useAuth } from '../hooks/useAuth'
import { useApp } from '../context/AppContext'

export function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const { profile } = useApp()

  const [email, setEmail] = useState('principal@abcite.edu.in')
  const [password, setPassword] = useState('••••••••••••')
  const [loading, setLoading] = useState(false)

  const handleLogin = (e) => {
    e?.preventDefault()
    setLoading(true)
    setTimeout(() => {
      login(email, password)
      setLoading(false)
      navigate('/')
    }, 400)
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
          {/* Demonstration Notice */}
          <div className="p-3.5 bg-amber-50 rounded-xl border border-amber-200 text-amber-900 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Demonstration Interface</p>
              <p className="mt-0.5 leading-relaxed">
                This is the frontend prototype. You can log in using the pre-filled sample administrator credentials or the quick demo button.
              </p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <Input
              label="College Administrator Email"
              type="email"
              icon={Mail}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. principal@college.edu.in"
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

            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-2 text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  defaultChecked
                  className="rounded text-[#142B4A] focus:ring-[#142B4A]"
                />
                Remember institution
              </label>
              <span className="text-slate-400">Demo Mode</span>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full"
              loading={loading}
              icon={ArrowRight}
            >
              Sign In to College Portal
            </Button>
          </form>

          {/* Quick Demo Instant Access */}
          <div className="pt-4 border-t border-slate-100">
            <Button
              type="button"
              variant="secondary"
              size="md"
              className="w-full bg-slate-50 hover:bg-slate-100 text-slate-800 border-dashed border-slate-300"
              icon={Sparkles}
              onClick={() => handleLogin()}
            >
              Quick Demo Sign-In ({profile.collegeName.split(' ')[0]})
            </Button>
          </div>

          {/* Institutional metadata footer */}
          <div className="text-center text-2xs text-slate-400 space-y-1">
            <p>Authorized access only under AICTE Approval Process Handbook</p>
            <p className="font-mono">Portal Version 2.4-Demo</p>
          </div>
        </div>
      </div>
    </div>
  )
}
