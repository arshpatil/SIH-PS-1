import React from 'react'
import { cn } from '../../utils/cn'

export function Card({
  children,
  className = '',
  hover = false,
  ...props
}) {
  return (
    <div
      className={cn(
        'bg-white rounded-xl border border-slate-200/90 shadow-subtle p-5 md:p-6 transition-all',
        hover && 'hover:border-slate-300 hover:shadow-md transition-shadow',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  subtitle,
  action,
  className = '',
}) {
  return (
    <div className={cn('flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-slate-100', className)}>
      <div>
        {title && <h3 className="text-base font-semibold text-slate-900 tracking-tight">{title}</h3>}
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
