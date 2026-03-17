'use client'

import { Search } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface SearchToolProps {
  label: string
  onClick?: () => void
}

export function SearchTool({ label, onClick }: SearchToolProps) {
  return <ToolBadge icon={Search} label={label} onClick={onClick} />
}
