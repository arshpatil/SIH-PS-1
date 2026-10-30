import React from 'react'
import { FolderSearch } from 'lucide-react'
import { Button } from './Button'

export function EmptyState({
  icon: Icon = FolderSearch,
  title = 'No records found',
  description = 'Try adjusting your search criteria or filter selections to find what you are looking for.',
  actionLabel,
  onAction,
}) {
  return (
    <div className="flex flex-col items-center justify-center p-8 sm:p-10 text-center bg-white rounded-xl border border-dashed border-slate-200 my-3">
      <div className="w-11 h-11 rounded-xl bg-slate-100/90 text-slate-500 flex items-center justify-center mb-3 shadow-2xs">
        <Icon className="w-5 h-5 text-slate-500" />
      </div>
      <h4 className="text-sm sm:text-base font-semibold text-slate-900">{title}</h4>
      <p className="text-xs text-slate-500 max-w-sm mt-1 mb-4 leading-relaxed">{description}</p>
      {actionLabel && onAction && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
