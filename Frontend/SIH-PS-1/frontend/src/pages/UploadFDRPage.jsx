import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  UploadCloud,
  FileText,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  RotateCcw,
  FileCheck,
  Info,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { fdrUploadSchema, validateFdrFile } from '../schemas/fdrSchema'
import { SCHEDULED_BANKS } from '../constants/bankList'
import { formatCurrency, formatFileSize } from '../utils/formatters'
import { formatDate } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'

export function UploadFDRPage() {
  const navigate = useNavigate()
  const { addFDR, showToast } = useApp()

  const [step, setStep] = useState(1) // Step 1: Entry, Step 2: Review, Step 3: Success
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileError, setFileError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submittedFdrId, setSubmittedFdrId] = useState(null)
  const [validatedData, setValidatedData] = useState(null)

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(fdrUploadSchema),
    defaultValues: {
      fdrNumber: '',
      bankName: '',
      branchName: '',
      depositAmount: '',
      issueDate: '',
      maturityDate: '',
      interestRate: '7.10% p.a.',
      remarks: '',
    },
  })

  const formValues = watch()

  // Handle local file selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const validation = validateFdrFile(file)
    if (!validation.valid) {
      setFileError(validation.error)
      setSelectedFile(null)
    } else {
      setFileError(null)
      setSelectedFile(file)
    }
  }

  // Step 1 Validation -> Proceed to Review Step
  const onProceedToReview = (data) => {
    if (!selectedFile) {
      setFileError('Please attach a copy of the Fixed Deposit Receipt (PDF/PNG/JPEG)')
      showToast('Please attach a supporting FDR document before proceeding.', 'warning')
      return
    }
    setFileError(null)
    setValidatedData(data)
    setStep(2)
  }

  const onInvalid = (_formErrors) => {
    if (!selectedFile) {
      setFileError('Please attach a copy of the Fixed Deposit Receipt (PDF/PNG/JPEG)')
    }
    showToast('Please correct the highlighted form errors before proceeding.', 'error')
  }

  // Step 2 Submission -> Add to Backend & Upload Document
  const onFinalSubmit = async () => {
    setIsSubmitting(true)
    const payload = validatedData || formValues
    try {
      const res = await addFDR(
        {
          fdrNumber: payload.fdrNumber,
          bankName: payload.bankName,
          branchName: payload.branchName || 'Main Institutional Branch',
          depositAmount: parseFloat(payload.depositAmount),
          issueDate: payload.issueDate,
          maturityDate: payload.maturityDate,
          remarks: payload.remarks || '',
        },
        selectedFile
      )

      setIsSubmitting(false)
      setSubmittedFdrId(res?.record?.id)
      setStep(3)
    } catch (err) {
      setIsSubmitting(false)
      showToast(err.message || 'Failed to submit FDR to backend.', 'error')
    }
  }

  const handleResetForm = () => {
    reset()
    setSelectedFile(null)
    setFileError(null)
    setValidatedData(null)
    setStep(1)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Title */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
          Submit Fixed Deposit Receipt (FDR)
        </h2>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Upload and register institutional security deposit receipts with AICTE joint lien endorsement.
        </p>
      </div>

      {/* Stepper Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-2xs">
        <div className="flex items-center justify-between max-w-lg mx-auto">
          {/* Step 1 */}
          <div className="flex items-center gap-2">
            <span
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                step >= 1 ? 'bg-[#142B4A] text-white' : 'bg-slate-200 text-slate-600'
              }`}
            >
              1
            </span>
            <span className={`text-xs font-medium ${step >= 1 ? 'text-slate-900' : 'text-slate-600'}`}>
              Enter Details
            </span>
          </div>

          <div className={`h-0.5 w-12 sm:w-20 ${step >= 2 ? 'bg-[#142B4A]' : 'bg-slate-200'}`} />

          {/* Step 2 */}
          <div className="flex items-center gap-2">
            <span
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                step >= 2 ? 'bg-[#142B4A] text-white' : 'bg-slate-200 text-slate-600'
              }`}
            >
              2
            </span>
            <span className={`text-xs font-medium ${step >= 2 ? 'text-slate-900' : 'text-slate-600'}`}>
              Review
            </span>
          </div>

          <div className={`h-0.5 w-12 sm:w-20 ${step >= 3 ? 'bg-[#142B4A]' : 'bg-slate-200'}`} />

          {/* Step 3 */}
          <div className="flex items-center gap-2">
            <span
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                step === 3 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'
              }`}
            >
              3
            </span>
            <span className={`text-xs font-medium ${step === 3 ? 'text-slate-900' : 'text-slate-600'}`}>
              Completed
            </span>
          </div>
        </div>
      </div>

      {/* STEP 1: FORM INPUT */}
      {step === 1 && (
        <form onSubmit={handleSubmit(onProceedToReview, onInvalid)} className="space-y-6">
          <Card>
            <CardHeader
              title="Fixed Deposit Receipt Details"
              subtitle="All fields marked with an asterisk (*) are mandatory under AICTE norms"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* FDR Number */}
              <Input
                label="FDR Reference / Receipt Number"
                placeholder="e.g. FDR-SBI-2026-90812"
                required
                error={errors.fdrNumber?.message}
                {...register('fdrNumber')}
              />

              {/* Bank Name */}
              <Select
                label="Issuing Scheduled Bank"
                required
                error={errors.bankName?.message}
                {...register('bankName')}
              >
                <option value="">Select a Scheduled Bank...</option>
                {SCHEDULED_BANKS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </Select>

              {/* Branch Name */}
              <Input
                label="Bank Branch & IFSC Code"
                placeholder="e.g. Pari Chowk Branch (IFSC: SBIN0011472)"
                required
                error={errors.branchName?.message}
                {...register('branchName')}
              />

              {/* Deposit Amount */}
              <Input
                label="Deposit Amount (INR ₹)"
                type="number"
                placeholder="e.g. 2500000"
                required
                error={errors.depositAmount?.message}
                helperText="Minimum deposit required is ₹ 10,000"
                {...register('depositAmount')}
              />

              {/* Issue Date */}
              <Input
                label="FDR Issue Date"
                type="date"
                required
                error={errors.issueDate?.message}
                {...register('issueDate')}
              />

              {/* Maturity Date */}
              <Input
                label="Maturity Date"
                type="date"
                required
                error={errors.maturityDate?.message}
                helperText="Must be later than the FDR issue date"
                {...register('maturityDate')}
              />

              {/* Interest Rate */}
              <Input
                label="Agreed Interest Rate (% p.a.)"
                placeholder="e.g. 7.15% p.a."
                error={errors.interestRate?.message}
                {...register('interestRate')}
              />

              {/* Remarks */}
              <div className="md:col-span-2">
                <Input
                  label="Remarks / Institutional Purpose"
                  placeholder="e.g. Security deposit for introduction of new MCA programme approved in 2026"
                  error={errors.remarks?.message}
                  {...register('remarks')}
                />
              </div>
            </div>
          </Card>

          {/* Document Upload Section */}
          <Card>
            <CardHeader
              title="FDR Document Attachment"
              subtitle="Upload scanned copy of the fixed deposit receipt bearing joint lien with AICTE"
            />

            <div className="space-y-4">
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:bg-slate-50/50 transition-colors">
                <input
                  type="file"
                  id="fdrDocumentFile"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <label
                  htmlFor="fdrDocumentFile"
                  className="cursor-pointer flex flex-col items-center justify-center"
                >
                  <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 mb-3">
                    <UploadCloud className="w-6 h-6 text-[#142B4A]" />
                  </div>
                  <p className="text-sm font-semibold text-slate-800">
                    Click to select file or drag and drop
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Accepted formats: PDF, PNG, JPEG (Max file size: 10 MB)
                  </p>
                </label>
              </div>

              {fileError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{fileError}</span>
                </div>
              )}

              {selectedFile && (
                <div className="flex items-center justify-between p-3.5 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="flex items-center gap-3 truncate">
                    <FileText className="w-5 h-5 text-[#142B4A] shrink-0" />
                    <div className="truncate">
                      <p className="text-xs font-semibold text-slate-900 truncate">
                        {selectedFile.name}
                      </p>
                      <p className="text-2xs text-slate-500">
                        {formatFileSize(selectedFile.size)} • {selectedFile.type || 'Document'}
                      </p>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                    Ready
                  </span>
                </div>
              )}
            </div>
          </Card>

          {/* Form Actions */}
          <div className="flex items-center justify-between pt-2">
            <Button
              variant="secondary"
              icon={RotateCcw}
              onClick={handleResetForm}
            >
              Reset Form
            </Button>

            <Button
              type="submit"
              variant="primary"
              icon={ArrowRight}
            >
              Proceed to Review
            </Button>
          </div>
        </form>
      )}

      {/* STEP 2: REVIEW STEP */}
      {step === 2 && (() => {
        const reviewData = validatedData || formValues
        return (
        <Card className="space-y-6">
          <CardHeader
            title="Review FDR Submission Before Submission"
            subtitle="Please verify the accuracy of the entered fixed deposit details before lodging"
          />

          <div className="p-4 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-xs flex items-start gap-2.5">
            <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Important Institutional Notice:</p>
              <p className="mt-0.5">
                Submissions are logged into the institutional state with initial status <strong>"Pending Verification"</strong>. Simulated actions in this portal do not constitute official AICTE approval.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm divide-y sm:divide-y-0 sm:divide-x divide-slate-100">
            {/* Column 1 */}
            <div className="space-y-3.5 pr-0 sm:pr-4">
              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">FDR Reference #</span>
                <p className="font-mono font-bold text-slate-900 mt-0.5">{reviewData.fdrNumber}</p>
              </div>

              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Issuing Bank</span>
                <p className="font-medium text-slate-800 mt-0.5">{reviewData.bankName}</p>
              </div>

              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Branch Details</span>
                <p className="text-slate-700 mt-0.5">{reviewData.branchName || 'Standard Institutional Branch'}</p>
              </div>

              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Deposit Amount</span>
                <p className="text-lg font-bold text-slate-900 mt-0.5">{formatCurrency(reviewData.depositAmount)}</p>
              </div>
            </div>

            {/* Column 2 */}
            <div className="space-y-3.5 pt-4 sm:pt-0 sm:pl-4">
              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Issue Date</span>
                <p className="font-medium text-slate-800 mt-0.5">{formatDate(reviewData.issueDate)}</p>
              </div>

              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Maturity Date</span>
                <p className="font-medium text-slate-800 mt-0.5">{formatDate(reviewData.maturityDate)}</p>
              </div>

              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Interest Rate</span>
                <p className="font-medium text-slate-800 mt-0.5">{reviewData.interestRate || '7.10% p.a.'}</p>
              </div>

              <div>
                <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Attached File</span>
                <p className="text-xs text-slate-800 font-medium truncate mt-0.5">
                  {selectedFile?.name} ({formatFileSize(selectedFile?.size)})
                </p>
              </div>
            </div>
          </div>

          {reviewData.remarks && (
            <div className="pt-3 border-t border-slate-100">
              <span className="text-2xs font-semibold text-slate-400 uppercase tracking-wider">Remarks / Purpose</span>
              <p className="text-xs text-slate-700 mt-1">{reviewData.remarks}</p>
            </div>
          )}

          {/* Buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-slate-100">
            <Button
              variant="secondary"
              icon={ArrowLeft}
              onClick={() => setStep(1)}
              disabled={isSubmitting}
            >
              Back to Edit
            </Button>

            <Button
              variant="primary"
              icon={FileCheck}
              loading={isSubmitting}
              onClick={onFinalSubmit}
            >
              Confirm & Submit FDR
            </Button>
          </div>
        </Card>
      )})()}

      {/* STEP 3: SUCCESS STATE */}
      {step === 3 && (
        <Card className="p-8 text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-sm">
            <CheckCircle className="w-10 h-10" />
          </div>

          <h3 className="text-xl font-bold text-slate-900">
            FDR Registered Successfully!
          </h3>

          <p className="text-sm text-slate-600 max-w-md mx-auto leading-relaxed">
            Receipt <span className="font-mono font-bold text-slate-900">{formValues.fdrNumber}</span> has been logged into the college dashboard under <strong>Pending Verification</strong> status.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-4">
            {submittedFdrId && (
              <Button
                variant="primary"
                onClick={() => navigate(`/fdrs/${submittedFdrId}`)}
              >
                View This FDR Details
              </Button>
            )}

            <Button
              variant="secondary"
              onClick={() => navigate('/fdrs')}
            >
              View All FDRs
            </Button>

            <Button
              variant="outline"
              onClick={handleResetForm}
            >
              Upload Another FDR
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
