'use client'

import { useEffect, useRef } from 'react'
import RFB from '@novnc/novnc/lib/rfb'

export type VNCStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface VNCViewerProps {
  url: string
  viewOnly?: boolean
  onStatusChange?: (status: VNCStatus, detail?: string) => void
}

export function VNCViewer({ url, viewOnly, onStatusChange }: VNCViewerProps) {
  const displayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!displayRef.current) return

    onStatusChange?.('connecting')

    let rfb: RFB | null = null
    try {
      rfb = new RFB(displayRef.current, url, {
        credentials: { password: '', username: '', target: '' },
      })

      rfb.viewOnly = viewOnly || false
      rfb.scaleViewport = true
      rfb.background = '#000'

      rfb.addEventListener('connect', () => onStatusChange?.('connected'))
      rfb.addEventListener('disconnect', (e: CustomEvent) => {
        if (e.detail?.clean) {
          onStatusChange?.('disconnected', '连接已断开')
        } else {
          onStatusChange?.('error', '沙箱环境可能已关闭或连接异常断开')
        }
      })
      rfb.addEventListener('securityfailure', () => {
        onStatusChange?.('error', '认证失败，无法连接到沙箱')
      })
    } catch {
      onStatusChange?.('error', '无法建立连接，沙箱环境可能未启动')
    }

    return () => {
      try { rfb?.disconnect() } catch { /* noop */ }
    }
  }, [url, viewOnly, onStatusChange])

  return (
    <div
      ref={displayRef}
      style={{ width: '100%', height: '100%', background: '#000' }}
    />
  )
}
