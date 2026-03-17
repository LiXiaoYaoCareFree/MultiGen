'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { SessionDetailView } from '@/components/session-detail-view'

interface PageProps {
  params: Promise<{ id: string }>
}

/**
 * 任务详情页：展示会话标题、事件时间线、任务进度与输入框。
 * - 通过 getSessionDetail 获取任务详情与事件列表（若后端返回 events）
 * - 未完成任务通过 chat 空 body 流式拉取事件
 * - 发送消息通过 chat 带 message/attachments 流式追加事件
 * - 支持从 URL 参数读取初始消息（用于首页跳转场景）
 */
export default function SessionDetailPage({ params }: PageProps) {
  const searchParams = useSearchParams()
  const [sessionData, setSessionData] = useState<{
    id: string
    initialMessage?: string
    initialAttachments?: string[]
    hasInitialMessage: boolean
  } | null>(null)
  
  useEffect(() => {
    params.then(p => {
      // 尝试从 URL 参数读取初始消息（Base64 编码）
      const initParam = searchParams.get('init')
      
      if (initParam) {
        try {
          // 解码 Base64
          const decoded = decodeURIComponent(atob(initParam))
          const { message, attachments } = JSON.parse(decoded)
          
          // 一次性设置所有状态
          setSessionData({
            id: p.id,
            initialMessage: message,
            initialAttachments: attachments,
            hasInitialMessage: true
          })
        } catch (e) {
          console.error('Failed to parse init param:', e)
          setSessionData({
            id: p.id,
            hasInitialMessage: false
          })
        }
      } else {
        // 没有初始消息
        setSessionData({
          id: p.id,
          hasInitialMessage: false
        })
      }
    })
  }, [params, searchParams])

  if (!sessionData) {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <SessionDetailView
      sessionId={sessionData.id}
      initialMessage={sessionData.initialMessage}
      initialAttachments={sessionData.initialAttachments}
      hasInitialMessage={sessionData.hasInitialMessage}
    />
  )
}
