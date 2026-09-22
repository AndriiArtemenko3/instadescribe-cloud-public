import { cn } from '@/lib/utils'

export type RightPanelTab = 'script' | 'characters' | 'quality'

const TABS: { id: RightPanelTab; label: string }[] = [
  { id: 'script',     label: 'Script' },
  { id: 'characters', label: 'Characters' },
  { id: 'quality',    label: 'Quality' },
]

interface Props {
  active: RightPanelTab
  onChange: (tab: RightPanelTab) => void
}

export function RightPanelTabs({ active, onChange }: Props) {
  return (
    <div role="tablist" className="flex h-10 shrink-0 items-stretch border-b border-neutral-200 bg-neutral-0">
      {TABS.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            'flex-1 px-4 text-xs font-medium transition-colors',
            active === t.id
              ? 'border-b-2 border-brand-400 text-neutral-900'
              : 'border-b-2 border-transparent text-neutral-500 hover:text-neutral-900',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
