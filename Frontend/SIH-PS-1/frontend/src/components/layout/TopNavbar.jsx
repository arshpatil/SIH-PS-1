import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Menu,
  Bell,
  User,
  ChevronDown,
  LogOut,
  Building,
  Shield,
  ExternalLink,
} from 'lucide-react'
import { useApp } from '../../context/AppContext'

export function TopNavbar({ onOpenMobileSidebar, onOpenLogout }) {
  const { profile, currentUser, unreadCount } = useApp()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const location = useLocation()

  const userName = currentUser?.full_name || currentUser?.name || 'Administrator'
  const userRole = currentUser?.role || currentUser?.role_category || 'INSTITUTION'
  const userEmail = currentUser?.email || 'admin@portal.gov.in'
  const initials =
    userName
      .split(' ')
      .filter(Boolean)
      .map((n) => n[0])
      .slice(0, 2)
      .join('')
      .toUpperCase() || 'U'

  const isOfficerOrAdmin =
    userRole === 'AICTE_OFFICER' ||
    userRole === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

  // Derive page title from pathname
  const getPageTitle = (pathname) => {
    if (pathname === '/') {
      if (userRole === 'ADMIN') return 'AICTE Central Administration'
      if (userRole === 'AICTE_OFFICER') return 'Scrutiny Officer Workbench'
      return 'Institution Overview'
    }
    if (pathname.startsWith('/fdrs/')) return 'FDR Record Details & Workflow'
    if (pathname === '/fdrs') return isOfficerOrAdmin ? 'AICTE FDR Scrutiny Repository' : 'Fixed Deposit Receipts'
    if (pathname === '/upload') return 'Register New FDR'
    if (pathname === '/requests') return 'Renewal & Release Petitions'
    if (pathname === '/calendar') return 'FDR Maturity & Renewal Calendar'
    if (pathname === '/notifications') return 'System Notifications'
    if (pathname === '/profile') return userRole === 'ADMIN' ? 'Administrator Profile' : isOfficerOrAdmin ? 'Officer Profile' : 'Institutional Profile & Settings'
    return 'Portal Dashboard'
  }

  const getBreadcrumb = (pathname) => {
    if (pathname === '/') return 'Dashboard'
    if (pathname.startsWith('/fdrs/')) return 'Dashboard / FDRs / Details'
    if (pathname === '/fdrs') return 'Dashboard / FDRs'
    if (pathname === '/upload') return 'Dashboard / Upload New FDR'
    if (pathname === '/requests') return 'Dashboard / Requests'
    if (pathname === '/calendar') return 'Dashboard / Calendar'
    if (pathname === '/notifications') return 'Dashboard / Notifications'
    if (pathname === '/profile') return 'Dashboard / Profile'
    return 'Dashboard'
  }

  return (
    <header className="sticky top-0 z-20 bg-white border-b border-slate-200/80 shadow-2xs">
      <div className="flex items-center justify-between px-3 sm:px-6 lg:px-8 h-16 min-w-0">
        {/* Left Side: Mobile Menu Button & Breadcrumb */}
        <div className="flex items-center gap-2.5 sm:gap-4 min-w-0 flex-1 mr-2">
          <button
            type="button"
            onClick={onOpenMobileSidebar}
            className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none shrink-0"
            aria-label="Open sidebar menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="min-w-0">
            <p className="text-2xs font-semibold text-slate-500 tracking-wide uppercase hidden sm:block truncate">
              {getBreadcrumb(location.pathname)}
            </p>
            <h1 className="text-base sm:text-lg font-bold text-slate-900 leading-tight truncate">
              {getPageTitle(location.pathname)}
            </h1>
          </div>
        </div>

        {/* Right Side: Institution Badge, Notifications, User Menu */}
        <div className="flex items-center gap-2 sm:gap-3 lg:gap-4 shrink-0">
          {/* Bank Integration Prototype Indicator */}
          <div
            className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-full text-[10px] sm:text-2xs font-bold uppercase bg-amber-50 text-amber-800 border border-amber-300 tracking-wider shadow-2xs whitespace-nowrap shrink-0"
            title="Prototype Integration: Core banking verification runs on synthetic mock data. No real bank network connected."
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" />
            <span className="hidden sm:inline">Bank Demo Mode</span>
            <span className="inline sm:hidden">Demo</span>
          </div>

          {/* Institutional / Bureau Badge - Desktop only */}
          <div
            className="hidden md:flex items-center gap-2 px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs max-w-[200px] xl:max-w-[280px]"
            title={isOfficerOrAdmin ? 'AICTE Clearance Bureau' : `${profile.collegeName} (${profile.aictePermanentId})`}
          >
            <Building className="w-3.5 h-3.5 text-[#142B4A] shrink-0" />
            <span className="font-semibold text-slate-700 truncate">
              {isOfficerOrAdmin ? 'AICTE Clearance Bureau' : profile.collegeName}
            </span>
            <span className="text-slate-400 shrink-0">|</span>
            <span className="text-slate-500 font-mono text-[11px] shrink-0">
              {isOfficerOrAdmin ? 'OFFICER DESK' : profile.aictePermanentId}
            </span>
          </div>

          {/* Notifications Link */}
          <Link
            to="/notifications"
            className="relative p-2 rounded-lg text-slate-600 hover:text-[#142B4A] hover:bg-slate-100 transition-colors shrink-0"
            title="Notifications"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white shadow-xs">
                {unreadCount}
              </span>
            )}
          </Link>

          {/* User Profile Dropdown */}
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 p-1 sm:p-1.5 rounded-lg hover:bg-slate-100 transition-colors focus:outline-none text-left"
            >
              <div className="w-8 h-8 rounded-full bg-[#142B4A] text-white flex items-center justify-center font-semibold text-xs shadow-xs shrink-0">
                {initials}
              </div>
              <div className="hidden sm:block min-w-0">
                <p className="text-xs font-semibold text-slate-800 leading-none truncate max-w-[120px] lg:max-w-[150px]">
                  {userName}
                </p>
                <p className="text-[11px] text-slate-500 leading-none mt-1 truncate">
                  {userRole}
                </p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden sm:block shrink-0" />
            </button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-dropdown border border-slate-200 py-1.5 z-40 text-sm animate-in fade-in slide-in-from-top-2">
                  <div className="px-4 py-2.5 border-b border-slate-100">
                    <p className="text-xs font-bold text-slate-900">{userName}</p>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{userEmail}</p>
                    <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded text-[11px] font-medium text-amber-800">
                      <Shield className="w-3 h-3 text-amber-600" />
                      <span>{userRole}</span>
                    </div>
                  </div>

                  <div className="py-1">
                    <Link
                      to="/profile"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-[#142B4A]"
                    >
                      <User className="w-4 h-4 text-slate-400" />
                      Profile & Account
                    </Link>
                    <Link
                      to="/requests"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-[#142B4A]"
                    >
                      <ExternalLink className="w-4 h-4 text-slate-400" />
                      Petitions & Actions
                    </Link>
                  </div>

                  <div className="pt-1 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => {
                        setDropdownOpen(false)
                        onOpenLogout()
                      }}
                      className="flex items-center gap-2.5 w-full px-4 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50"
                    >
                      <LogOut className="w-4 h-4" />
                      Sign Out
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

export default TopNavbar
