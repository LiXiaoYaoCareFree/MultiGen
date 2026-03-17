'use client'

/**
 * 会话列表 Hook
 *
 * 数据与 SSE 连接由 SessionsProvider 管理（放置在 root layout 中），
 * 本文件仅做 re-export，保持已有组件的 import 路径不变。
 */
export { useSessions } from '@/providers/sessions-provider'
