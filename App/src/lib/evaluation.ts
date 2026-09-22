import type { AudioEvent, Scene } from '@/types'

// AD-quality evaluation — a mirror of modular_pipeline/evaluation.py so the editor
// can show live quality scores with no round-trip and no model call. The two
// implementations are pinned to one expected score by tests/fixtures/eval_sample.json.

export const SECS_PER_WORD = 0.4
export const AD_START_OFFSET = 0.25
export const COLLISION_TOLERANCE = 0.5

export const WEIGHTS = {
  timing: 0.25,
  dialogue_safety: 0.3,
  coverage: 0.15,
  character_consistency: 0.15,
  grounding: 0.15,
} as const

export type Dimension = keyof typeof WEIGHTS
export type IssueCode =
  | 'narration_too_long'
  | 'dialogue_collision'
  | 'orphan_character'
  | 'duplicate_text'

export interface SceneFlag {
  sceneId: string
  issues: IssueCode[]
}

export interface EvalReport {
  overall: number
  dimensions: Record<Dimension, number>
  flags: SceneFlag[]
  activeCount: number
}

const norm = (text: string | undefined): string =>
  (text ?? '').trim().toLowerCase().replace(/\s+/g, ' ')

const round4 = (x: number): number => Math.round(x * 1e4) / 1e4

export function estimateSpeechSecs(text: string | undefined, speed = 1): number {
  const words = norm(text).split(' ').filter(Boolean)
  if (words.length === 0) return 0
  const safeSpeed = speed > 0 ? speed : 1
  return (words.length * SECS_PER_WORD) / safeSpeed
}

function dialogueOverlap(adStart: number, adEnd: number, audioEvents: AudioEvent[]): number {
  let total = 0
  for (const ev of audioEvents) {
    if (ev.type !== 'dialogue') continue
    const start = Math.max(adStart, ev.startSecs)
    const end = Math.min(adEnd, ev.endSecs)
    if (end > start) total += end - start
  }
  return total
}

export function evaluateAd(
  scenes: Scene[],
  audioEvents: AudioEvent[],
  entities: { id: string }[],
  durationSecs: number,
): EvalReport {
  const entityIds = new Set(entities.map((e) => e.id))
  const active = scenes.filter((s) => s.active && norm(s.text).length > 0)
  const n = active.length

  const emptyDims = {
    timing: 0,
    dialogue_safety: 0,
    coverage: 0,
    character_consistency: 0,
    grounding: 0,
  }
  if (n === 0) return { overall: 0, dimensions: emptyDims, flags: [], activeCount: 0 }

  const textCounts = new Map<string, number>()
  for (const s of active) {
    const key = norm(s.text)
    textCounts.set(key, (textCounts.get(key) ?? 0) + 1)
  }

  let timingOk = 0
  let safe = 0
  let consistent = 0
  let duplicates = 0
  let covered = 0
  const dur = durationSecs > 0 ? durationSecs : null
  const flags: SceneFlag[] = []

  for (const s of active) {
    const issues: IssueCode[] = []
    const start = s.startSecs
    const end = s.endSecs
    const est = estimateSpeechSecs(s.text, s.voiceSpeed ?? 1)

    if (est <= Math.max(0, end - start)) timingOk += 1
    else issues.push('narration_too_long')

    const adStart = start + AD_START_OFFSET
    if (dialogueOverlap(adStart, adStart + est, audioEvents) > COLLISION_TOLERANCE)
      issues.push('dialogue_collision')
    else safe += 1

    const charIds = s.characterIds ?? []
    if (charIds.every((cid) => entityIds.has(cid))) consistent += 1
    else issues.push('orphan_character')

    if ((textCounts.get(norm(s.text)) ?? 0) > 1) {
      duplicates += 1
      issues.push('duplicate_text')
    }

    if (dur) covered += Math.max(0, Math.min(end, dur) - start)

    if (issues.length) flags.push({ sceneId: String(s.sceneNumber ?? s.id), issues })
  }

  const dimensions: Record<Dimension, number> = {
    timing: timingOk / n,
    dialogue_safety: safe / n,
    coverage: dur ? Math.min(1, covered / dur) : 0,
    character_consistency: consistent / n,
    grounding: 1 - duplicates / n,
  }
  const overall = (Object.keys(WEIGHTS) as Dimension[]).reduce(
    (sum, k) => sum + dimensions[k] * WEIGHTS[k],
    0,
  )

  const rounded = Object.fromEntries(
    (Object.keys(dimensions) as Dimension[]).map((k) => [k, round4(dimensions[k])]),
  ) as Record<Dimension, number>

  return { overall: round4(overall), dimensions: rounded, flags, activeCount: n }
}
