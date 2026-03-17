'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { SessionHeader } from '@/components/session-header'
import { ChatInput } from '@/components/chat-input'
import { PlanPanel } from '@/components/plan-panel'
import { ChatMessage } from '@/components/chat-message'
import { FilePreviewPanel } from '@/components/file-preview-panel'
import { ToolPreviewPanel } from '@/components/tool-preview-panel'
import { VNCOverlay } from '@/components/vnc-overlay'
import { useSessionDetail } from '@/hooks/use-session-detail'
import { getToolKind } from '@/components/tool-use/utils'
import {
  eventsToTimeline,
  getLatestPlanFromEvents,
} from '@/lib/session-events'
import type { ToolEvent, FileInfo } from '@/lib/api/types'
import type { AttachmentFile, TimelineItem } from '@/lib/session-events'
import { sessionApi } from '@/lib/api/session'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

export interface SessionDetailViewProps {
  sessionId: string
  initialMessage?: string
  initialAttachments?: string[]
  hasInitialMessage?: boolean
}

/**
 * 从 timeline 中找到最后一个非 message 类型的工具事件
 */
function findLatestTool(timeline: TimelineItem[]): ToolEvent | null {
  for (let i = timeline.length - 1; i >= 0; i--) {
    const item = timeline[i]
    if (item.kind === 'tool' && getToolKind(item.data) !== 'message') {
      return item.data
    }
    if (item.kind === 'step' && item.tools.length > 0) {
      for (let j = item.tools.length - 1; j >= 0; j--) {
        if (getToolKind(item.tools[j]) !== 'message') {
          return item.tools[j]
        }
      }
    }
  }
  return null
}

