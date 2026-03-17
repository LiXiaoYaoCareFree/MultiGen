'use client'

import { SquareChevronRight } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface DefaultToolProps {
  label: string
  onClick?: () => void
}

export function DefaultTool({ label, onClick }: DefaultToolProps) {
  return <ToolBadge icon={SquareChevronRight} label={label} onClick={onClick} />
}
