'use client'

import {useState} from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {Button} from '@/components/ui/button'
import {Input} from '@/components/ui/input'

type DeleteSessionDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (adminApiKey?: string) => Promise<void>
}

/**
 * 删除任务确认弹窗
 * 确认后才发起 API 删除请求
 */
export function DeleteSessionDialog({open, onOpenChange, onConfirm}: DeleteSessionDialogProps) {
  const [deleting, setDeleting] = useState(false)
  const [adminApiKey, setAdminApiKey] = useState('')

  const handleConfirm = async () => {
    setDeleting(true)
    try {
      await onConfirm(adminApiKey || undefined)
    } finally {
      setDeleting(false)
    }
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setAdminApiKey('')
    }
    onOpenChange(isOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">
            要删除任务信息吗？
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground leading-relaxed">
            删除任务信息后，该任务下的所有聊天记录将被永远删除，无法找回，所上传的文件与生成文件均无法查看&下载。
          </DialogDescription>
        </DialogHeader>
        <div className="py-2">
          <label className="text-sm font-medium">管理员密钥（可选）</label>
          <Input
            type="password"
            placeholder="请输入管理员密钥"
            value={adminApiKey}
            onChange={(e) => setAdminApiKey(e.target.value)}
            className="mt-1"
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            className="cursor-pointer"
            onClick={() => onOpenChange(false)}
            disabled={deleting}
          >
            取消
          </Button>
          <Button
            className="cursor-pointer"
            onClick={handleConfirm}
            disabled={deleting}
          >
            {deleting ? '删除中...' : '确认'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
