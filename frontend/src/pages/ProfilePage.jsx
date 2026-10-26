import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Building2,
  UserCheck,
  Mail,
  Phone,
  MapPin,
  Save,
  RotateCcw,
  ShieldCheck,
  Info,
} from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { profileSchema } from '../schemas/profileSchema'
import { formatDate } from '../utils/dateUtils'
import { useApp } from '../context/AppContext'

export function ProfilePage() {
  const { profile, updateProfile } = useApp()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      collegeName: profile.collegeName,
      adminName: profile.adminName,
      designation: profile.designation,
      email: profile.email,
      alternateEmail: profile.alternateEmail || '',
      contactNumber: profile.contactNumber,
      address: profile.address,
      city: profile.city,
      state: profile.state,
      pincode: profile.pincode,
    },
  })

  const onSubmit = (data) => {
    setIsSubmitting(true)
    setTimeout(() => {
      updateProfile(data)
      setIsSubmitting(false)
    }, 500)
  }

  const handleReset = () => {
    reset({
      collegeName: profile.collegeName,
      adminName: profile.adminName,
      designation: profile.designation,
      email: profile.email,
      alternateEmail: profile.alternateEmail || '',
      contactNumber: profile.contactNumber,
      address: profile.address,
      city: profile.city,
      state: profile.state,
      pincode: profile.pincode,
    })
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
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
      <Card className="bg-gradient-to-r from-[#142B4A] to-[#1E3A5F] text-white p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-amber-500 text-slate-950 flex items-center justify-center font-bold text-lg shrink-0">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold leading-tight">{profile.collegeName}</h3>
              <p className="text-xs text-slate-300 font-mono mt-1">
                Permanent AICTE ID: {profile.aictePermanentId} • Session {profile.approvalYear}
              </p>
              <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-2xs font-semibold border border-emerald-400/30">
                <ShieldCheck className="w-3 h-3 text-emerald-400" />
                <span>AICTE Approved Technical Institution</span>
              </div>
            </div>
          </div>

          <div className="text-right sm:border-l sm:border-white/10 sm:pl-6 text-2xs text-slate-300">
            <span>Last Updated:</span>
            <p className="font-mono text-white text-xs mt-0.5">{formatDate(profile.lastUpdated)}</p>
          </div>
        </div>
      </Card>

      {/* Editable Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Institution Details */}
        <Card>
          <CardHeader
            title="Institutional Information"
            subtitle="Official institutional title and regulatory identifiers"
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
              value={profile.aictePermanentId}
              disabled
              helperText="Assigned by AICTE Central Approval Bureau"
            />

            <Input
              label="Current Approval Academic Year"
              value={profile.approvalYear}
              disabled
              helperText="Managed via annual Extension of Approval (EoA)"
            />
          </div>
        </Card>

        {/* Administrator Details */}
        <Card>
          <CardHeader
            title="Authorized College Administrator"
            subtitle="Primary contact officer authorized for FDR joint operations"
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
        <Card>
          <CardHeader
            title="Campus Postal Address"
            subtitle="Campus location for formal regulatory correspondence"
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
        <Card>
          <CardHeader
            title="Joint Account Endorsement"
            subtitle="Statutory joint signatory mapping"
          />

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-700 flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-slate-900">
                Joint Lien Mapping: {profile.jointAccountDetails}
              </p>
              <p className="text-slate-500 leading-relaxed">
                All Fixed Deposit Receipts submitted under this profile must carry a verified lien endorsement in the joint names of the Institution and the designated AICTE Regional Officer.
              </p>
            </div>
          </div>
        </Card>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-2">
          <Button
            type="button"
            variant="secondary"
            icon={RotateCcw}
            onClick={handleReset}
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
    </div>
  )
}
