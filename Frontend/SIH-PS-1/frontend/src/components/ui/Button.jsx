import React from 'react'
import { cn } from '../../utils/cn'

export function Button({
  children,
  className = '',
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  icon: Icon,
  iconPosition = 'left',
  type = 'button',
  onClick,
  ...props
}) {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-60 disabled:cursor-not-allowed select-none active:scale-[0.99]'

  const variants = {
    primary: 'bg-[#142B4A] hover:bg-[#0E1E34] text-white focus:ring-[#142B4A]/30 shadow-xs border border-[#142B4A]',
    secondary: 'bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 focus:ring-slate-300 shadow-2xs',
    outline: 'bg-transparent hover:bg-slate-50 text-[#142B4A] border border-[#142B4A]/30 focus:ring-[#142B4A]/20',
    ghost: 'bg-transparent hover:bg-slate-100 text-slate-700 focus:ring-slate-200',
    danger: 'bg-rose-600 hover:bg-rose-700 text-white focus:ring-rose-500/30 shadow-xs border border-rose-600',
    success: 'bg-emerald-600 hover:bg-emerald-700 text-white focus:ring-emerald-500/30 shadow-xs border border-emerald-600',
    warning: 'bg-amber-500 hover:bg-amber-600 text-slate-950 font-semibold focus:ring-amber-400/40 shadow-xs border border-amber-500',
  }

  const sizes = {
    xs: 'text-2xs px-2.5 py-1 gap-1 h-7',
    sm: 'text-xs px-3 py-1.5 gap-1.5 h-8',
    md: 'text-xs sm:text-sm px-3.5 py-2 gap-2 h-9 sm:h-10',
    lg: 'text-sm sm:text-base px-5 py-2.5 gap-2.5 h-11',
  }

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={cn(baseStyles, variants[variant] || variants.primary, sizes[size] || sizes.md, className)}
      {...props}
    >
      {loading ? (
        <svg className="animate-spin -ml-0.5 mr-2 h-3.5 w-3.5 text-current shrink-0" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      ) : Icon && iconPosition === 'left' ? (
        <Icon className={cn(size === 'xs' || size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4', 'shrink-0')} />
      ) : null}
      <span>{children}</span>
      {!loading && Icon && iconPosition === 'right' ? (
        <Icon className={cn(size === 'xs' || size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4', 'shrink-0')} />
      ) : null}
    </button>
  )
}
