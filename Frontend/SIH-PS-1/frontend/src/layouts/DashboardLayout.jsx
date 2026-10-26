import React, { useState } from 'react'
import { Outlet, Navigate } from 'react-router-dom'
import { Sidebar } from '../components/layout/Sidebar'
import { TopNavbar } from '../components/layout/TopNavbar'
import { LogoutModal } from '../components/layout/LogoutModal'
import { ToastContainer } from '../components/ui/Toast'
import { useAuth } from '../hooks/useAuth'

export function DashboardLayout() {
  const { isAuthenticated, authLoading, logout } = useAuth()
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [logoutModalOpen, setLogoutModalOpen] = useState(false)

  // Wait for initial session verification to complete
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#F4F7FB] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-[#142B4A] border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-500 font-medium">Verifying institutional session...</p>
        </div>
      </div>
    )
  }

  // Redirect to demo login if logged out
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="min-h-screen bg-[#F4F7FB] flex">
      {/* Sidebar */}
      <Sidebar
        isOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
        onOpenLogout={() => setLogoutModalOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col md:pl-64 min-w-0">
        <TopNavbar
          onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
          onOpenLogout={() => setLogoutModalOpen(true)}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>

        {/* Institutional Footer */}
        <footer className="py-4 px-6 text-center text-xs text-slate-600 border-t border-slate-200/80 bg-white">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>
              All India Council for Technical Education (AICTE) — Fixed Deposit Receipt Management System
            </span>
            <span className="font-medium text-slate-600">
              Technical Institutions Security Deposit Monitoring Cell
            </span>
          </div>
        </footer>
      </div>

      {/* Modals & Overlays */}
      <LogoutModal
        isOpen={logoutModalOpen}
        onClose={() => setLogoutModalOpen(false)}
        onConfirm={logout}
      />
      <ToastContainer />
    </div>
  )
}
