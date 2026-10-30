import React, { useState, useRef, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  UploadCloud,
  FileCheck2,
  Bell,
  Calendar,
  Building2,
  LogOut,
  ShieldCheck,
  X,
  UserCheck,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  ExternalLink,
} from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { cn } from '../../utils/cn'

export function Sidebar({
  isOpen,
  onClose,
  onOpenLogout,
  isCollapsed = false,
  onToggleCollapse,
}) {
  const { unreadCount, profile, currentUser } = useApp()
  const [menuDropdownOpen, setMenuDropdownOpen] = useState(false)
  const menuDropdownRef = useRef(null)

  const isAdmin = currentUser?.role === 'ADMIN' || currentUser?.role_category === 'ADMIN'
  const isOfficer = currentUser?.role === 'AICTE_OFFICER' || currentUser?.role_category === 'AICTE_OFFICER'
  const isOfficerOrAdmin = isAdmin || isOfficer

  // Close three-dot menu on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuDropdownRef.current && !menuDropdownRef.current.contains(event.target)) {
        setMenuDropdownOpen(false)
      }
    }
    if (menuDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menuDropdownOpen])

  const navItems = [
    {
      to: '/',
      label: isAdmin ? 'Admin Oversight' : isOfficer ? 'Scrutiny Workbench' : 'Dashboard',
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
      label: isOfficerOrAdmin ? 'Petitions & Actions' : 'Renewal & Release Petitions',
      icon: FileCheck2,
    },
    {
      to: '/calendar',
      label: 'Compliance Calendar',
      icon: Calendar,
    },
    {
      to: '/notifications',
      label: 'Notifications',
      icon: Bell,
      badge: unreadCount > 0 ? unreadCount : null,
    },
    {
      to: '/profile',
      label: isAdmin ? 'Admin Profile' : isOfficer ? 'Officer Profile' : 'Profile & Settings',
      icon: isOfficerOrAdmin ? UserCheck : Building2,
    },
  ]

  const renderContent = (isMobile = false) => {
    const collapsed = !isMobile && isCollapsed

    return (
      <div className="flex flex-col h-full bg-[#0B1B3D] text-slate-200 select-none border-r border-[#1E3A63]/60">
        {/* Brand Header */}
        <div className={cn(
          'flex items-center justify-between border-b border-white/10 transition-all',
          collapsed ? 'px-3 py-4' : 'px-5 py-4'
        )}>
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center text-[#0B1B3D] shadow-sm font-bold shrink-0">
              <ShieldCheck className="w-5 h-5 text-[#0B1B3D]" />
            </div>

            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-white text-sm tracking-tight truncate">AICTE FDR</span>
                  <span className="text-[10px] bg-amber-400/20 text-amber-300 font-bold px-1.5 py-0.2 rounded border border-amber-400/30">
                    GOV
                  </span>
                </div>
                <span className="text-[11px] text-slate-400 truncate">
                  {isOfficerOrAdmin ? 'Scrutiny Cell' : (profile.aictePermanentId || 'Institutional Portal')}
                </span>
              </div>
            )}
          </div>

          {/* Three-Dot Menu (Desktop) / Close Button (Mobile) */}
          {isMobile ? (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
              aria-label="Close mobile navigation"
            >
              <X className="w-5 h-5" />
            </button>
          ) : (
            <div className="relative" ref={menuDropdownRef}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setMenuDropdownOpen((prev) => !prev)
                }}
                className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-colors focus:outline-none focus:ring-1 focus:ring-white/30"
                aria-label="Sidebar options menu"
                title="Sidebar options"
              >
                <MoreVertical className="w-4 h-4" />
              </button>

              {/* Three-dot dropdown menu */}
              {menuDropdownOpen && (
                <div className="absolute right-0 top-full mt-1.5 w-48 rounded-lg bg-[#142B4A] border border-white/15 shadow-dropdown py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onToggleCollapse && onToggleCollapse()
                      setMenuDropdownOpen(false)
                    }}
                    className="flex items-center gap-2.5 w-full px-3.5 py-2 text-xs font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors text-left"
                  >
                    {isCollapsed ? (
                      <>
                        <ChevronRight className="w-4 h-4 text-amber-400" />
                        <span>Expand Sidebar</span>
                      </>
                    ) : (
                      <>
                        <ChevronLeft className="w-4 h-4 text-amber-400" />
                        <span>Collapse Sidebar</span>
                      </>
                    )}
                  </button>

                  <div className="my-1 border-t border-white/10" />

                  <a
                    href="https://www.aicte-india.org"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between w-full px-3.5 py-2 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
                    onClick={() => setMenuDropdownOpen(false)}
                  >
                    <span>AICTE Official Portal</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                  </a>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Role & Affiliation Banner (Expanded only) */}
        {!collapsed && (
          <div className="px-4 py-2.5 bg-[#071228]/80 border-b border-white/5 text-xs">
            <p className="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">
              {isOfficerOrAdmin ? 'Authorized Official' : 'Affiliated Institution'}
            </p>
            <p
              className="text-white font-medium text-xs truncate mt-0.5"
              title={isOfficerOrAdmin ? (currentUser?.full_name || 'AICTE Officer') : profile.collegeName}
            >
              {isOfficerOrAdmin ? (currentUser?.full_name || 'AICTE Scrutiny Officer') : profile.collegeName}
            </p>
          </div>
        )}

        {/* Navigation Items */}
        <div className={cn(
          'flex-1 py-3 overflow-y-auto space-y-1',
          collapsed ? 'px-2' : 'px-3'
        )}>
          {!collapsed && (
            <div className="px-3 pb-1.5 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
              Navigation
            </div>
          )}

          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => isMobile && onClose && onClose()}
                className={({ isActive }) =>
                  cn(
                    'relative group flex items-center rounded-lg text-xs font-medium transition-all',
                    collapsed ? 'justify-center p-2.5' : 'justify-between px-3 py-2.5',
                    isActive
                      ? 'bg-white/15 text-white font-semibold shadow-xs border-l-2 border-amber-400'
                      : 'text-slate-300 hover:text-white hover:bg-white/10'
                  )
                }
              >
                <div className={cn('flex items-center gap-3', collapsed && 'justify-center')}>
                  <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105 text-slate-300 group-hover:text-white" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </div>

                {!collapsed && item.badge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500 text-slate-950 shrink-0">
                    {item.badge}
                  </span>
                )}

                {/* Collapsed Badge indicator */}
                {collapsed && item.badge && (
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-400 ring-2 ring-[#0B1B3D]" />
                )}

                {/* Floating Tooltip when Collapsed */}
                {collapsed && (
                  <div className="absolute left-full ml-3 px-2.5 py-1.5 bg-[#071228] text-white text-xs font-medium rounded-md shadow-dropdown whitespace-nowrap z-50 pointer-events-none opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 border border-white/15">
                    <div className="flex items-center gap-1.5">
                      <span>{item.label}</span>
                      {item.badge && (
                        <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500 text-slate-950">
                          {item.badge}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </NavLink>
            )
          })}
        </div>

        {/* Footer Actions */}
        <div className={cn(
          'border-t border-white/10 transition-all',
          collapsed ? 'p-2 space-y-2' : 'p-3 space-y-2'
        )}>
          {/* Quick collapse/expand button in footer for ease of access */}
          {!isMobile && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className={cn(
                'flex items-center gap-2.5 w-full rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors',
                collapsed ? 'justify-center p-2' : 'px-3 py-2'
              )}
              title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            >
              {collapsed ? (
                <ChevronRight className="w-4 h-4 text-amber-400" />
              ) : (
                <>
                  <ChevronLeft className="w-4 h-4 text-amber-400" />
                  <span className="text-[11px]">Collapse Menu</span>
                </>
              )}
            </button>
          )}

          <button
            onClick={onOpenLogout}
            className={cn(
              'group relative flex items-center rounded-lg text-xs font-medium text-rose-300 hover:text-rose-100 hover:bg-rose-500/20 transition-colors w-full',
              collapsed ? 'justify-center p-2' : 'gap-2.5 px-3 py-2'
            )}
            title="Sign Out"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {!collapsed && <span>Sign Out</span>}

            {collapsed && (
              <div className="absolute left-full ml-3 px-2.5 py-1.5 bg-[#071228] text-rose-300 text-xs font-medium rounded-md shadow-dropdown whitespace-nowrap z-50 pointer-events-none opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 border border-white/15">
                Sign Out
              </div>
            )}
          </button>

          {!collapsed && (
            <div className="px-3 pt-1 text-[10px] text-slate-500 flex items-center justify-between border-t border-white/5">
              <span>Gov of India / AICTE</span>
              <span className="font-mono text-slate-400">v2.5-REG</span>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className={cn(
        'hidden md:flex md:flex-col md:fixed md:inset-y-0 z-30 shadow-elevated transition-all duration-200 ease-in-out',
        isCollapsed ? 'md:w-20' : 'md:w-64'
      )}>
        {renderContent(false)}
      </aside>

      {/* Mobile Drawer */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity duration-200"
            onClick={onClose}
          />
          <div className="fixed inset-y-0 left-0 w-72 max-w-[85vw] bg-[#0B1B3D] shadow-2xl z-10 animate-in slide-in-from-left duration-200 h-full">
            {renderContent(true)}
          </div>
        </div>
      )}
    </>
  )
}

export default Sidebar
