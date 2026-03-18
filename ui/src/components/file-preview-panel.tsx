'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
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
type PreviewType = 'text' | 'image' | 'video' | 'audio' | 'model' | 'pdf' | 'unsupported'

function getPreviewType(extension: string): PreviewType {
  const ext = extension.toLowerCase().replace(/^\./, '')
  const textExtensions = [
    'txt', 'md', 'markdown', 'json', 'xml', 'html', 'htm', 'css', 'scss', 'sass', 'less',
    'js', 'jsx', 'ts', 'tsx', 'vue', 'py', 'java', 'go', 'rs', 'c', 'cpp', 'h', 'hpp',
    'cs', 'php', 'rb', 'swift', 'kt', 'scala', 'sh', 'bash', 'zsh', 'yml', 'yaml',
    'toml', 'ini', 'conf', 'config', 'log', 'csv', 'sql', 'r', 'dart', 'lua', 'perl'
  ]
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico']
  const videoExtensions = ['mp4', 'webm', 'mov', 'm4v', 'mkv', 'avi']
  const audioExtensions = ['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac', 'opus']
  const modelExtensions = ['glb', 'gltf', 'obj', 'stl', 'fbx', 'ply', 'usdz']
  if (textExtensions.includes(ext)) return 'text'
  if (imageExtensions.includes(ext)) return 'image'
  if (videoExtensions.includes(ext)) return 'video'
  if (audioExtensions.includes(ext)) return 'audio'
  if (modelExtensions.includes(ext)) return 'model'
  if (ext === 'pdf') return 'pdf'
  return 'unsupported'
}

export function FilePreviewPanel({ file, onClose }: FilePreviewPanelProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const extension = useMemo(() => {
    if (!file) return ''
    const fromField = (file.extension || '').replace(/^\./, '').trim()
    if (fromField) return fromField
    const ext = file.filename.split('.').pop() || ''
    return ext.toLowerCase()
  }, [file])
  const previewType = getPreviewType(extension)

  const clearPreviewObjectUrl = useCallback((url: string | null) => {
    if (url?.startsWith('blob:')) {
      URL.revokeObjectURL(url)
    }
  }, [])

  const loadFileContent = useCallback(async (fileId: string, type: PreviewType) => {
    setLoading(true)
    setError(null)
    setContent(null)
    setPreviewUrl((prev) => {
      clearPreviewObjectUrl(prev)
      return null
    })

    try {
      if (type === 'text') {
        const blob = await fileApi.downloadFile(fileId)
        setContent(await blob.text())
      } else if (type === 'image' || type === 'video' || type === 'audio' || type === 'pdf') {
        const blob = await fileApi.downloadFile(fileId)
        setPreviewUrl(URL.createObjectURL(blob))
      } else if (type === 'model') {
        const modelUrl = fileApi.getFileDownloadUrl(fileId)
        setPreviewUrl(`https://modelviewer.dev/editor/#model=${encodeURIComponent(modelUrl)}`)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载文件内容失败'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [clearPreviewObjectUrl])

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

  useEffect(() => {
    if (file && file.id) {
      loadFileContent(file.id, previewType)
    }
  }, [file, previewType, loadFileContent])

  useEffect(() => {
    return () => {
      clearPreviewObjectUrl(previewUrl)
    }
  }, [previewUrl, clearPreviewObjectUrl])

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
              {extension || 'unknown'} · {formatFileSize(file.size)}
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

        {!loading && !error && previewType === 'unsupported' && (
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

        {!loading && !error && previewType === 'image' && previewUrl && (
          <ScrollArea className="h-full">
            <div className="p-4">
              <img 
                src={previewUrl} 
                alt={file.filename}
                className="max-w-full h-auto rounded-lg border"
              />
            </div>
          </ScrollArea>
        )}

        {!loading && !error && previewType === 'video' && previewUrl && (
          <div className="h-full p-4">
            <video src={previewUrl} controls className="w-full h-full rounded-lg border bg-black" />
          </div>
        )}

        {!loading && !error && previewType === 'audio' && previewUrl && (
          <div className="h-full p-6 flex items-center justify-center">
            <audio src={previewUrl} controls className="w-full max-w-2xl" />
          </div>
        )}

        {!loading && !error && previewType === 'pdf' && previewUrl && (
          <div className="h-full p-2">
            <iframe src={previewUrl} className="w-full h-full rounded-lg border" title={file.filename} />
          </div>
        )}

        {!loading && !error && previewType === 'model' && previewUrl && (
          <div className="h-full p-2">
            <iframe src={previewUrl} className="w-full h-full rounded-lg border" title={file.filename} />
          </div>
        )}

        {!loading && !error && previewType === 'text' && content !== null && (
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
