import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StepIndicatorProps {
  step: number
  total: number
}

export function StepIndicator({ step, total }: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-0 px-8 py-6">
      {Array.from({ length: total }, (_, i) => {
        const n = i + 1
        const done = n < step
        const active = n === step
        return (
          <div key={n} className="flex items-center">
            {i > 0 && (
              <div className={cn('h-0.5 w-16 sm:w-24', done ? 'bg-success-400' : 'bg-neutral-200')} />
            )}
            <div className={cn(
              'flex h-7 w-7 items-center justify-center rounded-full border-2 transition-colors',
              done  ? 'border-success-400 bg-success-400 text-white' :
              active ? 'border-neutral-900 bg-neutral-900 text-white' :
                       'border-neutral-200 bg-white text-neutral-400',
            )}>
              {done ? <Check size={13} strokeWidth={2.5} /> : (
                <span className="text-xs font-semibold">{n}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
