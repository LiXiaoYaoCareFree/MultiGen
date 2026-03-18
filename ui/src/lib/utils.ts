import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const WEEK_DAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'] as const

/**
 * 将日期字符串格式化为相对日期标签
 * - 今天 → "今天"
 * - 昨天 → "昨天"
 * - 本周内 → "周一"..."周六"
 * - 更早 → "MM/DD"
 */
export function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '今天'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return '今天'
  const now = new Date()

  // 归一化到当天 0:00
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return WEEK_DAYS[date.getDay()]

  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}/${day}`
}

/**
 * 格式化文件大小
 * @param bytes 文件大小（字节）
 * @returns 格式化后的文件大小字符串，如 "2.52 MB"
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`
}
