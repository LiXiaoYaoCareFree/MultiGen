'use client'

import {cn} from '@/lib/utils'
import {Button} from '@/components/ui/button'
import {suggestedQuestions} from '@/config/app.config'

interface SuggestedQuestionsProps {
  className?: string
  onQuestionClick?: (question: string) => void
}

export function SuggestedQuestions({className, onQuestionClick}: SuggestedQuestionsProps) {
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