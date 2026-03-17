'use client'

import {useRef, useState} from 'react'
import {useRouter} from 'next/navigation'
import {ChatHeader} from '@/components/chat-header'
import {ChatInput, type ChatInputRef} from '@/components/chat-input'
import {SuggestedQuestions} from '@/components/suggested-questions'
import {sessionApi} from '@/lib/api/session'
import type {FileInfo} from '@/lib/api/types'
import {toast} from 'sonner'

export default function Page() {
  const router = useRouter()
  const chatInputRef = useRef<ChatInputRef>(null)
  const [sending, setSending] = useState(false)

  const handleQuestionClick = (question: string) => {
    chatInputRef.current?.setInputText(question)
  }

  const handleSend = async (message: string, files: FileInfo[]) => {
    if (sending) return

    setSending(true)

    try {
      // 1. 创建新会话
      const session = await sessionApi.createSession()
      const sessionId = session.session_id

      // 2. 将消息数据编码到 URL，在详情页发送
      const attachments = files.map((file) => file.id)
      const payload = JSON.stringify({ message, attachments })
      // 使用 Base64 编码避免 URL 特殊字符问题
      const encoded = btoa(encodeURIComponent(payload))
      
      // 3. 跳转到详情页，携带编码后的初始消息
      router.push(`/sessions/${sessionId}?init=${encoded}`)
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '创建会话失败'
      toast.error(errorMessage)
      setSending(false)
      throw error
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* 顶部header */}
      <ChatHeader/>
      {/* 中间对话框 - 垂直居中，视觉上移一个导航栏高度 */}
      <div className="flex-1 flex items-center justify-center px-4 py-6 sm:py-8 -mt-12 sm:-mt-16">
        <div className="w-full max-w-full sm:max-w-[768px] sm:min-w-[390px] mx-auto">
          {/* 对话提示内容 */}
          <div className="text-[24px] sm:text-[32px] font-bold mb-4 sm:mb-6 text-center sm:text-left">
            <div className="text-gray-700">您好，同学</div>
            <div className="text-gray-500">我能为您做什么?</div>
          </div>
          {/* 对话框 */}
          <ChatInput
            ref={chatInputRef}
            className="mb-4 sm:mb-6"
            onSend={handleSend}
            disabled={sending}
          />
          {/* 推荐对话内容 */}
          <SuggestedQuestions onQuestionClick={handleQuestionClick}/>
        </div>
      </div>
    </div>
  )
}
