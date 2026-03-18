'use client'

import {useEffect, useMemo, useState} from 'react'
import {cn} from '@/lib/utils'
import {Button} from '@/components/ui/button'
import {getSuggestedQuestions} from '@/config/app.config'
import {configApi} from '@/lib/api/config'

interface SuggestedQuestionsProps {
  className?: string
  onQuestionClick?: (question: string) => void
}

function sanitizeQuestion(text: string): string {
  return text.replace(/[「」]/g, '').replace(/\s+/g, ' ').trim()
}

export function SuggestedQuestions({className, onQuestionClick}: SuggestedQuestionsProps) {
  const fallbackQuestions = useMemo(() => getSuggestedQuestions(4).map(sanitizeQuestion), [])
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>(fallbackQuestions)

  useEffect(() => {
    let cancelled = false
    const updateQuestions = () => {
      configApi.getSuggestedQuestions(4)
        .then((data) => {
          if (cancelled) return
          const list = Array.isArray(data?.questions)
            ? data.questions
              .filter((q) => typeof q === 'string' && q.trim())
              .map((q) => sanitizeQuestion(q))
              .filter((q) => q.length > 0)
            : []
          if (list.length > 0) {
            setSuggestedQuestions(list.slice(0, 4))
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSuggestedQuestions(fallbackQuestions)
          }
        })
    }
    updateQuestions()
    const timer = window.setInterval(() => {
      if (!cancelled) {
        updateQuestions()
      }
    }, 60 * 60 * 1000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [fallbackQuestions])

  const handleClick = (question: string) => {
    onQuestionClick?.(question)
  }

  return (
    <div className={cn('flex flex-wrap gap-2 sm:gap-3', className)}>
      {suggestedQuestions.map((question, index) => (
        <Button
          key={index}
          variant="outline"
          className="cursor-pointer text-xs sm:text-sm whitespace-normal break-words"
          onClick={() => handleClick(question)}
        >
          {question}
        </Button>
      ))}
    </div>
  )
}
