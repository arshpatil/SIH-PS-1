import React from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { LogOut, AlertTriangle } from 'lucide-react'

export function LogoutModal({ isOpen, onClose, onConfirm }) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Exit Demonstration Session"
      subtitle="FDR Management System — College Portal"
      maxWidth="max-w-md"
    >
      <div className="space-y-4">
        <div className="flex items-center gap-3 p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-xs">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
          <span>
            This is a frontend demonstration session. Logging out will return you to the college login screen.
          </span>
        </div>

        <p className="text-sm text-slate-600">
          Are you sure you want to sign out of the college administrator portal?
        </p>

        <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
          <Button variant="secondary" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="md"
            icon={LogOut}
            onClick={() => {
              onConfirm()
              onClose()
            }}
          >
            Sign Out
          </Button>
        </div>
      </div>
    </Modal>
  )
}
