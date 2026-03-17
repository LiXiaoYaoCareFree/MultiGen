'use client'

import { useCallback, useEffect, useState } from 'react'
import { fileApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Download, FileText, X } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { formatFileSize } from '@/lib/utils'
import { toast } from 'sonner'
import type { AttachmentFile } from '@/lib/session-events'

export interface FilePreviewPanelProps {
  /** 要预览的文件信息 */
  file: AttachmentFile | null
  /** 关闭回调 */
  onClose: () => void
}

/**
 * 判断文件类型是否支持预览
 * - 文本类：txt, md, json, xml, csv, log, js, ts, tsx, jsx, py, java, go, rs, etc.
 * - 图片类：jpg, jpeg, png, gif, svg, webp, bmp
 */
function isSupportedFileType(extension: string): { type: 'text' | 'image' | 'unsupported' } {
  const ext = extension.toLowerCase().replace(/^\./, '')
  
  // 文本类文件
  const textExtensions = [
    'txt', 'md', 'markdown', 'json', 'xml', 'html', 'htm', 'css', 'scss', 'sass', 'less',
    'js', 'jsx', 'ts', 'tsx', 'vue', 'py', 'java', 'go', 'rs', 'c', 'cpp', 'h', 'hpp',
    'cs', 'php', 'rb', 'swift', 'kt', 'scala', 'sh', 'bash', 'zsh', 'yml', 'yaml',
    'toml', 'ini', 'conf', 'config', 'log', 'csv', 'sql', 'r', 'dart', 'lua', 'perl',
  ]
  
  // 图片类文件
  const imageExtensions = [
    'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico',
  ]
  
  if (textExtensions.includes(ext)) {
    return { type: 'text' }
  }
  
  if (imageExtensions.includes(ext)) {
    return { type: 'image' }
  }
  
  return { type: 'unsupported' }
}

export function FilePreviewPanel({ file, onClose }: FilePreviewPanelProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)

  const fileType = file ? isSupportedFileType(file.extension) : { type: 'unsupported' as const }

  // 加载文件内容
  const loadFileContent = useCallback(async (fileId: string, type: 'text' | 'image' | 'unsupported') => {
    if (type === 'unsupported') {
      return
    }

    setLoading(true)
    setError(null)
    setContent(null)
    setImageUrl(null)

    try {
      if (type === 'image') {
        // 图片类型：生成预览 URL
        const blob = await fileApi.downloadFile(fileId)
        const url = URL.createObjectURL(blob)
        setImageUrl(url)
      } else {
        // 文本类型：读取内容
        const blob = await fileApi.downloadFile(fileId)
        const text = await blob.text()
        setContent(text)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载文件内容失败'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  // 下载文件
  const handleDownload = useCallback(async () => {
    if (!file) return
    
    try {
      const blob = await fileApi.downloadFile(file.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已下载「${file.filename}」`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '下载失败'
      toast.error(`下载失败: ${msg}`)
    }
  }, [file])

  // 当文件改变时加载内容
  useEffect(() => {
    if (file && file.id) {
      loadFileContent(file.id, fileType.type)
    }
  }, [file, fileType.type, loadFileContent])

  // 清理函数：关闭时释放资源
  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl)
      }
    }
  }, [imageUrl])

  if (!file) {
    return null
  }

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* 头部：文件名 + 操作按钮 - 添加背景色区分 */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-100 text-blue-600">
            <FileText size={16} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-gray-900 truncate">{file.filename}</p>
            <p className="text-xs text-gray-500">
              {file.extension.replace(/^\./, '')} · {formatFileSize(file.size)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleDownload}
            aria-label="下载文件"
            className="cursor-pointer"
          >
            <Download size={16} />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="关闭"
            className="cursor-pointer"
          >
            <X size={16} />
          </Button>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-hidden">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-gray-500">加载中...</p>
          </div>
        )}

        {error && !loading && (
          <div className="flex items-center justify-center h-full px-6">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {!loading && !error && fileType.type === 'unsupported' && (
          <div className="flex flex-col items-center justify-center h-full px-6 gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 text-gray-400">
              <FileText size={32} />
            </div>
            <div className="text-center">
              <p className="text-sm text-gray-700 font-medium">暂不支持预览此文件类型</p>
              <p className="text-xs text-gray-500 mt-1">您可以下载文件后查看</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              className="gap-2"
            >
              <Download size={16} />
              下载文件
            </Button>
          </div>
        )}

        {!loading && !error && fileType.type === 'image' && imageUrl && (
          <ScrollArea className="h-full">
            <div className="p-4">
              <img 
                src={imageUrl} 
                alt={file.filename}
                className="max-w-full h-auto rounded-lg border"
              />
            </div>
          </ScrollArea>
        )}

        {!loading && !error && fileType.type === 'text' && content !== null && (
          <ScrollArea className="h-full">
            <pre className="p-4 text-xs font-mono whitespace-pre-wrap break-words text-gray-700">
              {content}
            </pre>
          </ScrollArea>
        )}
      </div>
    </div>
  )
}
