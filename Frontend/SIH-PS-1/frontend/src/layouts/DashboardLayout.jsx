import React, { useState } from 'react'
import { Outlet, Navigate } from 'react-router-dom'
import { Sidebar } from '../components/layout/Sidebar'
import { TopNavbar } from '../components/layout/TopNavbar'
import { LogoutModal } from '../components/layout/LogoutModal'
import { ToastContainer } from '../components/ui/Toast'
import { useAuth } from '../hooks/useAuth'
import { cn } from '../utils/cn'

export function DashboardLayout() {
  const { isAuthenticated, authLoading, logout } = useAuth()
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [logoutModalOpen, setLogoutModalOpen] = useState(false)

  // Persist sidebar collapsed preference
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('aicte_sidebar_collapsed') === 'true'
    } catch {
      return false
    }
  })

  const toggleSidebarCollapse = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem('aicte_sidebar_collapsed', String(next))
      } catch {}
      return next
    })
  }

  // Wait for initial session verification to complete
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#F4F7FB] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-9 h-9 border-3 border-[#142B4A] border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-600 font-semibold tracking-wide">
            Verifying institutional credentials...
          </p>
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
      {/* Sidebar with 3-dot menu collapse/expand control */}
      <Sidebar
        isOpen={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
        onOpenLogout={() => setLogoutModalOpen(true)}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebarCollapse}
      />

      {/* Main Content Area - dynamically offsets for collapsed (md:pl-20) vs expanded (md:pl-64) */}
      <div className={cn(
        'flex-1 flex flex-col min-w-0 transition-all duration-200 ease-in-out',
        isSidebarCollapsed ? 'md:pl-20' : 'md:pl-64'
      )}>
        <TopNavbar
          onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
          onOpenLogout={() => setLogoutModalOpen(true)}
        />

        <main className="flex-1 p-3.5 sm:p-5 lg:p-7 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>

        {/* Institutional Government Footer */}
        <footer className="py-3.5 px-4 sm:px-6 text-2xs sm:text-xs text-slate-500 border-t border-slate-200/90 bg-white">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
              <span className="font-semibold text-slate-700">
                अखिल भारतीय तकनीकी शिक्षा परिषद (AICTE)
              </span>
              <span className="text-slate-300 hidden sm:inline">•</span>
              <span>All India Council for Technical Education</span>
            </div>
            <div className="flex items-center gap-2 font-medium text-slate-600">
              <span>Security Deposit & FDR Clearance Cell</span>
              <span className="text-slate-300">•</span>
              <span className="text-navy-700 font-semibold">Government of India</span>
            </div>
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

export default DashboardLayout
