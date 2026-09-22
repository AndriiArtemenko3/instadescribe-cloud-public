import { useMemo } from 'react'
import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AudioEvent, Entity, Scene } from '@/types'
import { type Dimension, type IssueCode, evaluateAd } from '@/lib/evaluation'
import { RightPanelTabs, type RightPanelTab } from './RightPanelTabs'

const DIM_LABELS: Record<Dimension, string> = {
  timing: 'Timing fit',
  dialogue_safety: 'Dialogue safety',
  coverage: 'Coverage',
  character_consistency: 'Character consistency',
  grounding: 'Grounding',
}

const ISSUE_LABELS: Record<IssueCode, string> = {
  narration_too_long: 'Narration is too long for its time window',
  dialogue_collision: 'Narration talks over dialogue',
  orphan_character: 'References a character with no entity',
  duplicate_text: 'Duplicate of another description',
}

interface QualityPanelProps {
  scenes: Scene[]
  audioEvents: AudioEvent[]
  entities: Entity[]
  activeTab: RightPanelTab
  onTabChange: (tab: RightPanelTab) => void
  onSelectScene: (sceneId: number) => void
}

const pct = (v: number): number => Math.round(v * 100)

function barColor(v: number): string {
  if (v >= 0.8) return 'bg-success-400'
  if (v >= 0.5) return 'bg-brand-400'
  return 'bg-danger-500'
}

export function QualityPanel({
  scenes,
  audioEvents,
  entities,
  activeTab,
  onTabChange,
  onSelectScene,
}: QualityPanelProps) {
  const report = useMemo(() => {
    const duration = scenes.reduce((max, s) => Math.max(max, s.endSecs), 0)
    return evaluateAd(scenes, audioEvents, entities, duration)
  }, [scenes, audioEvents, entities])

  const sceneByFlagId = (flagId: string): Scene | undefined =>
    scenes.find((s) => String(s.sceneNumber ?? s.id) === flagId)

  return (
    <aside className="flex h-full w-script-panel shrink-0 flex-col border-l border-neutral-200 bg-neutral-0">
      <RightPanelTabs active={activeTab} onChange={onTabChange} />

      {report.activeCount === 0 ? (
        <div className="flex flex-1 items-center justify-center p-6 text-center">
          <p className="text-sm text-neutral-400">
            Activate a scene to score its description. Quality updates live as you edit —
            no AI call.
          </p>
        </div>
      ) : (
        <div className="flex-1 space-y-6 overflow-y-auto p-4">
          <section>
            <div className="flex items-baseline justify-between">
              <span className="text-xs font-medium text-neutral-500">Overall quality</span>
              <span className="text-3xl font-semibold tabular-nums text-neutral-900">
                {pct(report.overall)}
              </span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-neutral-200">
              <div
                className={cn('h-2 rounded-full transition-all', barColor(report.overall))}
                style={{ width: `${pct(report.overall)}%` }}
              />
            </div>
            <p className="mt-1.5 text-[11px] text-neutral-400">
              {report.activeCount} active description{report.activeCount === 1 ? '' : 's'} scored
              · computed locally, no model call
            </p>
          </section>

          <section className="space-y-3">
            {(Object.keys(DIM_LABELS) as Dimension[]).map((k) => (
              <div key={k}>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-neutral-600">{DIM_LABELS[k]}</span>
                  <span className="tabular-nums text-neutral-500">{pct(report.dimensions[k])}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-neutral-200">
                  <div
                    className={cn('h-1.5 rounded-full transition-all', barColor(report.dimensions[k]))}
                    style={{ width: `${pct(report.dimensions[k])}%` }}
                  />
                </div>
              </div>
            ))}
          </section>

          <section>
            {report.flags.length === 0 ? (
              <p className="flex items-center gap-2 text-xs text-success-400">
                <CheckCircle2 size={14} />
                No issues in the active descriptions.
              </p>
            ) : (
              <>
                <h3 className="flex items-center gap-1.5 text-xs font-medium text-neutral-500">
                  <AlertTriangle size={13} className="text-danger-500" />
                  {report.flags.length} issue{report.flags.length === 1 ? '' : 's'} to review
                </h3>
                <ul className="mt-2 space-y-1.5">
                  {report.flags.map((f) => {
                    const scene = sceneByFlagId(f.sceneId)
                    return (
                      <li key={f.sceneId}>
                        <button
                          onClick={() => scene && onSelectScene(scene.id)}
                          className="w-full rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-left transition-colors hover:border-brand-400"
                        >
                          <span className="text-xs font-medium text-neutral-700">
                            Scene {f.sceneId}
                          </span>
                          <ul className="mt-1 space-y-0.5">
                            {f.issues.map((issue) => (
                              <li key={issue} className="text-[11px] text-danger-500">
                                {ISSUE_LABELS[issue]}
                              </li>
                            ))}
                          </ul>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </>
            )}
          </section>
        </div>
      )}

      <div className="shrink-0 border-t border-neutral-200 p-4">
        <p className="text-[11px] leading-relaxed text-neutral-400">
          Five rubric dimensions, weighted. Timing and dialogue safety carry the most
          weight because a description that runs long or talks over dialogue fails the
          listener first.
        </p>
      </div>
    </aside>
  )
}
