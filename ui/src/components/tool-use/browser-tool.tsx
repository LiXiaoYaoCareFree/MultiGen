'use client'

import { Globe } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface BrowserToolProps {
  label: string
  onClick?: () => void
}

export function BrowserTool({ label, onClick }: BrowserToolProps) {
  return <ToolBadge icon={Globe} label={label} onClick={onClick} />
}
