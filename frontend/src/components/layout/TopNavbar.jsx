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

  // Derive page title from pathname
  const getPageTitle = (pathname) => {
    if (pathname === '/') return 'Institution Overview'
    if (pathname.startsWith('/fdrs/')) return 'FDR Record Details'
    if (pathname === '/fdrs') return 'Fixed Deposit Receipts'
    if (pathname === '/upload') return 'Register New FDR'
    if (pathname === '/requests') return 'Renewal & Release Petitions'
    if (pathname === '/notifications') return 'System Notifications'
    if (pathname === '/profile') return 'Institutional Profile & Settings'
    return 'College Dashboard'
  }

  const getBreadcrumb = (pathname) => {
    if (pathname === '/') return 'Dashboard'
    if (pathname.startsWith('/fdrs/')) return 'Dashboard / My FDRs / Details'
    if (pathname === '/fdrs') return 'Dashboard / My FDRs'
    if (pathname === '/upload') return 'Dashboard / Upload New FDR'
    if (pathname === '/requests') return 'Dashboard / Requests'
    if (pathname === '/notifications') return 'Dashboard / Notifications'
    if (pathname === '/profile') return 'Dashboard / Profile'
    return 'Dashboard'
  }

  return (
    <header className="sticky top-0 z-20 bg-white border-b border-slate-200/80 shadow-2xs">
      <div className="flex items-center justify-between px-4 sm:px-6 lg:px-8 h-16">
        {/* Left Side: Mobile Menu Button & Breadcrumb */}
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onOpenMobileSidebar}
            className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none"
            aria-label="Open sidebar menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div>
            <p className="text-2xs font-semibold text-slate-600 tracking-wide uppercase hidden sm:block">
              {getBreadcrumb(location.pathname)}
            </p>
            <h1 className="text-lg font-bold text-slate-900 leading-tight">
              {getPageTitle(location.pathname)}
            </h1>
          </div>
        </div>

        {/* Right Side: Institution Badge, Notifications, User Menu */}
        <div className="flex items-center gap-3 sm:gap-4">
          {/* Institutional Badge - Desktop only */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs">
            <Building className="w-3.5 h-3.5 text-[#142B4A]" />
            <span className="font-semibold text-slate-700 truncate max-w-[200px]" title={profile.collegeName}>
              {profile.collegeName}
            </span>
            <span className="text-slate-400">|</span>
            <span className="text-slate-500 font-mono text-[11px]">{profile.aictePermanentId}</span>
          </div>

          {/* Notifications Link */}
          <Link
            to="/notifications"
            className="relative p-2 rounded-lg text-slate-600 hover:text-[#142B4A] hover:bg-slate-100 transition-colors"
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
          <div className="relative">
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-slate-100 transition-colors focus:outline-none text-left"
            >
              <div className="w-8 h-8 rounded-full bg-[#142B4A] text-white flex items-center justify-center font-semibold text-xs shadow-xs">
                {currentUser.name
                  .split(' ')
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join('')}
              </div>
              <div className="hidden sm:block">
                <p className="text-xs font-semibold text-slate-800 leading-none truncate max-w-[140px]">
                  {currentUser.name}
                </p>
                <p className="text-[11px] text-slate-500 leading-none mt-1">
                  {currentUser.role}
                </p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden sm:block" />
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
                    <p className="text-xs font-bold text-slate-900">{currentUser.name}</p>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{currentUser.email}</p>
                    <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 bg-amber-50 border border-amber-200 rounded text-[11px] font-medium text-amber-800">
                      <Shield className="w-3 h-3 text-amber-600" />
                      <span>Authorized Admin</span>
                    </div>
                  </div>

                  <div className="py-1">
                    <Link
                      to="/profile"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-[#142B4A]"
                    >
                      <User className="w-4 h-4 text-slate-400" />
                      Profile & College Details
                    </Link>
                    <Link
                      to="/requests"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-[#142B4A]"
                    >
                      <ExternalLink className="w-4 h-4 text-slate-400" />
                      Pending Requests ({profile.approvalYear})
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
