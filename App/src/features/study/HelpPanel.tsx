import { Sparkles, CheckCircle2, Circle, PlayCircle } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { STUDY_TASKS } from './studyTasks'

interface HelpPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onReplayTour: () => void
  taskDone: Record<string, boolean>
}

export function HelpPanel({ open, onOpenChange, onReplayTour, taskDone }: HelpPanelProps) {
  const doneCount = STUDY_TASKS.filter((t) => taskDone[t.id]).length
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Help &amp; guide</SheetTitle>
          <SheetDescription>
            A reminder of what audio description is and what to do here.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-6 overflow-y-auto px-4 pb-4">
          {/* Friendly explainer with a guide avatar. */}
          <section className="flex gap-3">
            <Avatar size="lg" className="shrink-0">
              <AvatarFallback className="bg-brand-50 text-brand-500">
                <Sparkles size={18} />
              </AvatarFallback>
            </Avatar>
            <div className="text-sm leading-relaxed text-neutral-600">
              <p className="font-medium text-neutral-900">What is audio description?</p>
              <p className="mt-1">
                Audio description is short spoken narration that tells a blind or
                low-vision listener what is happening on screen. It fits in the quiet
                gaps between dialogue. Your job is to make each line clear enough that
                someone can follow the story with their eyes closed.
              </p>
            </div>
          </section>

          {/* Guided steps. Each item ticks green as the visitor tries it. */}
          <section>
            <div className="flex items-baseline justify-between">
              <h3 className="text-sm font-semibold text-neutral-900">Try it</h3>
              <span className="text-xs tabular-nums text-neutral-500">
                {doneCount} / {STUDY_TASKS.length} done
              </span>
            </div>
            <ul className="mt-2 space-y-2">
              {STUDY_TASKS.map((task) => {
                const done = taskDone[task.id]
                return (
                  <li key={task.id} className="flex gap-2 text-sm">
                    {done ? (
                      <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-success-400" aria-hidden="true" />
                    ) : (
                      <Circle size={16} className="mt-0.5 shrink-0 text-neutral-300" aria-hidden="true" />
                    )}
                    <span className={done ? 'text-neutral-400' : 'text-neutral-700'}>
                      {task.label}
                      {task.note && (
                        <span className="mt-0.5 block text-xs italic text-neutral-400">{task.note}</span>
                      )}
                    </span>
                  </li>
                )
              })}
            </ul>
          </section>

          <Button variant="outline" className="gap-2 self-start" onClick={onReplayTour}>
            <PlayCircle size={16} />
            Replay walkthrough
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
