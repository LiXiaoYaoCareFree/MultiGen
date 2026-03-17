'use client'

import { useMemo } from 'react'
import type { ToolEvent } from '@/lib/api/types'
import { getToolKind, getFriendlyToolLabel, getArg } from '@/components/tool-use/utils'
import type { ToolKind } from '@/components/tool-use/utils'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import {
  Maximize2,
  Monitor,
  Play,
  Terminal,
  Globe,
  Search,
  FileSearch,
  Wrench,
  Bot,
  Sparkles,
} from 'lucide-react'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ToolPreviewPanelProps {
  tool: ToolEvent
  onClose: () => void
  onJumpToLatest?: () => void
  onOpenVNC?: () => void
}

type ConsoleRecord = { ps1: string; command: string; output: string }

type SearchResultItem = { url: string; title: string; snippet: string }

/* ------------------------------------------------------------------ */
/*  Content extractors                                                 */
/* ------------------------------------------------------------------ */

function getToolContent(tool: ToolEvent): Record<string, unknown> | null {
  const c = tool.content
  if (c && typeof c === 'object' && !Array.isArray(c)) return c as Record<string, unknown>
  return null
}

function getToolDescription(kind: ToolKind): string {
  const map: Record<ToolKind, string> = {
    bash: '终端',
    browser: '浏览器',
    search: '搜索',
    file: '文件',
    mcp: 'MCP 服务',
    a2a: 'A2A 智能体',
    message: '消息',
    default: '工具',
  }
  return map[kind]
}

function getToolIcon(kind: ToolKind) {
  const map: Record<ToolKind, typeof Terminal> = {
    bash: Terminal,
    browser: Globe,
    search: Search,
    file: FileSearch,
    mcp: Wrench,
    a2a: Bot,
    message: Monitor,
    default: Monitor,
  }
  return map[kind]
}

/* ------------------------------------------------------------------ */
/*  Jump-to-latest overlay button                                      */
/* ------------------------------------------------------------------ */

function JumpToLatestButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/90 backdrop-blur text-sm text-gray-700 hover:bg-white shadow-md border border-gray-200 transition-colors cursor-pointer"
    >
      <Play size={12} className="fill-current" />
      <span>跳转实时</span>
    </button>
  )
}

/* ------------------------------------------------------------------ */
/*  Sub-previews                                                       */
/* ------------------------------------------------------------------ */

