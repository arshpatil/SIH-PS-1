import React, { useState } from 'react'
import { Outlet, Navigate } from 'react-router-dom'
import { Sidebar } from '../components/layout/Sidebar'
import { TopNavbar } from '../components/layout/TopNavbar'
import { LogoutModal } from '../components/layout/LogoutModal'
import { ToastContainer } from '../components/ui/Toast'
import { useAuth } from '../hooks/useAuth'

export function DashboardLayout() {
  const { isAuthenticated, logout } = useAuth()
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [logoutModalOpen, setLogoutModalOpen] = useState(false)

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
