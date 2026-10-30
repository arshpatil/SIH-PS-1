import React from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { LogOut, AlertCircle } from 'lucide-react'

export function LogoutModal({ isOpen, onClose, onConfirm }) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Sign Out of Session"
      subtitle="AICTE Fixed Deposit Receipt Management Portal"
      maxWidth="max-w-md"
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200 text-slate-700 text-xs">
          <AlertCircle className="w-4 h-4 text-navy-700 shrink-0 mt-0.5" />
          <span className="leading-relaxed">
            Signing out will conclude your current authorized session. Any unsaved form drafts will be discarded.
          </span>
        </div>

        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
          Are you sure you want to end your current portal session and return to the login gateway?
        </p>

        <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Stay Signed In
          </Button>
          <Button
            variant="danger"
            size="sm"
            icon={LogOut}
            onClick={() => {
              onConfirm()
              onClose()
            }}
          >
            Confirm Sign Out
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default LogoutModal
