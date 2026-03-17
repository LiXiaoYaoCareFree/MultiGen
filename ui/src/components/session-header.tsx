'use client'

import { useCallback, useEffect, useState } from 'react'
import { SidebarTrigger, useSidebar } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { Download, FileSearchCorner, FileText } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item'
import { Avatar, AvatarGroupCount } from '@/components/ui/avatar'
import { formatFileSize } from '@/lib/utils'
import { fileApi } from '@/lib/api'
import { toast } from 'sonner'
import type { SessionFile } from '@/lib/api/types'
import { sessionFileToAttachment } from '@/lib/session-events'
import type { AttachmentFile } from '@/lib/session-events'

export interface SessionHeaderProps {
  /** 任务/会话标题 */
  title?: string
  /** 此任务下的文件列表（用于「此任务中所有文件」弹窗） */
  files?: SessionFile[]
  /** 受控：文件列表弹窗是否打开（用于从页面其他处打开，如「查看此任务中所有的文件」） */
  fileListOpen?: boolean
  /** 受控：文件列表弹窗打开状态变更 */
  onFileListOpenChange?: (open: boolean) => void
  /** 当文件列表对话框打开时的回调，用于刷新文件列表 */
  onFetchFiles?: () => void | Promise<void>
  /** 点击文件时的预览回调 */
  onFileClick?: (file: AttachmentFile) => void
}

export function SessionHeader({
  title = '',
  files,
  fileListOpen,
  onFileListOpenChange,
  onFetchFiles,
  onFileClick,
}: SessionHeaderProps) {
  const { open, isMobile } = useSidebar()
  const [mounted, setMounted] = useState(false)
  const [internalOpen, setInternalOpen] = useState(false)
  const isControlled = fileListOpen !== undefined
  const openState = isControlled ? fileListOpen : internalOpen
  const setOpenState = useCallback((v: boolean) => {
    if (isControlled) {
      onFileListOpenChange?.(v)
    } else {
      setInternalOpen(v)
    }
    // 当对话框打开时，触发文件列表刷新
    if (v && onFetchFiles) {
      onFetchFiles()
    }
  }, [isControlled, onFileListOpenChange, onFetchFiles])

  const fileList = Array.isArray(files) ? files : []
  
  // 对相同 filepath 的文件进行去重，保留最新的（数组中最后一个）
  const uniqueFileList = fileList.reduce((acc, file) => {
    // 使用 filepath 作为去重的 key，如果为空则使用 filename
    const key = file.filepath || file.filename
    const existingIndex = acc.findIndex(f => (f.filepath || f.filename) === key)
    
    if (existingIndex >= 0) {
      // 如果已存在，替换为当前文件（保留最新的）
      acc[existingIndex] = file
    } else {
      // 如果不存在，添加到结果中
      acc.push(file)
    }
    
    return acc
  }, [] as SessionFile[])
  
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const handleDownload = useCallback(async (file: SessionFile, e: React.MouseEvent) => {
    e.stopPropagation()
    if (downloadingId) return
    setDownloadingId(file.id)
    try {
      const blob = await fileApi.downloadFile(file.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = file.filename || `file-${file.id}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已下载「${file.filename}」`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '下载失败'
      toast.error(`下载「${file.filename}」失败: ${msg}`)
    } finally {
      setDownloadingId(null)
    }
  }, [downloadingId])

  const handleFileItemClick = useCallback((file: SessionFile) => {
    if (onFileClick) {
      onFileClick(sessionFileToAttachment(file))
      setOpenState(false)
    }
  }, [onFileClick, setOpenState])

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <header className="bg-[#f8f8f7] flex flex-row items-center justify-between pt-3 pb-2 gap-2 sticky top-0 z-10 flex-shrink-0">
      {(!open || isMobile) && <SidebarTrigger className="cursor-pointer flex-shrink-0" />}
      <div className="text-gray-700 text-lg whitespace-nowrap text-ellipsis overflow-hidden flex-1 min-w-0">
        {title || '未命名任务'}
      </div>
      {mounted ? (
        <Dialog open={openState} onOpenChange={setOpenState}>
          <DialogTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="cursor-pointer flex-shrink-0">
              <FileSearchCorner />
            </Button>
          </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>此任务中的所有文件</DialogTitle>
              </DialogHeader>
              <ScrollArea className="h-[500px]">
                <div className="flex flex-col gap-1">
                  {uniqueFileList.length === 0 ? (
                    <p className="text-sm text-gray-500 py-4">暂无文件</p>
                  ) : (
                    uniqueFileList.map((file) => (
                      <Item
                        key={file.id}
                        variant="default"
                        className="p-2 flex-shrink-0 gap-2 cursor-pointer hover:bg-gray-100"
                        onClick={() => handleFileItemClick(file)}
                      >
                        <ItemMedia>
                          <Avatar className="size-8">
                            <AvatarGroupCount>
                              <FileText />
                            </AvatarGroupCount>
                          </Avatar>
                        </ItemMedia>
                        <ItemContent className="gap-0">
                          <ItemTitle className="text-sm text-gray-700">
                            {file.filename}
                          </ItemTitle>
                          <ItemDescription className="text-xs">
                            {file.extension.replace(/^\./, '')} · {formatFileSize(file.size)}
                          </ItemDescription>
                        </ItemContent>
                        <ItemActions>
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            className="cursor-pointer"
                            onClick={(e) => handleDownload(file, e)}
                            disabled={downloadingId === file.id}
                            aria-label={`下载 ${file.filename}`}
                          >
                            <Download />
                          </Button>
                        </ItemActions>
                      </Item>
                    ))
                  )}
                </div>
              </ScrollArea>
          </DialogContent>
        </Dialog>
      ) : (
        <Button variant="ghost" size="icon-sm" className="cursor-pointer flex-shrink-0">
          <FileSearchCorner />
        </Button>
      )}
    </header>
  )
}