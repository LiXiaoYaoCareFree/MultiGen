'use client'

import { cn, formatFileSize } from '@/lib/utils'
import { FileSearch, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { AttachmentFile } from '@/lib/session-events'

export interface AttachmentsMessageProps {
  className?: string
  role: 'user' | 'assistant'
  files: AttachmentFile[]
  onViewAllFiles?: () => void
  onFileClick?: (file: AttachmentFile) => void
}

const CARD_WIDTH = 280
const CARD_HEIGHT = 72

function FileCard({
  file,
  index,
  sizeLabel,
  role,
  onClick,
}: {
  file: AttachmentFile
  index: number
  sizeLabel: string
  role: 'user' | 'assistant'
  onClick?: () => void
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 flex-shrink-0 cursor-pointer hover:bg-gray-50 transition-colors',
        role === 'user' && 'bg-white'
      )}
      style={{ width: CARD_WIDTH, height: CARD_HEIGHT }}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      }}
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-100 text-blue-600">
        <FileText size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {file.filename}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {file.extension} · {sizeLabel}
        </p>
      </div>
    </div>
  )
}

export function AttachmentsMessage({
  className,
  role,
  files,
  onViewAllFiles,
  onFileClick,
}: AttachmentsMessageProps) {
  const sizeLabel = (f: AttachmentFile) =>
    f.sizeLabel ?? formatFileSize(f.size)

  if (role === 'user') {
    return (
      <div
        className={cn(
          'flex flex-col flex-wrap gap-2 items-end justify-end',
          className
        )}
      >
        <div className="flex gap-2 flex-wrap max-w-[568px] justify-end">
          {files.map((file, index) => (
            <FileCard
              key={file.id ? `${file.id}-${index}` : `file-${index}`}
              file={file}
              index={index}
              sizeLabel={sizeLabel(file)}
              role="user"
              onClick={() => onFileClick?.(file)}
            />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn('flex flex-col justify-start', className)}
    >
      <div className="flex items-center gap-3 flex-wrap max-w-[600px]">
        {files.map((file, index) => (
          <FileCard
            key={file.id ? `${file.id}-${index}` : `file-${index}`}
            file={file}
            index={index}
            sizeLabel={sizeLabel(file)}
            role="assistant"
            onClick={() => onFileClick?.(file)}
          />
        ))}
        {onViewAllFiles && (
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 py-2 px-3 border border-gray-200 bg-white hover:bg-gray-50 text-gray-600 gap-2 rounded-lg cursor-pointer"
            style={{ width: CARD_WIDTH, height: CARD_HEIGHT }}
            onClick={onViewAllFiles}
          >
            <FileSearch size={18} className="shrink-0" />
            <span className="text-sm whitespace-nowrap">
              查看此任务中所有的文件
            </span>
          </Button>
        )}
      </div>
    </div>
  )
}