function ShellPreview({ tool }: { tool: ToolEvent }) {
  const content = getToolContent(tool)
  const consoleData = content?.console
  const sessionId = getArg(tool.args, 'session_id')

  const records: ConsoleRecord[] = useMemo(() => {
    if (Array.isArray(consoleData)) return consoleData as ConsoleRecord[]
    return []
  }, [consoleData])

  return (
    <div className="flex flex-col gap-3 p-4 h-full">
      <div className="flex-1 rounded-lg overflow-hidden border border-gray-700 bg-[#1e1e1e] flex flex-col min-h-0">
        <div className="text-center text-xs text-gray-400 py-1.5 bg-[#2d2d2d] border-b border-gray-700 flex-shrink-0">
          {sessionId || 'shell'}
        </div>
        <ScrollArea className="flex-1">
          <div className="p-4 font-mono text-sm leading-relaxed">
            {records.length > 0 ? records.map((rec, i) => (
              <div key={i} className="mb-2">
                <div>
                  <span className="text-green-400">{rec.ps1}</span>
                  {' '}
                  <span className="text-white">{rec.command}</span>
                </div>
                {rec.output && (
                  <pre className="text-gray-300 whitespace-pre-wrap break-words mt-0.5">{rec.output}</pre>
                )}
              </div>
            )) : (
              <span className="text-gray-500">等待命令输出...</span>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}

function BrowserPreview({ tool, onOpenVNC }: { tool: ToolEvent; onOpenVNC?: () => void }) {
  const content = getToolContent(tool)
  const screenshot = typeof content?.screenshot === 'string' ? content.screenshot : null
  const url = getArg(tool.args, 'url', 'href', 'link')

  return (
    <div className="flex flex-col gap-3 p-4 h-full">
      {url && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 border text-sm text-gray-600 flex-shrink-0">
          <Globe size={14} className="text-gray-400 flex-shrink-0" />
          <span className="truncate">{url}</span>
        </div>
      )}
      <div className="flex-1 rounded-lg overflow-hidden border min-h-0 relative">
        {screenshot ? (
          <ScrollArea className="h-full">
            <img
              src={screenshot}
              alt="浏览器截图"
              className="w-full h-auto"
            />
          </ScrollArea>
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-gray-500">
            等待页面截图...
          </div>
        )}
        {onOpenVNC && (
          <button
            type="button"
            onClick={onOpenVNC}
            className="absolute bottom-3 right-3 w-9 h-9 rounded-full bg-gray-800/80 text-white flex items-center justify-center shadow-lg hover:bg-gray-700 transition-colors cursor-pointer z-10"
            aria-label="打开远程桌面"
          >
            <Sparkles size={16} />
          </button>
        )}
      </div>
    </div>
  )
}

function SearchPreview({ tool }: { tool: ToolEvent }) {
  const content = getToolContent(tool)
  const rawResults = content?.results

  const results: SearchResultItem[] = useMemo(() => {
    if (Array.isArray(rawResults)) return rawResults as SearchResultItem[]
    return []
  }, [rawResults])

  const query = getArg(tool.args, 'query', 'q')

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-1 p-4">
        {query && (
          <div className="text-sm text-gray-500 mb-3">
            搜索&ldquo;{query}&rdquo;的结果 · 共 {results.length} 条
          </div>
        )}
        {results.length > 0 ? results.map((item, i) => (
          <a
            key={i}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block p-3 rounded-lg hover:bg-gray-50 transition-colors group"
          >
            <div className="text-xs text-green-700 truncate mb-0.5">{item.url}</div>
            <div className="text-sm font-medium text-blue-700 group-hover:underline mb-1 line-clamp-1">
              {item.title}
            </div>
            {item.snippet && (
              <div className="text-xs text-gray-600 line-clamp-2">{item.snippet}</div>
            )}
          </a>
        )) : (
          <div className="text-sm text-gray-500 text-center py-8">暂无搜索结果</div>
        )}
      </div>
    </ScrollArea>
  )
}

function FileToolPreview({ tool }: { tool: ToolEvent }) {
  const content = getToolContent(tool)
  const fileContent = typeof content?.content === 'string' ? content.content : null
  const filepath = getArg(tool.args, 'filepath', 'path', 'pathname')

  return (
    <div className="flex flex-col gap-3 p-4 h-full">
      <div className="flex-1 rounded-lg overflow-hidden border border-gray-700 bg-[#1e1e1e] flex flex-col min-h-0">
        {filepath && (
          <div className="text-center text-xs text-gray-400 py-1.5 bg-[#2d2d2d] border-b border-gray-700 flex-shrink-0 truncate px-4">
            {filepath}
          </div>
        )}
        <ScrollArea className="flex-1">
          <pre className="p-4 font-mono text-sm text-gray-300 whitespace-pre-wrap break-words leading-relaxed">
            {fileContent ?? '等待文件内容...'}
          </pre>
        </ScrollArea>
      </div>
    </div>
  )
}

function MCPPreview({ tool }: { tool: ToolEvent }) {
  const content = getToolContent(tool)
  const result = content?.result

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4">
        <div className="flex flex-col gap-1">
          <div className="text-xs text-gray-500 uppercase tracking-wide">工具信息</div>
          <div className="rounded-lg border bg-gray-50 p-3 text-sm">
            <div><span className="text-gray-500">名称：</span><span className="text-gray-800">{tool.name}</span></div>
            <div><span className="text-gray-500">函数：</span><span className="text-gray-800">{tool.function}</span></div>
            {Object.keys(tool.args).length > 0 && (
              <div className="mt-1">
                <span className="text-gray-500">参数：</span>
                <pre className="text-xs text-gray-700 mt-1 whitespace-pre-wrap break-words">
                  {JSON.stringify(tool.args, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-xs text-gray-500 uppercase tracking-wide">执行结果</div>
          <div className="rounded-lg border border-gray-700 bg-[#1e1e1e] p-4">
            <pre className="font-mono text-sm text-gray-300 whitespace-pre-wrap break-words">
              {result != null
                ? (typeof result === 'string' ? result : JSON.stringify(result, null, 2))
                : '等待执行结果...'}
            </pre>
          </div>
        </div>
      </div>
    </ScrollArea>
  )
}

function A2APreview({ tool }: { tool: ToolEvent }) {
  const content = getToolContent(tool)
  const result = content?.a2a_result

  const query = getArg(tool.args, 'query', 'message', 'input')

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4">
        <div className="flex flex-col gap-1">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Agent 调用信息</div>
          <div className="rounded-lg border bg-gray-50 p-3 text-sm">
            <div><span className="text-gray-500">工具：</span><span className="text-gray-800">{tool.name}</span></div>
            <div><span className="text-gray-500">函数：</span><span className="text-gray-800">{tool.function}</span></div>
            {query && <div><span className="text-gray-500">指令：</span><span className="text-gray-800">{query}</span></div>}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-xs text-gray-500 uppercase tracking-wide">执行结果</div>
          <div className="rounded-lg border border-gray-700 bg-[#1e1e1e] p-4">
            <pre className="font-mono text-sm text-gray-300 whitespace-pre-wrap break-words">
              {result != null
                ? (typeof result === 'string' ? result : JSON.stringify(result, null, 2))
                : '等待执行结果...'}
            </pre>
          </div>
        </div>
      </div>
    </ScrollArea>
  )
}

function DefaultPreview({ tool }: { tool: ToolEvent }) {
  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4">
        <div className="rounded-lg border bg-gray-50 p-3 text-sm">
          <div><span className="text-gray-500">名称：</span><span className="text-gray-800">{tool.name}</span></div>
          <div><span className="text-gray-500">函数：</span><span className="text-gray-800">{tool.function}</span></div>
        </div>
        {tool.content != null && (
          <div className="rounded-lg border border-gray-700 bg-[#1e1e1e] p-4">
            <pre className="font-mono text-sm text-gray-300 whitespace-pre-wrap break-words">
              {typeof tool.content === 'string' ? tool.content : JSON.stringify(tool.content, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </ScrollArea>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function ToolPreviewPanel({
  tool,
  onClose,
  onJumpToLatest,
  onOpenVNC,
}: ToolPreviewPanelProps) {
  const kind = getToolKind(tool)
  const label = getFriendlyToolLabel(tool)
  const ToolIcon = getToolIcon(kind)
  const toolDesc = getToolDescription(kind)

  return (
    <div className="flex flex-col h-full rounded-xl bg-white shadow-xl overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-2 px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">llmops 的电脑</h2>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="关闭预览"
            className="cursor-pointer"
          >
            <Maximize2 size={16} />
          </Button>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Monitor size={14} className="text-gray-500 flex-shrink-0" />
          <span>llmops 正在使用</span>
          <span className="font-medium text-gray-800">{toolDesc}</span>
        </div>
        <div className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 border border-gray-200 bg-gray-100 text-gray-700 text-xs w-fit max-w-full">
          <ToolIcon size={14} className="flex-shrink-0 text-gray-500" />
          <span className="truncate">{label}</span>
        </div>
      </div>

      {/* Content with overlaid jump button */}
      <div className="flex-1 overflow-hidden relative">
        {kind === 'bash' && <ShellPreview tool={tool} />}
        {kind === 'browser' && <BrowserPreview tool={tool} onOpenVNC={onOpenVNC} />}
        {kind === 'search' && <SearchPreview tool={tool} />}
        {kind === 'file' && <FileToolPreview tool={tool} />}
        {kind === 'mcp' && <MCPPreview tool={tool} />}
        {kind === 'a2a' && <A2APreview tool={tool} />}
        {(kind === 'default' || kind === 'message') && <DefaultPreview tool={tool} />}

        {/* "跳转实时" overlaid at bottom-center */}
        {onJumpToLatest && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10">
            <JumpToLatestButton onClick={onJumpToLatest} />
          </div>
        )}
      </div>
    </div>
  )
}
