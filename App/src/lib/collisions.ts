import type { Scene, AdGap, AudioEvent } from '@/types'

// Dialogue-collision model.
//
// Each audio-description line is voiced starting just after its scene begins
// (the export mux places it at scene.start + 0.25s) and runs for as long as the
// narration takes to read. A collision is when that spoken window overlaps real
// dialogue, so the description talks over what characters are saying. Smart Fill
// fixes a collision by shortening the line into the silence a curated AD gap
// offers, so it stays disabled when no such gap sits near the scene.

const AD_START_OFFSET = 0.25      // seconds; mirrors the server export mux offset
const MIN_FILL_GAP = 1.5          // seconds; below this, shortening can't yield usable AD
const COLLISION_TOLERANCE = 0.5   // seconds; ignore sub-half-second overlaps as rounding

export interface SceneCollision {
  collides: boolean
  estSecs: number
  gapSecs: number              // silence a curated AD gap lends this scene (Smart Fill target)
  overlapSecs: number          // total seconds the narration talks over dialogue
  overlapStart: number | null  // span of the worst overlap, for the timeline marker
  overlapEnd: number | null
  canFill: boolean
}

// Estimate spoken duration in seconds. Heuristic: narration averages ~150
// words/min, i.e. ~0.4s per word; a faster playback speed compresses it.
export function estimateSpeechSecs(text: string, speed = 1): number {
  const words = text.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return 0
  const safeSpeed = speed > 0 ? speed : 1
  return (words.length * 0.4) / safeSpeed
}

// The largest silence a scene can borrow from a curated AD gap: the biggest
// overlap between the scene window and any gap. Returns 0 when none intersects.
// This is the duration Smart Fill rewrites the line down to.
export function sceneGapSecs(scene: Scene, adGaps: AdGap[]): number {
  let best = 0
  for (const gap of adGaps) {
    const overlap = Math.min(scene.endSecs, gap.endSecs) - Math.max(scene.startSecs, gap.startSecs)
    if (overlap > best) best = overlap
  }
  return best
}

// Resolve whether an active scene's narration would talk over dialogue, and
// whether a curated gap gives Smart Fill room to fix it.
export function getSceneCollision(
  scene: Scene,
  audioEvents: AudioEvent[],
  adGaps: AdGap[],
): SceneCollision {
  const estSecs = estimateSpeechSecs(scene.text, scene.voiceSpeed)
  const gapSecs = sceneGapSecs(scene, adGaps)

  const adStart = scene.startSecs + AD_START_OFFSET
  const adEnd = adStart + estSecs

  let overlapSecs = 0
  let overlapStart: number | null = null
  let overlapEnd: number | null = null
  // Only an active scene with narration can collide; inactive scenes are excluded
  // from the export, so they carry no warning.
  if (scene.active && estSecs > 0) {
    for (const ev of audioEvents) {
      if (ev.type !== 'dialogue') continue
      const start = Math.max(adStart, ev.startSecs)
      const end = Math.min(adEnd, ev.endSecs)
      if (end > start) {
        overlapSecs += end - start
        overlapStart = overlapStart === null ? start : Math.min(overlapStart, start)
        overlapEnd = overlapEnd === null ? end : Math.max(overlapEnd, end)
      }
    }
  }

  const collides = overlapSecs > COLLISION_TOLERANCE
  const canFill = collides && gapSecs >= MIN_FILL_GAP && estSecs > gapSecs

  return { collides, estSecs, gapSecs, overlapSecs, overlapStart, overlapEnd, canFill }
}

// Smart Fill helps only when the line collides AND a curated gap exists to shrink
// it into. When the surrounding moment is wall-to-wall dialogue, shortening can't
// rescue it and the button stays disabled.
export function canSmartFill(collision: SceneCollision | null | undefined): boolean {
  return !!collision && collision.canFill
}
