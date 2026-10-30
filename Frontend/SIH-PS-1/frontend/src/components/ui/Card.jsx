import React from 'react'
import { cn } from '../../utils/cn'

export function Card({
  children,
  className = '',
  hover = false,
  padding = 'default', // 'none' | 'sm' | 'default' | 'lg'
  ...props
}) {
  const paddingMap = {
    none: 'p-0',
    sm: 'p-3 sm:p-4',
    default: 'p-4 sm:p-5 md:p-6',
    lg: 'p-6 sm:p-8',
  }

  return (
    <div
      className={cn(
        'bg-white rounded-xl border border-slate-200 shadow-card transition-all',
        hover && 'hover:border-slate-300 hover:shadow-subtle transition-shadow',
        paddingMap[padding] || paddingMap.default,
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
  icon: Icon,
  className = '',
}) {
  return (
    <div className={cn('flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3.5 border-b border-slate-100', className)}>
      <div className="flex items-start gap-2.5">
        {Icon && (
          <div className="p-1.5 rounded-lg bg-navy-50 text-navy-700 mt-0.5 shrink-0">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <div>
          {title && <h3 className="text-sm sm:text-base font-semibold text-slate-900 tracking-tight">{title}</h3>}
          {subtitle && <p className="text-2xs sm:text-xs text-slate-500 mt-0.5 leading-relaxed">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="shrink-0 flex items-center gap-2">{action}</div>}
    </div>
  )
}
