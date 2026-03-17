'use client'

import type { LucideIcon } from 'lucide-react'

export interface ToolBadgeProps {
  icon: LucideIcon
  label: string
  onClick?: () => void
}

export function ToolBadge({ icon: Icon, label, onClick }: ToolBadgeProps) {
  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } } : undefined}
      className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 border border-gray-200 bg-gray-100 text-gray-700 text-sm w-fit max-w-full min-w-0 cursor-pointer hover:bg-gray-200/60 transition-colors"
    >
      <span className="shrink-0 flex items-center justify-center text-gray-600">
        <Icon size={16} className="shrink-0" />
      </span>
      <span className="truncate max-w-[480px]">{label}</span>
    </div>
  )
}