export function SessionDetailView({ sessionId, initialMessage, initialAttachments, hasInitialMessage }: SessionDetailViewProps) {
  const router = useRouter()
  const {
    session,
    files,
    events,
    loading,
    error,
    refresh,
    refreshFiles,
    sendMessage,
    streaming,
  } = useSessionDetail(sessionId, hasInitialMessage)

  const timeline = useMemo(() => eventsToTimeline(events), [events])
  const planSteps = useMemo(() => getLatestPlanFromEvents(events), [events])

  const [fileListOpen, setFileListOpen] = useState(false)
  const [previewFile, setPreviewFile] = useState<AttachmentFile | null>(null)
  const [previewTool, setPreviewTool] = useState<ToolEvent | null>(null)
  const [vncOpen, setVncOpen] = useState(false)
  const initialMessageSentRef = useRef(false)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const prevToolCountRef = useRef(0)

  const hasPreview = previewFile !== null || previewTool !== null

  /**
   * 将 previewTool 解析为 timeline 中最新版本的工具对象。
   * 自动跟踪设置 previewTool 时工具事件可能尚无 content（如截图），
   * 后续 SSE 更新后 timeline 中对象已刷新但 state 仍为旧引用。
   * 通过 tool_call_id 匹配获取最新版本。
   */
  const resolvedPreviewTool = useMemo(() => {
    if (!previewTool) return null
    const id = (previewTool as { tool_call_id?: string }).tool_call_id
    if (!id) return previewTool

    for (let i = timeline.length - 1; i >= 0; i--) {
      const item = timeline[i]
      if (item.kind === 'tool' && (item.data as { tool_call_id?: string }).tool_call_id === id) {
        return item.data
      }
      if (item.kind === 'step') {
        for (const t of item.tools) {
          if ((t as { tool_call_id?: string }).tool_call_id === id) return t
        }
      }
    }
    return previewTool
  }, [previewTool, timeline])

  // 任务运行中自动追踪最新工具预览（VNC 打开时暂停）
  useEffect(() => {
    if (session?.status !== 'running' || vncOpen) return

    const latestTool = findLatestTool(timeline)
    const toolCount = timeline.reduce((n, item) => {
      if (item.kind === 'tool') return n + 1
      if (item.kind === 'step') return n + item.tools.length
      return n
    }, 0)

    if (toolCount > prevToolCountRef.current && latestTool) {
      setPreviewTool(latestTool)
      setPreviewFile(null)
      scrollContainerRef.current?.scrollTo({ top: scrollContainerRef.current.scrollHeight, behavior: 'smooth' })
    }
    prevToolCountRef.current = toolCount
  }, [timeline, session?.status, vncOpen])

  useEffect(() => {
    if (
      initialMessage &&
      !initialMessageSentRef.current &&
      session &&
      !loading &&
      !streaming
    ) {
      initialMessageSentRef.current = true
      sendMessage(initialMessage, initialAttachments || [])
        .then(() => {
          setTimeout(() => {
            router.replace(`/sessions/${sessionId}`)
          }, 100)
        })
        .catch((e) => {
          toast.error(e instanceof Error ? e.message : '发送消息失败')
        })
    }
  }, [initialMessage, initialAttachments, session, loading, streaming, sendMessage, sessionId, router])

  const handleSend = useCallback(
    async (message: string, uploadedFiles: FileInfo[]) => {
      try {
        const attachmentIds = uploadedFiles.map((f) => f.id)
        await sendMessage(message, attachmentIds)
      } catch (e) {
        toast.error(e instanceof Error ? e.message : '发送失败，请重试')
        throw e
      }
    },
    [sendMessage]
  )

  const handleViewAllFiles = useCallback(() => {
    refreshFiles()
    setFileListOpen(true)
  }, [refreshFiles])

  const handleFileClick = useCallback((file: AttachmentFile) => {
    setPreviewFile(file)
    setPreviewTool(null)
  }, [])

  const handleToolClick = useCallback((tool: ToolEvent) => {
    const kind = getToolKind(tool)
    if (kind === 'message') return
    setPreviewTool(tool)
    setPreviewFile(null)
  }, [])

  const handleClosePreview = useCallback(() => {
    setPreviewFile(null)
    setPreviewTool(null)
  }, [])

  const handleJumpToLatest = useCallback(() => {
    const latest = findLatestTool(timeline)
    if (latest) {
      setPreviewTool(latest)
      setPreviewFile(null)
    }
    scrollContainerRef.current?.scrollTo({ top: scrollContainerRef.current.scrollHeight, behavior: 'smooth' })
  }, [timeline])

  const handleOpenVNC = useCallback(() => {
    setVncOpen(true)
  }, [])

  const handleCloseVNC = useCallback(() => {
    setVncOpen(false)
    // 关闭 VNC 后跳转到最新工具
    const latest = findLatestTool(timeline)
    if (latest && session?.status === 'running') {
      setPreviewTool(latest)
      setPreviewFile(null)
      setTimeout(() => {
        scrollContainerRef.current?.scrollTo({ top: scrollContainerRef.current.scrollHeight, behavior: 'smooth' })
      }, 100)
    }
  }, [timeline, session?.status])

  const handleStop = useCallback(async () => {
    if (!session) return
    try {
      await sessionApi.stopSession(sessionId)
      toast.success('任务已停止')
      refresh()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '停止任务失败')
    }
  }, [session, sessionId, refresh])

  if (loading && !session) {
    return (
      <div className="relative flex flex-col h-full flex-1 min-w-0 px-4 items-center justify-center">
        {hasInitialMessage ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="size-4 animate-spin" />
            <span>正在思考中...</span>
          </div>
        ) : (
          <p className="text-sm text-gray-500">加载中...</p>
        )}
      </div>
    )
  }

  if (error && !session) {
    return (
      <div className="relative flex flex-col h-full flex-1 min-w-0 px-4 items-center justify-center gap-2">
        <p className="text-sm text-red-600">{error.message}</p>
        <button
          type="button"
          onClick={() => refresh()}
          className="text-sm text-primary underline"
        >
          重试
        </button>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="relative flex flex-col h-full flex-1 min-w-0 px-4 items-center justify-center">
        <p className="text-sm text-gray-500">未找到该任务</p>
      </div>
    )
  }

  return (
    <>
      <div className="flex flex-row h-screen w-full overflow-hidden">
        {/* 主内容区 */}
        <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
          <div className={`flex flex-col h-full mx-auto w-full min-w-0 px-4 ${hasPreview ? '' : 'max-w-[768px]'}`}>
            <div className="flex-shrink-0">
              <SessionHeader
                title={session.title}
                files={files}
                fileListOpen={fileListOpen}
                onFileListOpenChange={setFileListOpen}
                onFetchFiles={refreshFiles}
                onFileClick={handleFileClick}
              />
            </div>

            <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
              <div className="flex flex-col w-full gap-3 pt-3">
                {timeline.length === 0 && !streaming && !hasInitialMessage && (
                  <div className="flex items-center justify-center py-8 text-sm text-gray-500">
                    暂无对话记录，在下方输入任务或提问
                  </div>
                )}
                {timeline.map((item) => (
                  <ChatMessage
                    key={item.id}
                    item={item}
                    onViewAllFiles={handleViewAllFiles}
                    onFileClick={handleFileClick}
                    onToolClick={handleToolClick}
                  />
                ))}

                {(session?.status === 'running' || (hasInitialMessage && !initialMessageSentRef.current)) && (
                  <div className="flex items-center gap-2 text-sm text-gray-500 py-3">
                    <Loader2 className="size-4 animate-spin" />
                    <span>正在思考中...</span>
                  </div>
                )}

                <div className="h-[140px]" />
              </div>
            </div>

            <div className="flex-shrink-0 bg-[#f8f8f7] py-4">
              <PlanPanel className="mb-2" steps={planSteps} />
              <ChatInput
                onSend={handleSend}
                sessionId={sessionId}
                isRunning={session?.status === 'running'}
                onStop={handleStop}
              />
            </div>
          </div>
        </div>

        {/* 文件预览面板 */}
        {previewFile && (
          <div className="flex-shrink-0 w-[600px] h-full animate-in slide-in-from-right duration-300">
            <FilePreviewPanel file={previewFile} onClose={handleClosePreview} />
          </div>
        )}

        {/* 工具预览面板 */}
        {resolvedPreviewTool && (
          <div className="flex-shrink-0 w-[600px] h-full py-2 pr-2 animate-in slide-in-from-right duration-300">
            <ToolPreviewPanel
              tool={resolvedPreviewTool}
              onClose={handleClosePreview}
              onJumpToLatest={handleJumpToLatest}
              onOpenVNC={getToolKind(resolvedPreviewTool) === 'browser' ? handleOpenVNC : undefined}
            />
          </div>
        )}
      </div>

      {/* noVNC 全屏远程桌面覆盖层 */}
      {vncOpen && (
        <VNCOverlay sessionId={sessionId} onClose={handleCloseVNC} />
      )}
    </>
  )
}
