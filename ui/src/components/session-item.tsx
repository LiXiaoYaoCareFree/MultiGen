'use client'

import {useCallback, useEffect, useState} from 'react'
import {CircuitBoard, Loader2, MoreHorizontal, Trash} from 'lucide-react'
import {Button} from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {Item, ItemActions, ItemContent, ItemDescription, ItemMedia} from '@/components/ui/item'
import {Avatar, AvatarGroupCount} from '@/components/ui/avatar'
import {formatRelativeDate} from '@/lib/utils'
import type {Session} from '@/lib/api'

type SessionItemProps = {
  session: Session
  isActive: boolean
  onClick: (sessionId: string) => void
  onDelete: (session: Session) => void
}

/**
 * 单个会话列表项
 * 展示会话标题、描述、时间及操作菜单
 */
export function SessionItem({session, isActive, onClick, onDelete}: SessionItemProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const handleClick = useCallback(() => {
    onClick(session.session_id)
  }, [onClick, session.session_id])

  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete(session)
  }, [onDelete, session])

  const description = session.latest_message || '暂无消息'
  const dateLabel = formatRelativeDate(session.latest_message_at)
  const isRunning = session.status === 'running' || session.status === 'waiting'

  return (
    <Item
      className={`p-2 hover:bg-white cursor-pointer gap-2 items-start ${isActive ? 'bg-white' : ''}`}
      onClick={handleClick}
    >
      {/* 左侧图标 */}
      <ItemMedia>
        <Avatar className="size-8">
          <AvatarGroupCount>
            {isRunning
              ? <Loader2 className="animate-spin"/>
              : <CircuitBoard/>
            }
          </AvatarGroupCount>
        </Avatar>
      </ItemMedia>
      {/* 中间内容 */}
      <ItemContent className="gap-0 min-w-0">
        <p className="text-sm font-medium truncate">
          {session.title || '新任务'}
        </p>
        <p className="text-xs text-muted-foreground truncate">
          {description}
        </p>
      </ItemContent>
      {/* 右侧操作区 */}
      <ItemActions className="flex flex-col pt-0.5 gap-0 self-start">
        <ItemDescription className="text-xs whitespace-nowrap">{dateLabel}</ItemDescription>
        {mounted && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon-xs"
                variant="ghost"
                className="cursor-pointer"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal/>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" side="bottom">
              <DropdownMenuItem
                variant="destructive"
                className="cursor-pointer"
                onClick={handleDelete}
              >
                <Trash/>
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </ItemActions>
    </Item>
  )
}


