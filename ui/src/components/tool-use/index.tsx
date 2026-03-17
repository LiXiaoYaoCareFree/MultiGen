'use client'

import type { ComponentType } from 'react'
import type { ToolEvent } from '@/lib/api/types'
import { getToolKind, getFriendlyToolLabel } from './utils'
import type { ToolKind } from './utils'
import { MessageTool } from './message-tool'
import { FileTool } from './file-tool'
import { BashTool } from './bash-tool'
import { SearchTool } from './search-tool'
import { BrowserTool } from './browser-tool'
import { McpTool } from './mcp-tool'
import { A2aTool } from './a2a-tool'
import { DefaultTool } from './default-tool'

export type { ToolKind } from './utils'
export { getToolKind, getFriendlyToolLabel } from './utils'
export { MessageTool } from './message-tool'
export { FileTool } from './file-tool'
export { BashTool } from './bash-tool'
export { SearchTool } from './search-tool'
export { BrowserTool } from './browser-tool'
export { McpTool } from './mcp-tool'
export { A2aTool } from './a2a-tool'
export { DefaultTool } from './default-tool'
export { ToolBadge } from './tool-badge'

export interface ToolUseProps {
  data?: ToolEvent | null
  onClick?: () => void
}

const TOOL_COMPONENTS: Record<ToolKind, ComponentType<{ label: string; onClick?: () => void }>> = {
  message: MessageTool,
  bash: BashTool,
  file: FileTool,
  search: SearchTool,
  browser: BrowserTool,
  mcp: McpTool,
  a2a: A2aTool,
  default: DefaultTool,
}

export function ToolUse({ data, onClick }: ToolUseProps) {
  const label = getFriendlyToolLabel(data)
  const kind = getToolKind(data)
  const Component = TOOL_COMPONENTS[kind]
  return <Component label={label} onClick={onClick} />
}
