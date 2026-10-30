import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, FileQuestion, ShieldCheck } from 'lucide-react'
import { Button } from '../components/ui/Button'

export function NotFoundPage() {
  return (
    <div className="min-h-[55vh] flex flex-col items-center justify-center text-center p-6 bg-white rounded-xl border border-slate-200 shadow-card my-6">
      <div className="w-14 h-14 rounded-xl bg-navy-50 border border-navy-200/60 flex items-center justify-center text-navy-800 mb-3 shadow-2xs">
        <FileQuestion className="w-7 h-7 text-navy-700" />
      </div>
      <span className="text-2xs font-bold uppercase tracking-wider text-amber-700 bg-amber-100 px-2.5 py-0.5 rounded-full border border-amber-300 mb-2">
        HTTP 404 — Not Found
      </span>
      <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">Record or Section Not Found</h2>
      <p className="text-xs sm:text-sm text-slate-500 max-w-sm mt-1 mb-5 leading-relaxed">
        The requested FDR management section, dossier route, or document reference does not exist in the regulatory registry.
      </p>
      <Link to="/">
        <Button variant="primary" icon={ArrowLeft}>
          Return to Portal Dashboard
        </Button>
      </Link>
    </div>
  )
}

export default NotFoundPage
