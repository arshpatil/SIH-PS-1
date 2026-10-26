import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  UploadCloud,
  FileCheck2,
  Bell,
  Building2,
  LogOut,
  ShieldCheck,
  X,
  UserCheck,
} from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { cn } from '../../utils/cn'

export function Sidebar({ isOpen, onClose, onOpenLogout }) {
  const { unreadCount, profile, currentUser } = useApp()

  const isOfficerOrAdmin =
    currentUser?.role === 'AICTE_OFFICER' ||
    currentUser?.role === 'ADMIN' ||
    currentUser?.role_category === 'AICTE_OFFICER' ||
    currentUser?.role_category === 'ADMIN'

  const navItems = [
    {
      to: '/',
      label: isOfficerOrAdmin ? 'Overview & Metrics' : 'Dashboard',
      icon: LayoutDashboard,
      end: true,
    },
    {
      to: '/fdrs',
      label: isOfficerOrAdmin ? 'Scrutiny Repository' : 'My FDRs',
      icon: FileText,
    },
    ...(!isOfficerOrAdmin
      ? [
          {
            to: '/upload',
            label: 'Upload New FDR',
            icon: UploadCloud,
          },
        ]
      : []),
    {
      to: '/requests',
      label: isOfficerOrAdmin ? 'Petitions & Actions' : 'Renewal / Release Requests',
      icon: FileCheck2,
    },
    {
      to: '/notifications',
      label: 'Notifications',
      icon: Bell,
      badge: unreadCount > 0 ? unreadCount : null,
    },
    {
      to: '/profile',
      label: isOfficerOrAdmin ? 'Officer Profile' : 'Profile & Settings',
      icon: isOfficerOrAdmin ? UserCheck : Building2,
    },
  ]

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#142B4A] text-slate-200 select-none">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-6 py-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center text-[#142B4A] shadow-md font-bold text-lg shrink-0">
            <ShieldCheck className="w-6 h-6 text-[#142B4A]" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-white text-base tracking-tight">FDR Portal</span>
              <span className="text-[10px] bg-amber-400/20 text-amber-300 font-semibold px-1.5 py-0.5 rounded border border-amber-400/30">
                AICTE
              </span>
            </div>
            <span className="text-2xs text-slate-400 truncate max-w-[140px]">
              {isOfficerOrAdmin ? 'Scrutiny Bureau' : (profile.aictePermanentId || 'College Portal')}
            </span>
          </div>
        </div>

        {/* Close Button on Mobile */}
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Role / Institution Strip */}
      <div className="px-6 py-3 bg-[#0E1E34]/80 border-b border-white/5 text-xs">
        <p className="text-slate-400 text-2xs uppercase tracking-wider font-semibold">
          {isOfficerOrAdmin ? 'Officer Clearance Desk' : 'Affiliated Institution'}
        </p>
        <p
          className="text-white font-medium truncate mt-0.5"
          title={isOfficerOrAdmin ? (currentUser?.full_name || 'AICTE Officer') : profile.collegeName}
        >
          {isOfficerOrAdmin ? (currentUser?.full_name || 'AICTE Officer') : profile.collegeName}
        </p>
      </div>

      {/* Navigation List */}
      <div className="flex-1 py-4 px-3 overflow-y-auto space-y-1">
        <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Menu
        </div>
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => onClose && onClose()}
              className={({ isActive }) =>
                cn(
                  'flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all group',
                  isActive
                    ? 'bg-white/15 text-white font-semibold shadow-xs'
                    : 'text-slate-300 hover:text-white hover:bg-white/10'
                )
              }
            >
              <div className="flex items-center gap-3">
                <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-amber-500 text-slate-950">
                  {item.badge}
                </span>
              )}
            </NavLink>
          )
        })}
      </div>

      {/* Footer / Logout */}
      <div className="p-4 border-t border-white/10 space-y-2">
        <button
          onClick={onOpenLogout}
          className="flex items-center gap-3 w-full px-3.5 py-2.5 rounded-lg text-sm font-medium text-rose-300 hover:text-rose-100 hover:bg-rose-500/20 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out</span>
        </button>
        <div className="px-3 pt-2 text-2xs text-slate-400 flex items-center justify-between">
          <span>AICTE Security Deposit</span>
          <span>v2.4-SIH</span>
        </div>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-30 shadow-xl border-r border-slate-800">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={onClose}
          />
          <div className="fixed inset-y-0 left-0 w-72 max-w-full bg-[#142B4A] shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  )
}

export default Sidebar
