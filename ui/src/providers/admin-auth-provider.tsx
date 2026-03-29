'use client'

import React, {createContext, useCallback, useContext, useMemo, useState} from 'react'
import {Button} from '@/components/ui/button'
import {Input} from '@/components/ui/input'
import {ADMIN_AUTH_CONFIG, ADMIN_AUTH_STORAGE_KEY} from '@/config/auth.config'

type AdminAuthContextValue = {
  isLoginRequired: boolean
  isAuthenticated: boolean
  login: (password: string) => boolean
  logout: () => void
}

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

export function AdminAuthProvider({children}: { children: React.ReactNode }) {
  const [adminApiKey, setAdminApiKey] = useState(() => {
    if (!ADMIN_AUTH_CONFIG.loginRequired) {
      return ADMIN_AUTH_CONFIG.password
    }
    if (typeof window === 'undefined') {
      return ''
    }
    return sessionStorage.getItem(ADMIN_AUTH_STORAGE_KEY) || ''
  })
  const isAuthenticated = !ADMIN_AUTH_CONFIG.loginRequired || Boolean(adminApiKey)

  const login = useCallback((password: string) => {
    const nextAdminApiKey = password.trim()
    if (!nextAdminApiKey) {
      return false
    }
    if (ADMIN_AUTH_CONFIG.password && nextAdminApiKey !== ADMIN_AUTH_CONFIG.password) {
      return false
    }
    sessionStorage.setItem(ADMIN_AUTH_STORAGE_KEY, nextAdminApiKey)
    setAdminApiKey(nextAdminApiKey)
    return true
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(ADMIN_AUTH_STORAGE_KEY)
    setAdminApiKey('')
  }, [])

  const value = useMemo(
    () => ({
      isLoginRequired: ADMIN_AUTH_CONFIG.loginRequired,
      isAuthenticated,
      login,
      logout,
    }),
    [isAuthenticated, login, logout],
  )

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export function useAdminAuth(): AdminAuthContextValue {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) {
    throw new Error('useAdminAuth 必须在 AdminAuthProvider 内使用')
  }
  return ctx
}

export function AdminAuthGate({children}: { children: React.ReactNode }) {
  const {isLoginRequired, isAuthenticated, login} = useAdminAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleLogin = (event: React.FormEvent) => {
    event.preventDefault()
    if (!login(password)) {
      setError('管理员密钥不能为空或不正确')
      return
    }
    setPassword('')
    setError('')
  }

  if (!isLoginRequired) {
    return <>{children}</>
  }

  if (!isAuthenticated) {
    return (
      <div className="h-screen bg-[#f8f8f7] flex items-center justify-center px-4">
        <form
          onSubmit={handleLogin}
          className="w-full max-w-md bg-white rounded-xl border p-6 shadow-sm space-y-4"
        >
          <div className="space-y-1">
            <h1 className="text-xl font-semibold text-gray-800">管理员登录</h1>
            <p className="text-sm text-muted-foreground">登录后可访问会话管理与对话功能</p>
          </div>
          <Input
            type="password"
            placeholder="请输入管理员密钥"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
              if (error) {
                setError('')
              }
            }}
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <Button type="submit" className="w-full cursor-pointer">
            登录
          </Button>
        </form>
      </div>
    )
  }

  return <>{children}</>
}
