'use client'

import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

export interface MarkdownContentProps {
  content: string
  className?: string
}

/**
 * remark-gfm autolink 对紧跟 CJK 字符的 URL 边界检测不准确，
 * 会将 `https://example.com，后续中文` 整段识别为链接。
 * 在 URL 与相邻 CJK 字符/标点之间插入空格修正边界。
 */
const CJK_RANGES = '\u3000-\u303F\u4E00-\u9FFF\uFF01-\uFF60'
const URL_FOLLOWED_BY_CJK = new RegExp(
  `(https?:\\/\\/[^\\s${CJK_RANGES}]+)([${CJK_RANGES}])`,
  'g',
)

function normalizeAutolinks(text: string): string {
  return text.replace(URL_FOLLOWED_BY_CJK, '$1 $2')
}

const headingClasses: Record<string, string> = {
  h1: 'text-lg font-semibold mt-4 mb-2 first:mt-0 text-gray-900',
  h2: 'text-base font-semibold mt-3 mb-1.5 first:mt-0 text-gray-900',
  h3: 'text-sm font-semibold mt-2.5 mb-1 first:mt-0 text-gray-800',
  h4: 'text-sm font-medium mt-2 mb-1 first:mt-0 text-gray-800',
  h5: 'text-sm font-medium mt-1.5 mb-0.5 first:mt-0 text-gray-700',
  h6: 'text-sm font-medium mt-1 mb-0.5 first:mt-0 text-gray-700',
}

const components: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  h1: ({ node, className, ...props }) => (
    <h1 className={cn(headingClasses.h1, className)} {...props} />
  ),
  h2: ({ node, className, ...props }) => (
    <h2 className={cn(headingClasses.h2, className)} {...props} />
  ),
  h3: ({ node, className, ...props }) => (
    <h3 className={cn(headingClasses.h3, className)} {...props} />
  ),
  h4: ({ node, className, ...props }) => (
    <h4 className={cn(headingClasses.h4, className)} {...props} />
  ),
  h5: ({ node, className, ...props }) => (
    <h5 className={cn(headingClasses.h5, className)} {...props} />
  ),
  h6: ({ node, className, ...props }) => (
    <h6 className={cn(headingClasses.h6, className)} {...props} />
  ),
  p: ({ node, className, ...props }) => (
    <p className={cn('text-sm text-gray-700 leading-relaxed mb-2 last:mb-0', className)} {...props} />
  ),
  ul: ({ node, className, ...props }) => (
    <ul className={cn('text-sm text-gray-700 list-disc pl-5 mb-2 space-y-0.5', className)} {...props} />
  ),
  ol: ({ node, className, ...props }) => (
    <ol className={cn('text-sm text-gray-700 list-decimal pl-5 mb-2 space-y-0.5', className)} {...props} />
  ),
  li: ({ node, className, ...props }) => (
    <li className={cn('leading-relaxed', className)} {...props} />
  ),
  strong: ({ node, className, ...props }) => (
    <strong className={cn('font-semibold text-gray-900', className)} {...props} />
  ),
  code: ({ node, className, children, ...props }) => {
    const text = typeof children === 'string' ? children : ''
    const isBlock = text.includes('\n')
    return (
      <code
        className={cn(
          isBlock
            ? 'block p-3 rounded-md bg-gray-100 text-gray-800 text-sm font-mono overflow-x-auto my-2'
            : 'inline px-1.5 py-0.5 rounded bg-gray-100 text-gray-800 text-[0.8125em] font-mono',
          className
        )}
        {...props}
      >
        {children}
      </code>
    )
  },
  pre: ({ node, className, ...props }) => (
    <pre className={cn('my-2 overflow-x-auto', className)} {...props} />
  ),
  blockquote: ({ node, className, ...props }) => (
    <blockquote
      className={cn(
        'border-l-4 border-gray-200 pl-3 py-0.5 my-2 text-sm text-gray-600 italic',
        className
      )}
      {...props}
    />
  ),
  a: ({ node, className, href, children, ...props }) => {
    // 安全兜底：如果 href 包含 CJK 字符，说明 autolink 仍然误判，降级为纯文本
    if (href && /[\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF]/.test(href)) {
      return <span className="text-sm text-gray-700">{children}</span>
    }
    return (
      <a
        className={cn('text-sm text-blue-600 hover:underline', className)}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    )
  },
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  const normalized = useMemo(() => normalizeAutolinks(content), [content])

  return (
    <div className={cn('markdown-content break-words', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {normalized}
      </ReactMarkdown>
    </div>
  )
}
