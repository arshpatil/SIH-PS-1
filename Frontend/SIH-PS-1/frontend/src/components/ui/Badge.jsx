import React from 'react'
import { cn } from '../../utils/cn'

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  dot = false,
}) {
  const variants = {
    default: 'bg-slate-100 text-slate-800 border-slate-200',
    primary: 'bg-navy-50 text-navy-800 border-navy-200',
    success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    warning: 'bg-amber-50 text-amber-900 border-amber-300',
    danger: 'bg-rose-50 text-rose-800 border-rose-200',
    info: 'bg-blue-50 text-blue-800 border-blue-200',
    purple: 'bg-purple-50 text-purple-800 border-purple-200',
    neutral: 'bg-slate-50 text-slate-600 border-slate-200',
  }

  const dotColors = {
    default: 'bg-slate-500',
    primary: 'bg-[#142B4A]',
    success: 'bg-emerald-600',
    warning: 'bg-amber-600',
    danger: 'bg-rose-600',
    info: 'bg-blue-600',
    purple: 'bg-purple-600',
    neutral: 'bg-slate-400',
  }

  const sizes = {
    xs: 'text-[10px] px-1.5 py-0.5 leading-none',
    sm: 'text-2xs px-2 py-0.5 leading-tight',
    md: 'text-xs px-2.5 py-1 leading-tight',
    lg: 'text-sm px-3 py-1.5 leading-tight',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-full border shadow-2xs whitespace-nowrap',
        variants[variant] || variants.default,
        sizes[size] || sizes.md,
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            'w-1.5 h-1.5 rounded-full mr-1.5 shrink-0',
            dotColors[variant] || 'bg-slate-500'
          )}
        />
      )}
      {children}
    </span>
  )
}
