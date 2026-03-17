'use client'

import { FileSearch } from 'lucide-react'
import { ToolBadge } from './tool-badge'

export interface FileToolProps {
  label: string
  onClick?: () => void
}

export function FileTool({ label, onClick }: FileToolProps) {
  return <ToolBadge icon={FileSearch} label={label} onClick={onClick} />
}
