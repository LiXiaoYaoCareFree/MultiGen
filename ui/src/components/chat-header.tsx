'use client'

import Link from 'next/link'
import {SidebarTrigger, useSidebar} from '@/components/ui/sidebar'
import {LlmopsSettings} from '@/components/llmops-settings'
import {Button} from '@/components/ui/button'
import {LogOut} from 'lucide-react'
import {useAdminAuth} from '@/providers/admin-auth-provider'

export function ChatHeader() {
  const {open, isMobile} = useSidebar()
  const {isLoginRequired, isAuthenticated, logout} = useAdminAuth()

  return (
    <header className="flex justify-between items-center w-full py-2 px-4 z-50">
      {/* 左侧操作&logo */}
      <div className="flex items-center gap-2">
        {/* 面板操作按钮: 关闭面板&移动端下会显示 */}
        {(!open || isMobile) && <SidebarTrigger className="cursor-pointer"/>}
        {/* Logo占位符 */}
        <Link href="/" className="block bg-white w-[80px] h-9 rounded-md"/>
      </div>
      <div className="flex items-center gap-2">
        {isLoginRequired && isAuthenticated && (
          <Button
            variant="outline"
            size="sm"
            className="cursor-pointer"
            onClick={logout}
          >
            <LogOut className="size-4"/>
            退出登录
          </Button>
        )}
        <LlmopsSettings/>
      </div>
    </header>
  )
}
