'use client'

import { Wrench } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface McpToolProps {
  label: string
  onClick?: () => void
}

export function McpTool({ label, onClick }: McpToolProps) {
  return <ToolBadge icon={Wrench} label={label} onClick={onClick} />
}
