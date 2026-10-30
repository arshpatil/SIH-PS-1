import React, { useState, useEffect } from 'react'
import {
  Building2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  Info,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  ArrowRightLeft,
} from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { Button } from '../ui/Button'
import { formatDate } from '../../utils/dateUtils'
import { formatCurrency } from '../../utils/formatters'
import { bankService } from '../../services/bankService'
import { useApp } from '../../context/AppContext'

export function BankVerificationCard({ fdr, onVerified }) {
  const { showToast } = useApp()
  const [providerInfo, setProviderInfo] = useState(null)
  const [latestVerification, setLatestVerification] = useState(null)
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [selectedScenario, setSelectedScenario] = useState('MATCHED')
  const [isVerifying, setIsVerifying] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)

  const activeVerification = latestVerification || fdr?.latest_bank_verification || null

  // Fetch provider info on mount
  useEffect(() => {
    let isMounted = true
    bankService
      .getBankStatus()
      .then((data) => {
        if (isMounted) setProviderInfo(data)
      })
      .catch(() => {
        // Fallback default info
        if (isMounted) {
          setProviderInfo({
            provider_name: 'SIMULATED_MOCK_PROVIDER',
            provider_mode: 'DEMO',
            is_demo: true,
            is_mock: true,
            disclaimer:
              'PROTOTYPE DEMONSTRATION ONLY: Synthetic test data from MockBankProvider. No real bank network connected.',
          })
        }
      })
    return () => {
      isMounted = false
    }
  }, [])

  const handleVerify = async () => {
    if (!fdr?.id) return
    setIsVerifying(true)
    try {
      const res = await bankService.verifyFDR(fdr.id, selectedScenario)
      setLatestVerification(res.data)
      showToast(res.message || 'Simulated bank verification completed.', 'info')
      if (onVerified) {
        onVerified(res.data)
      }
      // Refresh history if open
      if (showHistory) {
        loadHistory()
      }
    } catch (err) {
      showToast(
        err.response?.data?.error || err.message || 'Bank verification check failed.',
        'error'
      )
    } finally {
      setIsVerifying(false)
    }
  }

  const loadHistory = async () => {
    if (!fdr?.id) return
    setIsLoadingHistory(true)
    try {
      const logs = await bankService.getVerificationHistory(fdr.id)
      setHistory(logs)
    } catch {
      // Ignore or toast
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const toggleHistory = () => {
    if (!showHistory && history.length === 0) {
      loadHistory()
    }
    setShowHistory(!showHistory)
  }

  const status = activeVerification?.verification_status || 'NOT_CHECKED'
  const isDemo = providerInfo?.is_demo ?? true

  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden">
      {/* Header Banner */}
      <CardHeader className="bg-[#0B1B3D] border-b border-[#142B4A] text-white p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-white/10 text-amber-300 border border-white/10 shrink-0">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
                  Core Banking Integration Layer
                </h3>
                {isDemo && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-extrabold uppercase bg-amber-400/20 text-amber-300 border border-amber-400/40 tracking-wider">
                    DEMO MODE
                  </span>
                )}
              </div>
              <p className="text-2xs text-slate-300 mt-0.5">
                Provider: <span className="font-mono text-amber-200">{providerInfo?.provider_name || 'SIMULATED_MOCK_PROVIDER'}</span> (Simulated CBS Verification)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="xs"
              className="bg-white/10 hover:bg-white/20 text-white border-white/20 text-2xs"
              icon={RefreshCw}
              loading={isVerifying}
              onClick={handleVerify}
            >
              Run Simulated Check
            </Button>
          </div>
        </div>
      </CardHeader>

      <div className="p-4 sm:p-6 space-y-4">
        {/* Prototype Disclaimer Notice */}
        <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200/90 text-amber-950 flex items-start gap-2.5 text-2xs">
          <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-0.5 leading-relaxed">
            <span className="font-bold">Prototype Demonstration Layer: </span>
            <span>
              This is a prototype integration displaying deterministic synthetic data for evaluation. No real banking connectivity exists. Simulated responses are not legal proof of deposit status and do not silently alter official FDR records.
            </span>
          </div>
        </div>

        {/* Verification Status Overview */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-2xs text-slate-500 font-semibold uppercase block mb-1">
              Verification Status
            </span>
            {status === 'MATCHED' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Simulated: Details Matched
              </span>
            )}
            {status === 'MISMATCH' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                Simulated: Discrepancy
              </span>
            )}
            {status === 'NOT_FOUND' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                <XCircle className="w-3.5 h-3.5 text-rose-600" />
                Simulated: Account Not Found
              </span>
            )}
            {status === 'UNAVAILABLE' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-200 text-slate-800 border border-slate-300">
                <Clock className="w-3.5 h-3.5 text-slate-600" />
                Simulated: Gateway Timeout
              </span>
            )}
            {status === 'NOT_CHECKED' && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                Not Verified Yet
              </span>
            )}
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-2xs text-slate-500 font-semibold uppercase block mb-1">
              Provider Mode
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold font-mono text-slate-900">
                {activeVerification?.provider_mode || providerInfo?.provider_mode || 'DEMO'}
              </span>
              <span className="text-2xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-semibold border border-purple-200">
                Synthetic Mock
              </span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-2xs text-slate-500 font-semibold uppercase block mb-1">
              Bank Reference
            </span>
            <span className="text-xs font-mono font-bold text-slate-900 truncate block">
              {activeVerification?.bank_reference || 'N/A (Pending Check)'}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-2xs text-slate-500 font-semibold uppercase block mb-1">
              Last Checked
            </span>
            <span className="text-xs font-medium text-slate-700 block">
              {activeVerification?.created_at ? formatDate(activeVerification.created_at) : 'Never'}
            </span>
          </div>
        </div>

        {/* Message / Feedback */}
        {activeVerification?.message && (
          <div className="text-xs text-slate-700 bg-slate-50 p-3 rounded-xl border border-slate-200">
            <span className="font-semibold text-slate-900">Provider Message: </span>
            {activeVerification.message}
          </div>
        )}

        {/* Discrepancy / Mismatch Detail Alert */}
        {status === 'MISMATCH' && activeVerification?.mismatched_fields && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 space-y-2">
            <div className="flex items-center gap-2 text-rose-900 font-bold text-xs">
              <ShieldAlert className="w-4 h-4 text-rose-600" />
              <span>Simulated Core Banking Parameter Discrepancies</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-2xs">
              {Object.entries(activeVerification.mismatched_fields).map(([fieldName, diff]) => (
                <div key={fieldName} className="p-2.5 rounded bg-white border border-rose-200 space-y-1">
                  <div className="font-bold text-rose-950 uppercase tracking-wide">
                    {fieldName.replace(/_/g, ' ')}
                  </div>
                  <div className="flex items-center justify-between text-slate-600 pt-0.5">
                    <span>Portal Claimed:</span>
                    <span className="font-mono font-semibold text-slate-900">
                      {fieldName.includes('amount') ? formatCurrency(diff.expected) : String(diff.expected)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-rose-700">
                    <span>Simulated Bank CBS:</span>
                    <span className="font-mono font-bold text-rose-800">
                      {fieldName.includes('amount') ? formatCurrency(diff.bank_value) : String(diff.bank_value)}
                    </span>
                  </div>
                  {diff.discrepancy_note && (
                    <p className="text-rose-600 italic text-3xs pt-1 border-t border-rose-100">
                      {diff.discrepancy_note}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Matched Fields List */}
        {status === 'MATCHED' && activeVerification?.matched_fields && (
          <div className="p-3 rounded-xl bg-emerald-50/80 border border-emerald-200 space-y-2">
            <div className="flex items-center gap-2 text-emerald-900 font-bold text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Verified Parameters (Matched in Simulated CBS)</span>
            </div>
            <div className="flex flex-wrap gap-2 text-2xs">
              {Object.entries(activeVerification.matched_fields).map(([k, v]) => (
                <span
                  key={k}
                  className="px-2.5 py-1 rounded-md bg-white border border-emerald-200 text-emerald-950 font-medium flex items-center gap-1.5"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span className="capitalize">{k.replace(/_/g, ' ')}:</span>
                  <span className="font-mono font-bold">
                    {k.includes('amount') ? formatCurrency(v) : String(v)}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Evaluator Simulation Control Panel (DEMO Mode) */}
        {isDemo && (
          <div className="p-3.5 rounded-xl bg-slate-100/80 border border-slate-200 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-2xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <ArrowRightLeft className="w-3.5 h-3.5 text-slate-500" />
                SIH Prototype Simulation Scenario
              </span>
              <span className="text-3xs text-slate-500">Select test scenario to simulate response</span>
            </div>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
              <select
                value={selectedScenario}
                onChange={(e) => setSelectedScenario(e.target.value)}
                className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20"
              >
                <option value="MATCHED">Simulate Matched (Details Consistent)</option>
                <option value="MISMATCH">Simulate Discrepancy (Amount & Date Mismatch)</option>
                <option value="NOT_FOUND">Simulate Not Found (Account Missing in Bank)</option>
                <option value="UNAVAILABLE">Simulate Gateway Timeout (Bank Service Down)</option>
              </select>

              <Button
                variant="primary"
                size="xs"
                className="bg-[#142B4A] hover:bg-[#1A3C67] text-white shrink-0"
                icon={RefreshCw}
                loading={isVerifying}
                onClick={handleVerify}
              >
                Simulate Check
              </Button>
            </div>
          </div>
        )}

        {/* Verification History Accordion */}
        <div className="pt-1">
          <button
            type="button"
            onClick={toggleHistory}
            className="flex items-center justify-between w-full text-2xs font-bold uppercase text-slate-600 hover:text-slate-900 transition-colors py-1"
          >
            <span>Previous Bank Verification Queries ({history.length})</span>
            {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showHistory && (
            <div className="mt-2 space-y-2 border-t border-slate-200 pt-2 max-h-48 overflow-y-auto pr-1">
              {isLoadingHistory ? (
                <div className="text-center py-3 text-2xs text-slate-500">Loading history...</div>
              ) : history.length === 0 ? (
                <div className="text-center py-3 text-2xs text-slate-500 italic">
                  No previous verification queries recorded for this FDR.
                </div>
              ) : (
                history.map((log) => (
                  <div
                    key={log.id}
                    className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between text-2xs"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900">{log.verification_status}</span>
                        <span className="text-3xs px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 font-semibold">
                          {log.provider_mode}
                        </span>
                        {log.bank_reference && (
                          <span className="text-slate-500 font-mono text-3xs">
                            Ref: {log.bank_reference}
                          </span>
                        )}
                      </div>
                      <p className="text-slate-600 mt-0.5">{log.message}</p>
                    </div>
                    <span className="text-slate-400 font-mono shrink-0 ml-3">
                      {formatDate(log.created_at)}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
