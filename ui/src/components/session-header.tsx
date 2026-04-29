'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { SidebarTrigger, useSidebar } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { ChevronDown, ChevronRight, Download, FileSearchCorner, FileText, Folder } from 'lucide-react'
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
import { sessionApi } from '@/lib/api/session'
import { toast } from 'sonner'
import type { SessionFile } from '@/lib/api/types'
import { sessionFileToAttachment } from '@/lib/session-events'
import type { AttachmentFile } from '@/lib/session-events'

type FileTreeNode = {
  name: string
  path: string
  absolutePath: string
  folders: FileTreeNode[]
  files: SessionFile[]
}

function formatDisplayFilename(filename: string, keepChars = 40): string {
  const name = (filename || '').trim()
  if (!name) return ''
  const dot = name.lastIndexOf('.')
  if (dot <= 0 || dot === name.length - 1) {
    return name
  }
  const base = name.slice(0, dot)
  const ext = name.slice(dot)
  if (base.length <= keepChars) {
    return `${base}${ext}`
  }
  return `${base.slice(0, keepChars)}…${ext}`
}

export interface SessionHeaderProps {
  /** 会话 ID */
  sessionId?: string
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
  sessionId = '',
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
  const uniqueFileList = useMemo(() => {
    return fileList.reduce((acc, file) => {
      const key = file.filepath || file.filename
      const existingIndex = acc.findIndex(f => (f.filepath || f.filename) === key)

      if (existingIndex >= 0) {
        acc[existingIndex] = file
      } else {
        acc.push(file)
      }

      return acc
    }, [] as SessionFile[])
  }, [fileList])

  const buildFileTree = useCallback((items: SessionFile[]): FileTreeNode => {
    const root: FileTreeNode = { name: '', path: '', absolutePath: '', folders: [], files: [] }

    const ensureFolder = (parent: FileTreeNode, name: string, path: string, absolutePath: string) => {
      const existing = parent.folders.find((folder) => folder.path === path)
      if (existing) return existing
      const created: FileTreeNode = { name, path, absolutePath, folders: [], files: [] }
      parent.folders.push(created)
      parent.folders.sort((a, b) => a.name.localeCompare(b.name))
      return created
    }

    items.forEach((file) => {
      const rawPath = (file.filepath || file.filename || '').replace(/\\/g, '/').trim()
      const normalizedPath = rawPath.replace(/^\/+/, '')
      const isAbsolute = rawPath.startsWith('/')
      const segments = normalizedPath.split('/').filter(Boolean)
      const fallbackName = file.filename || '未命名文件'
      const filename = segments.length > 0 ? segments[segments.length - 1] : fallbackName
      const folderSegments = segments.length > 1 ? segments.slice(0, -1) : []

      let current = root
      let currentPath = ''
      let currentAbsolutePath = ''
      folderSegments.forEach((segment) => {
        currentPath = currentPath ? `${currentPath}/${segment}` : segment
        currentAbsolutePath = currentAbsolutePath
          ? `${currentAbsolutePath}/${segment}`
          : isAbsolute ? `/${segment}` : segment
        current = ensureFolder(current, segment, currentPath, currentAbsolutePath)
      })

      current.files.push({
        ...file,
        filename,
      })
      current.files.sort((a, b) => a.filename.localeCompare(b.filename))
    })

    return root
  }, [])

  const fileTree = useMemo(() => buildFileTree(uniqueFileList), [buildFileTree, uniqueFileList])
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({})
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadingFolderPath, setDownloadingFolderPath] = useState<string | null>(null)

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

  const handleFolderDownload = useCallback(async (folder: FileTreeNode, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!sessionId || !folder.absolutePath || downloadingFolderPath) return
    setDownloadingFolderPath(folder.path)
    try {
      const blob = await sessionApi.downloadSessionFolder(sessionId, folder.absolutePath)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${folder.name || 'folder'}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success(`已下载文件夹「${folder.name}」`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '下载失败'
      toast.error(`下载文件夹「${folder.name}」失败: ${msg}`)
    } finally {
      setDownloadingFolderPath(null)
    }
  }, [downloadingFolderPath, sessionId])

  const handleFileItemClick = useCallback((file: SessionFile) => {
    if (onFileClick) {
      onFileClick(sessionFileToAttachment(file))
      setOpenState(false)
    }
  }, [onFileClick, setOpenState])

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!openState) return
    setExpandedFolders((prev) => {
      const next = { ...prev }
      let changed = false
      const visit = (node: FileTreeNode, depth: number) => {
        node.folders.forEach((folder) => {
          if (prev[folder.path] === undefined) {
            next[folder.path] = depth < 2
            changed = true
          }
          visit(folder, depth + 1)
        })
      }
      visit(fileTree, 0)
      return changed ? next : prev
    })
  }, [fileTree, openState])

  const toggleFolder = useCallback((path: string) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [path]: !prev[path],
    }))
  }, [])

  const renderTree = useCallback((node: FileTreeNode, depth = 0) => {
    const folderItems = node.folders.map((folder) => {
      const isExpanded = expandedFolders[folder.path] ?? depth < 1
      const nestedCount = folder.files.length + folder.folders.length
      return (
        <div key={folder.path} className="flex flex-col gap-1">
          <div
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
            style={{ paddingLeft: `${depth * 16 + 8}px` }}
          >
            <button
              type="button"
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
              onClick={() => toggleFolder(folder.path)}
            >
              {isExpanded ? <ChevronDown className="size-4 text-gray-500" /> : <ChevronRight className="size-4 text-gray-500" />}
              <Folder className="size-4 text-amber-500" />
              <span className="flex-1 truncate">{folder.name}</span>
              <span className="text-xs text-gray-400">{nestedCount}</span>
            </button>
            <Button
              variant="ghost"
              size="icon-xs"
              className="cursor-pointer"
              onClick={(e) => handleFolderDownload(folder, e)}
              disabled={!sessionId || downloadingFolderPath === folder.path}
              aria-label={`下载文件夹 ${folder.name}`}
            >
              <Download />
            </Button>
          </div>
          {isExpanded ? renderTree(folder, depth + 1) : null}
        </div>
      )
    })

    const fileItems = node.files.map((file) => (
      <Item
        key={file.id}
        variant="default"
        className="p-2 w-full min-w-0 gap-2 cursor-pointer hover:bg-gray-100 border-0 shadow-none"
        style={{ paddingLeft: `${depth * 16 + 28}px` }}
        onClick={() => handleFileItemClick(file)}
      >
        <ItemMedia>
          <Avatar className="size-8">
            <AvatarGroupCount>
              <FileText />
            </AvatarGroupCount>
          </Avatar>
        </ItemMedia>
        <ItemContent className="gap-0 min-w-0">
          <ItemTitle className="text-sm text-gray-700 w-full min-w-0">
            <span className="block w-full truncate">
              {formatDisplayFilename(file.filename)}
            </span>
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

    return (
      <div className="flex flex-col gap-1">
        {folderItems}
        {fileItems}
      </div>
    )
  }, [downloadingFolderPath, downloadingId, expandedFolders, handleDownload, handleFileItemClick, handleFolderDownload, sessionId, toggleFolder])

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
                <div className="flex flex-col gap-2">
                  {uniqueFileList.length === 0 ? (
                    <p className="text-sm text-gray-500 py-4">暂无文件</p>
                  ) : (
                    <>
                      <div className="px-2 pb-1 text-xs text-gray-500">
                        共 {uniqueFileList.length} 个文件
                      </div>
                      {renderTree(fileTree)}
                    </>
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
