import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'

export interface TourPage {
  selector: string
  body: string
}

export interface TourStep {
  title: string
  pages: TourPage[]
  /** Runs when this step becomes active (e.g. switch the right panel tab). */
  onEnter?: () => void
}

interface EditorTourProps {
  steps: TourStep[]
  onClose: () => void
}

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

// One page flattened out of the step/page tree, with its position for traversal.
interface Entry {
  si: number
  pi: number
  selector: string
  body: string
  title: string
  pageCount: number
}

// Padding around the highlighted region, in px (a 4px-grid multiple).
const SPOTLIGHT_PAD = 8
// Gap between the spotlight ring and the popover card.
const CARD_GAP = 12
const CARD_WIDTH = 300

function readRect(selector: string): Rect | null {
  const el = document.querySelector(selector)
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) return null
  return { top: r.top, left: r.left, width: r.width, height: r.height }
}

function flatten(steps: TourStep[]): Entry[] {
  const out: Entry[] = []
  steps.forEach((step, si) => {
    step.pages.forEach((page, pi) => {
      out.push({
        si,
        pi,
        selector: page.selector,
        body: page.body,
        title: step.title,
        pageCount: step.pages.length,
      })
    })
  })
  return out
}

/** First entry index at or after `from` whose target element exists. */
function nextValidIndex(entries: Entry[], from: number): number {
  for (let i = from; i < entries.length; i++) {
    if (readRect(entries[i].selector)) return i
  }
  return -1
}

/** Last entry index at or before `from` whose target element exists. */
function prevValidIndex(entries: Entry[], from: number): number {
  for (let i = from; i >= 0; i--) {
    if (readRect(entries[i].selector)) return i
  }
  return -1
}

export function EditorTour({ steps, onClose }: EditorTourProps) {
  const entries = useMemo(() => flatten(steps), [steps])
  const [index, setIndex] = useState(() => Math.max(0, nextValidIndex(entries, 0)))
  const [rect, setRect] = useState<Rect | null>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const lastStepRef = useRef<number>(-1)

  const entry = entries[index]
  const isFirst = index === 0
  const isLast = index === entries.length - 1

  const recompute = useCallback(() => {
    if (!entry) return
    const r = readRect(entry.selector)
    if (r) {
      setRect(r)
    } else {
      // Target vanished (layout change). Move forward to the next valid entry,
      // or close if none remain.
      const fwd = nextValidIndex(entries, index + 1)
      if (fwd === -1) onClose()
      else setIndex(fwd)
    }
  }, [entry, entries, index, onClose])

  // Run the step's onEnter when the step changes, then re-measure after the
  // panel content (e.g. a tab swap) has had a chance to lay out.
  useEffect(() => {
    if (!entry) return
    if (entry.si !== lastStepRef.current) {
      lastStepRef.current = entry.si
      steps[entry.si]?.onEnter?.()
      const t = window.setTimeout(recompute, 50)
      return () => window.clearTimeout(t)
    }
  }, [entry, steps, recompute])

  // Measure on mount and whenever the entry changes, before paint.
  useLayoutEffect(() => {
    recompute()
  }, [recompute])

  // Keep the spotlight aligned when the viewport changes.
  useEffect(() => {
    window.addEventListener('resize', recompute)
    window.addEventListener('scroll', recompute, true)
    return () => {
      window.removeEventListener('resize', recompute)
      window.removeEventListener('scroll', recompute, true)
    }
  }, [recompute])

  // Move keyboard focus to the primary control on each step.
  useEffect(() => {
    nextRef.current?.focus()
  }, [index])

  // Escape skips the walkthrough. Clicking the dim area does nothing.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!entry || !rect) return null

  function goBack() {
    const back = prevValidIndex(entries, index - 1)
    if (back !== -1) setIndex(back)
  }

  function goNext() {
    if (isLast) {
      onClose()
      return
    }
    const fwd = nextValidIndex(entries, index + 1)
    if (fwd === -1) onClose()
    else setIndex(fwd)
  }

  // Spotlight ring geometry.
  const ringTop = rect.top - SPOTLIGHT_PAD
  const ringLeft = rect.left - SPOTLIGHT_PAD
  const ringWidth = rect.width + SPOTLIGHT_PAD * 2
  const ringHeight = rect.height + SPOTLIGHT_PAD * 2

  // Card placement: below the target by default, above when there is no room.
  const vh = window.innerHeight
  const vw = window.innerWidth
  const spaceBelow = vh - (ringTop + ringHeight)
  const placeBelow = spaceBelow > 180
  const cardTop = placeBelow
    ? ringTop + ringHeight + CARD_GAP
    : Math.max(CARD_GAP, ringTop - CARD_GAP - 180)
  // Align the card's left edge with the target, clamped to the viewport.
  const cardLeft = Math.min(Math.max(CARD_GAP, ringLeft), vw - CARD_WIDTH - CARD_GAP)

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Editor walkthrough"
      className="fixed inset-0 z-[60]"
    >
      {/* Spotlight ring: a single element whose huge spread shadow dims the rest
          of the screen, leaving the target region clear. Static, no animation. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed rounded-lg border-2 border-brand-400 transition-all duration-150"
        style={{
          top: ringTop,
          left: ringLeft,
          width: ringWidth,
          height: ringHeight,
          boxShadow: '0 0 0 9999px rgba(26, 26, 26, 0.6)',
        }}
      />

      {/* Coachmark card. */}
      <div
        className="fixed rounded-lg bg-neutral-0 p-4 shadow-xl transition-all duration-150"
        style={{ top: cardTop, left: cardLeft, width: CARD_WIDTH }}
      >
        <h2 className="text-sm font-semibold text-neutral-900">{entry.title}</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-neutral-600">{entry.body}</p>

        {entry.pageCount > 1 && (
          <div className="mt-3 flex items-center gap-1.5" aria-hidden="true">
            {Array.from({ length: entry.pageCount }).map((_, i) => (
              <span
                key={i}
                className={
                  i === entry.pi
                    ? 'h-1.5 w-1.5 rounded-full bg-brand-400'
                    : 'h-1.5 w-1.5 rounded-full bg-neutral-200'
                }
              />
            ))}
          </div>
        )}

        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs tabular-nums text-neutral-500">
            Step {entry.si + 1} of {steps.length}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              aria-label="Skip the walkthrough"
            >
              Skip
            </Button>
            {!isFirst && (
              <Button variant="outline" size="sm" onClick={goBack} aria-label="Previous step">
                Back
              </Button>
            )}
            <Button
              ref={nextRef}
              size="sm"
              onClick={goNext}
              aria-label={isLast ? 'Finish the walkthrough' : 'Next step'}
            >
              {isLast ? 'Done' : 'Next'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
