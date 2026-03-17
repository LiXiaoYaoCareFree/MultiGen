'use client'

import React, {createContext, useCallback, useContext, useEffect, useRef, useState} from 'react'
import {sessionApi} from '@/lib/api'
import type {Session} from '@/lib/api'

/** 重连配置 */
const RETRY_CONFIG = {
  maxRetries: 10,
  baseDelay: 1000,
  maxDelay: 30_000,
} as const

/**
 * 从 API 返回值中安全提取 Session 数组
 * 兼容 data 为 { sessions: [...] } / 直接数组 / null 等格式
 */
function normalizeSessions(raw: unknown): Session[] {
  if (Array.isArray(raw)) return raw as Session[]
  if (raw && typeof raw === 'object' && 'sessions' in raw) {
    return Array.isArray((raw as Record<string, unknown>).sessions)
      ? ((raw as Record<string, unknown>).sessions as Session[])
      : []
  }
  return []
}

// ==================== Context ====================

type SessionsContextValue = {
  sessions: Session[]
  loading: boolean
  error: string | null
  /** 手动刷新（通过 REST 接口拉取一次） */
  refresh: () => Promise<void>
  deleteSession: (sessionId: string, adminApiKey?: string) => Promise<boolean>
}

const SessionsContext = createContext<SessionsContextValue | null>(null)

// ==================== Provider ====================

/**
 * 会话列表数据 Provider
 *
 * 放置在 root layout 中，确保不会因为侧边栏展开/折叠而重新挂载。
 *
 * 数据流:
 *  1. 挂载后立即通过 REST GET /sessions 获取初始数据（仅一次）
 *  2. 同时建立 SSE POST /sessions/stream 长连接，接收实时推送
 *  3. SSE 断开后自动指数退避重连
 *  4. refresh() 可手动通过 REST 拉取
 */
export function SessionsProvider({children}: { children: React.ReactNode }) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const cleanupRef = useRef<(() => void) | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  /** 确保 REST 初始请求只发起一次（防止 Strict Mode 重复） */
  const initialFetchedRef = useRef(false)
  /** 标记 SSE 是否已经推送过数据，防止 REST 回调覆盖更新的 SSE 数据 */
  const sseReceivedRef = useRef(false)

  // ---------- 手动刷新 ----------
  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const raw = await sessionApi.getSessions()
      setSessions(normalizeSessions(raw))
    } catch (err) {
      console.error('[Sessions] REST 获取失败:', err)
      setError(err instanceof Error ? err.message : '获取会话列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // ---------- 初始 REST 请求（仅一次） ----------
  useEffect(() => {
    if (initialFetchedRef.current) return
    initialFetchedRef.current = true

    sessionApi
      .getSessions()
      .then((raw) => {
        // 仅在 SSE 尚未推送过数据时更新，防止用旧数据覆盖 SSE 已推送的新数据
        if (!sseReceivedRef.current) {
          setSessions(normalizeSessions(raw))
        }
        setLoading(false)
        setError(null)
      })
      .catch((err) => {
        console.error('[Sessions] 初始获取失败:', err)
        setError(err instanceof Error ? err.message : '获取会话列表失败')
        setLoading(false)
      })
  }, [])

  // ---------- SSE 实时订阅 ----------
  useEffect(() => {
    let mounted = true
    let retryCount = 0

    const connect = () => {
      if (!mounted) return

      // 清理上一次连接
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
      }

      const cleanup = sessionApi.streamSessions(
        // onSessions
        (newSessions) => {
          if (!mounted) return
          retryCount = 0
          sseReceivedRef.current = true
          setSessions(newSessions)
          setLoading(false)
          setError(null)
        },
        // onError / onEnd
        (err) => {
          if (!mounted) return
          console.warn('[Sessions] SSE 断开:', err.message)

          if (retryCount >= RETRY_CONFIG.maxRetries) {
            console.error('[Sessions] 超过最大重试次数，停止重连')
            return
          }

          const delay = Math.min(
            RETRY_CONFIG.baseDelay * Math.pow(2, retryCount),
            RETRY_CONFIG.maxDelay,
          )
          retryCount++
          console.log(`[Sessions] ${delay}ms 后尝试重连（第 ${retryCount} 次）`)
          retryTimerRef.current = setTimeout(connect, delay)
        },
      )

      cleanupRef.current = cleanup
    }

    connect()

    return () => {
      mounted = false
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
      }
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
    }
  }, [])

  // ---------- 删除会话 ----------
  const deleteSession = useCallback(async (sessionId: string, adminApiKey?: string): Promise<boolean> => {
    try {
      await sessionApi.deleteSession(sessionId, adminApiKey)
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId))
      return true
    } catch {
      return false
    }
  }, [])

  return (
    <SessionsContext.Provider value={{sessions, loading, error, refresh, deleteSession}}>
      {children}
    </SessionsContext.Provider>
  )
}

// ==================== Hook ====================

/**
 * 获取会话列表数据的 Hook
 *
 * 必须在 <SessionsProvider> 内使用
 */
export function useSessions(): SessionsContextValue {
  const ctx = useContext(SessionsContext)
  if (!ctx) {
    throw new Error('useSessions 必须在 SessionsProvider 内使用')
  }
  return ctx
}

