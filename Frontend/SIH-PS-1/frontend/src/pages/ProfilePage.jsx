import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Building2,
  RotateCcw,
  ShieldCheck,
  Info,
  Save,
  Shield,
  CheckCircle,
  Loader2,
  UserCheck,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { profileSchema } from '../schemas/profileSchema'
import { formatDate } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'
import { reportService } from '../services/reportService'

export function ProfilePage() {
  const { profile, currentUser, updateProfile, showToast } = useApp()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [auditLogs, setAuditLogs] = useState([])
  const [auditLoading, setAuditLoading] = useState(false)

  useEffect(() => {
    let isMounted = true
    async function fetchAudit() {
      setAuditLoading(true)
      try {
        const res = await reportService.getAuditLogs({ per_page: 15 })
        if (isMounted && res?.data) {
          setAuditLogs(res.data)
        }
      } catch {
        // Fallback silently if audit logs cannot be fetched
      } finally {
        if (isMounted) setAuditLoading(false)
      }
    }
    fetchAudit()
    return () => {
      isMounted = false
    }
  }, [])

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' || currentUser?.role === 'ADMIN'

  // Form for Institution Profile
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      collegeName: profile.collegeName || '',
      adminName: profile.adminName || currentUser?.full_name || '',
      designation: profile.designation || 'Director / Principal',
      email: profile.email || currentUser?.email || '',
      alternateEmail: profile.alternateEmail || '',
      contactNumber: profile.contactNumber || '',
      address: profile.address || '',
      city: profile.city || '',
      state: profile.state || '',
      pincode: profile.pincode || '',
    },
  })

  // Sync form when profile data changes
  useEffect(() => {
    if (!isOfficerOrAdmin && profile) {
      reset({
        collegeName: profile.collegeName || '',
        adminName: profile.adminName || currentUser?.full_name || '',
        designation: profile.designation || 'Director / Principal',
        email: profile.email || currentUser?.email || '',
        alternateEmail: profile.alternateEmail || '',
        contactNumber: profile.contactNumber || '',
        address: profile.address || '',
        city: profile.city || '',
        state: profile.state || '',
        pincode: profile.pincode || '',
      })
    }
  }, [profile, currentUser, isOfficerOrAdmin, reset])

  // Institution profile submission
  const onSubmitInstitution = async (data) => {
    setIsSubmitting(true)
    try {
      await updateProfile({
        adminName: data.adminName,
        full_name: data.adminName,
        address: data.address,
        institution_address: data.address,
        contactNumber: data.contactNumber,
        contact_phone: data.contactNumber,
        alternateEmail: data.alternateEmail,
        contact_email: data.alternateEmail,
        collegeName: data.collegeName,
        city: data.city,
        state: data.state,
        pincode: data.pincode,
      })
      reset(data)
      showToast('Institutional profile updated successfully.', 'success')
    } catch (err) {
      console.error('Failed to update profile:', err)
      showToast(err.message || 'Failed to update profile.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleResetInstitution = () => {
    reset({
      collegeName: profile.collegeName || '',
      adminName: profile.adminName || currentUser?.full_name || '',
      designation: profile.designation || 'Director / Principal',
      email: profile.email || currentUser?.email || '',
      alternateEmail: profile.alternateEmail || '',
      contactNumber: profile.contactNumber || '',
      address: profile.address || '',
      city: profile.city || '',
      state: profile.state || '',
      pincode: profile.pincode || '',
    })
  }

  // Officer / Admin profile state
  const [officerName, setOfficerName] = useState(currentUser?.full_name || '')
  const [prevFullName, setPrevFullName] = useState(currentUser?.full_name)

  if (currentUser?.full_name && currentUser.full_name !== prevFullName) {
    setPrevFullName(currentUser.full_name)
    setOfficerName(currentUser.full_name)
  }

  const isOfficerDirty = officerName.trim() !== (currentUser?.full_name || '')

  const onSubmitOfficer = async (e) => {
    e.preventDefault()
    if (!officerName.trim()) {
      showToast('Name cannot be empty', 'error')
      return
    }
    setIsSubmitting(true)
    try {
      await updateProfile({
        full_name: officerName.trim(),
        adminName: officerName.trim(),
      })
      showToast('Officer profile updated successfully.', 'success')
    } catch (err) {
      console.error('Failed to update officer profile:', err)
      showToast(err.message || 'Failed to update profile.', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleResetOfficer = () => {
    setOfficerName(currentUser?.full_name || '')
  }

  // --------------------------------------------------------------------------
  // AICTE OFFICER / ADMIN PROFILE VIEW
  // --------------------------------------------------------------------------
  if (isOfficerOrAdmin) {
    return (
      <div className="max-w-4xl mx-auto space-y-5 sm:space-y-6">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            AICTE Official Profile & Bureau Credentials
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Administrative credentials and regulatory authorization details for FDR verification and compliance scrutiny.
          </p>
        </div>

        {/* Bureau Officer Banner */}
        <div className="bg-[#0B1B3D] border border-[#1E3A63] rounded-xl p-5 sm:p-6 text-white shadow-subtle relative overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-xl bg-amber-500 text-slate-950 flex items-center justify-center font-bold text-base shrink-0 shadow-xs">
                <Shield className="w-5 h-5 text-navy-950" />
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-bold leading-tight text-white">
                  {currentUser?.full_name || 'AICTE Officer'}
                </h3>
                <p className="text-2xs sm:text-xs text-slate-300 font-mono mt-1">
                  Official Account: {currentUser?.email}
                </p>
                <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/10 text-amber-300 text-2xs font-semibold border border-white/15">
                  <CheckCircle className="w-3 h-3 text-amber-400" />
                  <span>
                    {currentUser?.role === 'ADMIN'
                      ? 'Central System Administrator'
                      : 'Authorized Desk Scrutiny Officer'}
                  </span>
                </div>
              </div>
            </div>

            <div className="text-left sm:text-right sm:border-l sm:border-white/10 sm:pl-6 text-2xs text-slate-300">
              <span className="text-slate-400">Account Authorization:</span>
              <p className="font-semibold text-emerald-400 text-xs mt-0.5">Active & In Good Standing</p>
              {currentUser?.last_login_at && (
                <p className="text-2xs text-slate-400 mt-1 tabular-nums">
                  Last Login: {formatDate(currentUser.last_login_at)}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Officer Details Form */}
        <form onSubmit={onSubmitOfficer} className="space-y-5">
          <Card className="p-4 sm:p-6">
            <CardHeader
              title="Official Identity & Credentials"
              subtitle="Registered regulatory identity in the AICTE FDR Scrutiny Division"
              icon={UserCheck}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Full Name / Officer Designation"
                required
                value={officerName}
                onChange={(e) => setOfficerName(e.target.value)}
                helperText="Displayed on audit logs and regulatory approval records"
              />

              <Input
                label="Official Registered Email"
                value={currentUser?.email || ''}
                disabled
                helperText="Government SSO authentication identifier"
              />

              <Input
                label="Assigned System Role"
                value={currentUser?.role || ''}
                disabled
                helperText="Role-based permissions assigned by AICTE Central Administration"
              />

              <Input
                label="Jurisdiction / Bureau"
                value="Central Monitoring & Regional Oversight"
                disabled
                helperText="Authorized for multi-institution review"
              />
            </div>
          </Card>

          <Card className="p-4 sm:p-6">
            <CardHeader
              title="Security & Regulatory Compliance"
              subtitle="Auditing and accountability standards"
              icon={ShieldCheck}
            />
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-700 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-navy-700 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-semibold text-slate-900">
                  Statutory Audit Compliance Notice
                </p>
                <p className="text-2xs text-slate-500 leading-relaxed">
                  All FDR workflow transitions, release approvals, and deficiency notices issued under your credentials are cryptographically stamped with your user ID and recorded in the permanent audit trail.
                </p>
              </div>
            </div>
          </Card>

          <div className="flex items-center justify-between pt-1">
            <Button
              type="button"
              variant="secondary"
              icon={RotateCcw}
              onClick={handleResetOfficer}
              disabled={!isOfficerDirty || isSubmitting}
            >
              Discard Changes
            </Button>

            <Button
              type="submit"
              variant="primary"
              icon={Save}
              loading={isSubmitting}
              disabled={!isOfficerDirty}
            >
              Save Officer Profile
            </Button>
          </div>
        </form>
      </div>
    )
  }

  // --------------------------------------------------------------------------
  // INSTITUTION PROFILE VIEW
  // --------------------------------------------------------------------------
  return (
    <div className="max-w-4xl mx-auto space-y-5 sm:space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
          College Profile & Institutional Settings
        </h2>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Review and update institution contact details and authorized administrator credentials for AICTE records.
        </p>
      </div>

      {/* Institutional Read-Only Summary Banner */}
      <div className="bg-[#0B1B3D] border border-[#1E3A63] rounded-xl p-5 sm:p-6 text-white shadow-subtle relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-amber-500 text-slate-950 flex items-center justify-center font-bold text-base shrink-0 shadow-xs">
              <Building2 className="w-5 h-5 text-navy-950" />
            </div>
            <div>
              <h3 className="text-base sm:text-lg font-bold leading-tight text-white">
                {profile.collegeName || currentUser?.institution_name || 'Technical Institution'}
              </h3>
              <p className="text-2xs sm:text-xs text-slate-300 font-mono mt-1">
                Permanent AICTE ID: {profile.aictePermanentId || currentUser?.institution_code || '1-4392817291'} • Session {profile.approvalYear || '2026-2027'}
              </p>
              <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/10 text-amber-300 text-2xs font-semibold border border-white/15">
                <ShieldCheck className="w-3 h-3 text-amber-400" />
                <span>AICTE Approved Technical Institution</span>
              </div>
            </div>
          </div>

          <div className="text-left sm:text-right sm:border-l sm:border-white/10 sm:pl-6 text-2xs text-slate-300">
            <span className="text-slate-400">Last Records Audit:</span>
            <p className="font-mono text-white text-xs mt-0.5 tabular-nums">
              {formatDate(profile.lastUpdated || '2026-10-18T10:30:00Z')}
            </p>
          </div>
        </div>
      </div>

      {/* Editable Form */}
      <form onSubmit={handleSubmit(onSubmitInstitution)} className="space-y-5">
        {/* Institution Details */}
        <Card className="p-4 sm:p-6">
          <CardHeader
            title="Institutional Information"
            subtitle="Official institutional title and regulatory identifiers"
            icon={Building2}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <Input
                label="College / Institution Full Name"
                required
                error={errors.collegeName?.message}
                {...register('collegeName')}
              />
            </div>

            <Input
              label="AICTE Permanent ID (Locked)"
              value={profile.aictePermanentId || currentUser?.institution_code || '1-4392817291'}
              disabled
              helperText="Assigned by AICTE Central Approval Bureau"
            />

            <Input
              label="Current Approval Academic Year"
              value={profile.approvalYear || '2026-2027'}
              disabled
              helperText="Managed via annual Extension of Approval (EoA)"
            />
          </div>
        </Card>

        {/* Administrator Details */}
        <Card className="p-4 sm:p-6">
          <CardHeader
            title="Authorized College Administrator"
            subtitle="Primary contact officer authorized for FDR joint operations"
            icon={UserCheck}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Administrator / Principal Name"
              required
              error={errors.adminName?.message}
              {...register('adminName')}
            />

            <Input
              label="Designation / Role"
              required
              error={errors.designation?.message}
              {...register('designation')}
            />

            <Input
              label="Official Email Address"
              type="email"
              required
              error={errors.email?.message}
              {...register('email')}
            />

            <Input
              label="Official Contact Number"
              placeholder="+91 98450 12345"
              required
              error={errors.contactNumber?.message}
              {...register('contactNumber')}
            />

            <div className="md:col-span-2">
              <Input
                label="Alternate Notification Email"
                type="email"
                placeholder="registrar@abcite.edu.in"
                error={errors.alternateEmail?.message}
                helperText="Receives copies of 30-day maturity alerts and renewal approvals"
                {...register('alternateEmail')}
              />
            </div>
          </div>
        </Card>

        {/* Location & Physical Address */}
        <Card className="p-4 sm:p-6">
          <CardHeader
            title="Campus Postal Address"
            subtitle="Campus location for formal regulatory correspondence"
            icon={Building2}
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-3">
              <Input
                label="Registered Institutional Address"
                required
                error={errors.address?.message}
                {...register('address')}
              />
            </div>

            <Input
              label="City"
              required
              error={errors.city?.message}
              {...register('city')}
            />

            <Input
              label="State / Union Territory"
              required
              error={errors.state?.message}
              {...register('state')}
            />

            <Input
              label="PIN Code"
              required
              error={errors.pincode?.message}
              {...register('pincode')}
            />
          </div>
        </Card>

        {/* Joint Lien Details (Read-only reference) */}
        <Card className="p-4 sm:p-6">
          <CardHeader
            title="Joint Account Endorsement"
            subtitle="Statutory joint signatory mapping"
            icon={ShieldCheck}
          />

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-700 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-navy-700 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-semibold text-slate-900">
                Joint Lien Signatory: {profile.jointAccountDetails || 'Joint Account with Regional Officer, AICTE Northern Region'}
              </p>
              <p className="text-2xs text-slate-500 leading-relaxed">
                All Fixed Deposit Receipts submitted under this profile must carry a verified lien endorsement in the joint names of the Institution and the designated AICTE Regional Officer.
              </p>
            </div>
          </div>
        </Card>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-1">
          <Button
            type="button"
            variant="secondary"
            icon={RotateCcw}
            onClick={handleResetInstitution}
            disabled={!isDirty || isSubmitting}
          >
            Discard Changes
          </Button>

          <Button
            type="submit"
            variant="primary"
            icon={Save}
            loading={isSubmitting}
          >
            Save Profile Updates
          </Button>
        </div>
      </form>

      {/* Audit Trail & Regulatory Activity History */}
      <Card className="p-4 sm:p-6">
        <CardHeader
          title="Audit Trail & Regulatory History"
          subtitle="Immutable transaction events and administrative actions recorded under this account"
          icon={ShieldCheck}
        />

        {auditLoading ? (
          <div className="py-8 flex items-center justify-center gap-2 text-slate-500 text-xs">
            <Loader2 className="w-4 h-4 animate-spin text-navy-700" />
            <span>Loading security audit records...</span>
          </div>
        ) : auditLogs.length === 0 ? (
          <p className="text-slate-400 italic py-6 text-center text-xs">
            No recent audit trail entries logged.
          </p>
        ) : (
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-2xs uppercase text-slate-500 font-semibold bg-slate-50/70">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Actor</th>
                  <th className="py-2.5 px-3">Action Event</th>
                  <th className="py-2.5 px-3">Target Entity</th>
                  <th className="py-2.5 px-3">Audit Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80">
                    <td className="py-2.5 px-3 whitespace-nowrap text-slate-500 tabular-nums text-2xs">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-900">
                      {log.user_name || log.user_email || `User #${log.user_id || 'System'}`}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="font-mono px-2 py-0.5 rounded text-[11px] bg-slate-100 text-slate-800 font-semibold border border-slate-200">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap font-mono text-slate-600 text-2xs">
                      {log.target_type ? `${log.target_type} #${log.target_id || ''}` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      {log.details || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

export default ProfilePage
