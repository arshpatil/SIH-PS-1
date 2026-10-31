import React, { useState, useRef, useEffect } from 'react'
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
  ChevronRight,
  Landmark,
} from 'lucide-react'
import { useApp } from '../../context/AppContext'

export function TopNavbar({ onOpenMobileSidebar, onOpenLogout }) {
  const { profile, currentUser, unreadCount } = useApp()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)
  const location = useLocation()

  const userName = currentUser?.full_name || currentUser?.name || 'Authorized User'
  const userRole = currentUser?.role || currentUser?.role_category || 'INSTITUTION'
  const userEmail = currentUser?.email || 'portal@aicte.gov.in'
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

  // Close profile dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false)
      }
    }
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [dropdownOpen])

  // Derive page title from pathname
  const getPageTitle = (pathname) => {
    if (pathname === '/') {
      if (userRole === 'ADMIN') return 'Central Administration & Oversight'
      if (userRole === 'AICTE_OFFICER') return 'Scrutiny Officer Workbench'
      return 'Institutional Deposit Dashboard'
    }
    if (pathname.startsWith('/fdrs/')) return 'Fixed Deposit Receipt Record & Scrutiny'
    if (pathname === '/fdrs') return isOfficerOrAdmin ? 'AICTE FDR Scrutiny Repository' : 'Fixed Deposit Receipts (FDRs)'
    if (pathname === '/upload') return 'Register & Deposit New FDR'
    if (pathname === '/requests') return 'Renewal & Release Petitions'
    if (pathname === '/calendar') return 'Compliance & Maturity Calendar'
    if (pathname === '/notifications') return 'Official Notices & System Alerts'
    if (pathname === '/profile') return userRole === 'ADMIN' ? 'Administrator Profile' : isOfficerOrAdmin ? 'Officer Profile' : 'Institution Profile & Settings'
    return 'Regulatory Portal'
  }

  const getBreadcrumbs = (pathname) => {
    if (pathname === '/') return [{ label: 'Portal', path: '/' }, { label: 'Dashboard' }]
    if (pathname.startsWith('/fdrs/')) return [{ label: 'Portal', path: '/' }, { label: 'FDRs', path: '/fdrs' }, { label: 'Record Scrutiny' }]
    if (pathname === '/fdrs') return [{ label: 'Portal', path: '/' }, { label: 'FDR Repository' }]
    if (pathname === '/upload') return [{ label: 'Portal', path: '/' }, { label: 'Deposit Registration' }]
    if (pathname === '/requests') return [{ label: 'Portal', path: '/' }, { label: 'Petitions & Scrutiny' }]
    if (pathname === '/calendar') return [{ label: 'Portal', path: '/' }, { label: 'Compliance Calendar' }]
    if (pathname === '/notifications') return [{ label: 'Portal', path: '/' }, { label: 'Notifications' }]
    if (pathname === '/profile') return [{ label: 'Portal', path: '/' }, { label: 'Profile' }]
    return [{ label: 'Portal', path: '/' }, { label: 'Overview' }]
  }

  const breadcrumbs = getBreadcrumbs(location.pathname)

  return (
    <header className="sticky top-0 z-20 bg-white border-b border-slate-200/90 shadow-2xs">
      {/* Official Government of India & AICTE Top Strip */}
      <div className="bg-[#0B1B3D] text-slate-300 px-3 sm:px-6 lg:px-8 py-1 text-[10px] sm:text-[11px] font-medium border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2 truncate">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            <span className="text-white font-semibold tracking-wide">भारत सरकार</span>
            <span className="text-slate-400">|</span>
            <span className="hidden sm:inline text-slate-200">Government of India</span>
          </div>
          <span className="text-slate-500 hidden md:inline">•</span>
          <span className="hidden md:inline text-slate-300 truncate">
            अखिल भारतीय तकनीकी शिक्षा परिषद (AICTE)
          </span>
        </div>

        <div className="flex items-center gap-3 shrink-0 text-[10px]">
          <span className="text-amber-300 font-medium hidden sm:inline">Regulatory Compliance System</span>
          <span className="px-1.5 py-0.2 rounded bg-white/10 text-slate-200 font-mono">
            SEC-DEPOSIT-V2
          </span>
        </div>
      </div>

      {/* Main Navigation Bar */}
      <div className="flex items-center justify-between px-3 sm:px-6 lg:px-8 h-15 min-w-0">
        {/* Left Side: Mobile Menu Button & Breadcrumb */}
        <div className="flex items-center gap-2 sm:gap-3.5 min-w-0 flex-1 mr-2">
          <button
            type="button"
            onClick={onOpenMobileSidebar}
            className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none shrink-0"
            aria-label="Open sidebar menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="min-w-0">
            {/* Breadcrumb links */}
            <nav className="flex items-center gap-1 text-[11px] font-semibold text-slate-500 tracking-wide uppercase truncate" aria-label="Breadcrumb">
              {breadcrumbs.map((b, idx) => (
                <React.Fragment key={idx}>
                  {idx > 0 && <ChevronRight className="w-3 h-3 text-slate-400 shrink-0" />}
                  {b.path ? (
                    <Link to={b.path} className="hover:text-navy-700 transition-colors truncate">
                      {b.label}
                    </Link>
                  ) : (
                    <span className="text-slate-700 truncate">{b.label}</span>
                  )}
                </React.Fragment>
              ))}
            </nav>

            <h1 className="text-sm sm:text-base lg:text-lg font-bold text-slate-900 leading-tight truncate">
              {getPageTitle(location.pathname)}
            </h1>
          </div>
        </div>

        {/* Right Side: Institution Badge, Notifications, User Menu */}
        <div className="flex items-center gap-2.5 sm:gap-3.5 shrink-0">
          {/* Institutional / Bureau Badge - Visible on medium screens and up */}
          <div
            className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs max-w-[220px] lg:max-w-[280px] xl:max-w-[360px] shadow-2xs"
            title={isOfficerOrAdmin ? 'AICTE Scrutiny Bureau' : `${profile.collegeName} (${profile.aictePermanentId})`}
          >
            <Building className="w-3.5 h-3.5 text-navy-700 shrink-0" />
            <span className="font-semibold text-slate-800 truncate">
              {isOfficerOrAdmin ? 'AICTE Scrutiny Bureau' : profile.collegeName}
            </span>
            <span className="text-slate-300 shrink-0">|</span>
            <span className="text-slate-600 font-mono text-2xs shrink-0 font-medium">
              {isOfficerOrAdmin ? 'SCRUTINY' : profile.aictePermanentId}
            </span>
          </div>

          {/* Notifications Link */}
          <Link
            to="/notifications"
            className="relative p-2 rounded-lg text-slate-600 hover:text-navy-700 hover:bg-slate-100 transition-colors shrink-0"
            title="View Notifications"
          >
            <Bell className="w-4 h-4 sm:w-5 sm:h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white shadow-xs">
                {unreadCount}
              </span>
            )}
          </Link>

          {/* User Profile Dropdown */}
          <div className="relative shrink-0" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 p-1 sm:p-1.5 rounded-lg hover:bg-slate-100 transition-colors focus:outline-none text-left"
              aria-label="User account menu"
            >
              <div className="w-8 h-8 rounded-full bg-[#142B4A] text-white flex items-center justify-center font-bold text-xs shadow-xs shrink-0 border border-navy-800">
                {initials}
              </div>
              <div className="hidden sm:block min-w-0">
                <p className="text-xs font-bold text-slate-800 leading-none truncate max-w-[120px] lg:max-w-[150px]">
                  {userName}
                </p>
                <p className="text-[10px] text-slate-500 font-medium leading-none mt-1 truncate">
                  {userRole}
                </p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden sm:block shrink-0" />
            </button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-dropdown border border-slate-200 py-1.5 z-40 text-xs animate-in fade-in slide-in-from-top-2 duration-100">
                <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
                  <p className="text-xs font-bold text-slate-900 truncate">{userName}</p>
                  <p className="text-[11px] text-slate-500 truncate mt-0.5">{userEmail}</p>
                  <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 bg-navy-50 border border-navy-200 rounded text-[11px] font-semibold text-navy-800">
                    <Shield className="w-3 h-3 text-navy-700" />
                    <span>{userRole}</span>
                  </div>
                </div>

                <div className="py-1">
                  <Link
                    to="/profile"
                    onClick={() => setDropdownOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-navy-900 transition-colors"
                  >
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    Institutional Account & Profile
                  </Link>
                  <Link
                    to="/requests"
                    onClick={() => setDropdownOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-navy-900 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                    Petitions & Scrutiny Cases
                  </Link>
                </div>

                <div className="pt-1 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => {
                      setDropdownOpen(false)
                      onOpenLogout()
                    }}
                    className="flex items-center gap-2.5 w-full px-4 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign Out of Session
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}

export default TopNavbar
