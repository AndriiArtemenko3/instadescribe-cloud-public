import { describe, it, expect } from 'vitest'
import type { Scene, AudioEvent, AdGap } from '@/types'
import {
  estimateSpeechSecs,
  sceneGapSecs,
  getSceneCollision,
  canSmartFill,
} from './collisions'

const makeScene = (p: Partial<Scene> = {}): Scene => ({
  id: 1,
  sceneNumber: 1,
  startSecs: 0,
  endSecs: 10,
  durationSecs: 10,
  text: '',
  template: '',
  characterIds: [],
  locked: false,
  needsReview: false,
  active: true,
  voiceSpeed: 1,
  ...p,
})

const makeEvent = (p: Partial<AudioEvent> = {}): AudioEvent => ({
  id: 1,
  type: 'dialogue',
  startSecs: 0,
  endSecs: 1,
  durationSecs: 1,
  ...p,
})

const makeGap = (p: Partial<AdGap> = {}): AdGap => ({
  id: 1,
  startSecs: 0,
  endSecs: 1,
  durationSecs: 1,
  isRecommended: true,
  ...p,
})

const words = (n: number) => Array.from({ length: n }, () => 'word').join(' ')

describe('estimateSpeechSecs', () => {
  it('returns 0 for empty or whitespace text', () => {
    expect(estimateSpeechSecs('')).toBe(0)
    expect(estimateSpeechSecs('   ')).toBe(0)
  })

  it('estimates ~0.4s per word at speed 1', () => {
    expect(estimateSpeechSecs(words(5))).toBeCloseTo(2.0)
    expect(estimateSpeechSecs(words(10))).toBeCloseTo(4.0)
  })

  it('compresses by playback speed', () => {
    expect(estimateSpeechSecs(words(10), 2)).toBeCloseTo(2.0)
  })

  it('treats a non-positive speed as 1', () => {
    expect(estimateSpeechSecs(words(10), 0)).toBeCloseTo(4.0)
  })
})

describe('sceneGapSecs', () => {
  const scene = makeScene({ startSecs: 10, endSecs: 20 })

  it('returns 0 when no gap intersects', () => {
    expect(sceneGapSecs(scene, [makeGap({ startSecs: 30, endSecs: 40 })])).toBe(0)
  })

  it('returns the largest overlapping gap span', () => {
    const gaps = [
      makeGap({ id: 1, startSecs: 14, endSecs: 18 }), // 4s overlap
      makeGap({ id: 2, startSecs: 11, endSecs: 12 }), // 1s overlap
    ]
    expect(sceneGapSecs(scene, gaps)).toBeCloseTo(4.0)
  })
})

describe('getSceneCollision', () => {
  it('reports a collision when narration overruns dialogue beyond tolerance', () => {
    const scene = makeScene({ startSecs: 10, endSecs: 20, text: words(15) }) // est 6.0s, ad 10.25..16.25
    const events = [makeEvent({ type: 'dialogue', startSecs: 11, endSecs: 13 })]
    const gaps = [makeGap({ startSecs: 14, endSecs: 18 })] // 4s borrowable

    const c = getSceneCollision(scene, events, gaps)
    expect(c.collides).toBe(true)
    expect(c.overlapSecs).toBeCloseTo(2.0)
    expect(c.overlapStart).toBeCloseTo(11)
    expect(c.overlapEnd).toBeCloseTo(13)
    expect(c.canFill).toBe(true) // gap 4.0 >= 1.5 and est 6.0 > 4.0
  })

  it('ignores sub-half-second overlaps as rounding', () => {
    const scene = makeScene({ startSecs: 0, endSecs: 10, text: words(5) }) // est 2.0s, ad 0.25..2.25
    const events = [makeEvent({ type: 'dialogue', startSecs: 2.0, endSecs: 2.5 })] // 0.25s overlap
    expect(getSceneCollision(scene, events, []).collides).toBe(false)
  })

  it('never collides for an inactive scene', () => {
    const scene = makeScene({ startSecs: 10, endSecs: 20, text: words(15), active: false })
    const events = [makeEvent({ type: 'dialogue', startSecs: 11, endSecs: 13 })]
    const c = getSceneCollision(scene, events, [])
    expect(c.collides).toBe(false)
    expect(c.overlapSecs).toBe(0)
  })

  it('only counts dialogue events', () => {
    const scene = makeScene({ startSecs: 10, endSecs: 20, text: words(15) })
    const events = [makeEvent({ type: 'music', startSecs: 11, endSecs: 13 })]
    expect(getSceneCollision(scene, events, []).collides).toBe(false)
  })

  it('does not allow Smart Fill when no usable gap exists', () => {
    const scene = makeScene({ startSecs: 10, endSecs: 20, text: words(15) })
    const events = [makeEvent({ type: 'dialogue', startSecs: 11, endSecs: 13 })]
    const c = getSceneCollision(scene, events, []) // no gaps → gapSecs 0
    expect(c.collides).toBe(true)
    expect(c.canFill).toBe(false)
  })
})

describe('canSmartFill', () => {
  it('is false for null/undefined', () => {
    expect(canSmartFill(null)).toBe(false)
    expect(canSmartFill(undefined)).toBe(false)
  })

  it('passes through the canFill flag', () => {
    const scene = makeScene({ startSecs: 10, endSecs: 20, text: words(15) })
    const events = [makeEvent({ type: 'dialogue', startSecs: 11, endSecs: 13 })]
    const gaps = [makeGap({ startSecs: 14, endSecs: 18 })]
    expect(canSmartFill(getSceneCollision(scene, events, gaps))).toBe(true)
  })
})
