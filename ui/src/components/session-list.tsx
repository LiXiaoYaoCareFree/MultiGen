'use client'

import {useCallback, useState} from 'react'
import {useParams, useRouter} from 'next/navigation'
import {toast} from 'sonner'
import {ItemGroup} from '@/components/ui/item'
import {SessionItem} from '@/components/session-item'
import {DeleteSessionDialog} from '@/components/delete-session-dialog'
import {useSessions} from '@/hooks/use-sessions'
import type {Session} from '@/lib/api'

/**
 * 会话列表组件
 * 负责渲染列表、处理路由导航及删除操作
 */
export function SessionList() {
  const router = useRouter()
  const params = useParams()
  const {sessions, loading, error, refresh, deleteSession} = useSessions()

  // 待删除的会话
  const [pendingDeleteSession, setPendingDeleteSession] = useState<Session | null>(null)

  const handleSessionClick = useCallback((sessionId: string) => {
    router.push(`/sessions/${sessionId}`)
  }, [router])

  const handleDeleteRequest = useCallback((session: Session) => {
    setPendingDeleteSession(session)
  }, [])

  const handleDeleteConfirm = useCallback(async (adminApiKey?: string) => {
    if (!pendingDeleteSession) return

    const sessionTitle = pendingDeleteSession.title || '新任务'
    const success = await deleteSession(pendingDeleteSession.session_id, adminApiKey)

    if (success) {
      toast.success(`已删除任务「${sessionTitle}」`)
      // 如果删除的是当前正在查看的会话，跳转到首页
      if (params?.id === pendingDeleteSession.session_id) {
        router.push('/')
      }
    } else {
      toast.error(`删除任务「${sessionTitle}」失败，请重试`)
    }

    setPendingDeleteSession(null)
  }, [pendingDeleteSession, deleteSession, params?.id, router])

  const handleDialogOpenChange = useCallback((open: boolean) => {
    if (!open) {
      setPendingDeleteSession(null)
    }
  }, [])

  // 加载态：骨架屏
  if (loading) {
    return (
      <ItemGroup className="gap-1">
        {Array.from({length: 3}).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-2 p-2 animate-pulse"
          >
            <div className="size-8 rounded-full bg-muted"/>
            <div className="flex-1 space-y-1.5">
              <div className="h-3.5 bg-muted rounded w-3/4"/>
              <div className="h-3 bg-muted rounded w-1/2"/>
            </div>
          </div>
        ))}
      </ItemGroup>
    )
  }

  // 错误态
  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-sm text-muted-foreground">
        <p>加载失败</p>
        <button
          className="text-primary underline underline-offset-4 cursor-pointer"
          onClick={refresh}
        >
          重试
        </button>
      </div>
    )
  }

  // 空态
  if (sessions.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        暂无任务
      </div>
    )
  }

  return (
    <>
      <ItemGroup className="gap-1">
        {sessions.map((session) => (
          <SessionItem
            key={session.session_id}
            session={session}
            isActive={session.session_id === String(params?.id ?? '')}
            onClick={handleSessionClick}
            onDelete={handleDeleteRequest}
          />
        ))}
      </ItemGroup>

      {/* 删除确认弹窗 */}
      <DeleteSessionDialog
        open={!!pendingDeleteSession}
        onOpenChange={handleDialogOpenChange}
        onConfirm={handleDeleteConfirm}
      />
    </>
  )
}

