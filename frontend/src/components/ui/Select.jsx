import React, { forwardRef } from 'react'
import { cn } from '../../utils/cn'

export const Select = forwardRef(function Select(
  {
    label,
    error,
    helperText,
    children,
    className = '',
    required = false,
    id,
    ...props
  },
  ref
) {
  const selectId = id || props.name

  return (
    <div className="w-full space-y-1.5 text-left">
      {label && (
        <label
          htmlFor={selectId}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-700"
        >
          {label}
          {required && <span className="text-rose-500 ml-1">*</span>}
        </label>
      )}

      <div className="relative rounded-lg shadow-2xs">
        <select
          id={selectId}
          ref={ref}
          className={cn(
            'block w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-slate-900 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-[#142B4A]/20 focus:border-[#142B4A]',
            'disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed',
            error ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-200' : 'border-slate-300',
            className
          )}
          {...props}
        >
          {children}
        </select>
      </div>

      {error ? (
        <p className="text-xs text-rose-600 font-medium">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-slate-500">{helperText}</p>
      ) : null}
    </div>
  )
})
