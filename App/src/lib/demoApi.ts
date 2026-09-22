// Zero-API demo backend. When the build is produced with VITE_DEMO_MODE=1, the
// write/render endpoints in api.ts route here instead of hitting Flask/OpenAI.
// Reads stay static (api.ts already fetches scenes/audio/entities from /data).
// Nothing here needs a key, a server, or ffmpeg.

import { useAppStore } from '@/store/appStore'
import type {
  ExportFmt,
  ExportStatus,
  ScenePatch,
  ServerOverridesMap,
  SmartFillResult,
  VoiceId,
} from './api'

// ─── In-memory, ephemeral scene overrides (per project, reset on refresh) ──────
// A tutorial visitor can edit freely; nothing persists server-side and there is
// nothing to corrupt or clean up.
const overrides = new Map<string, ServerOverridesMap>()

export function demoFetchOverrides(projectId: string): Promise<ServerOverridesMap> {
  return Promise.resolve(overrides.get(projectId) ?? {})
}

export function demoPatchScene(
  projectId: string,
  sceneNumber: number,
  patch: ScenePatch,
): Promise<void> {
  const map = overrides.get(projectId) ?? {}
  const key = `scene_${sceneNumber}`
  map[key] = { ...map[key], ...patch }
  overrides.set(projectId, map)
  return Promise.resolve()
}

// Entity rename re-renders captions server-side in the live app; in the demo we
// keep it a no-op so the editor stays stable. Tutorials that teach renaming wait
// for the baked-fixture path.
export function demoPatchEntity(): Promise<void> {
  return Promise.resolve()
}

// ─── Smart Fill — deterministic local shortening, no model call ────────────────
// AD is delivered at ~2.3 words/sec; trim to fit the time budget while keeping the
// leading clause. Honest and useful without a backend.
const WORDS_PER_SEC = 2.3

export function demoSmartFill(
  _projectId: string,
  text: string,
  targetSecs: number,
): Promise<SmartFillResult> {
  const budget = Math.max(3, Math.round(targetSecs * WORDS_PER_SEC))
  const words = text.trim().split(/\s+/).filter(Boolean)
  const kept = words.slice(0, budget)
  let ad = kept.join(' ')
  if (kept.length < words.length) ad = ad.replace(/[,;:]?$/, '') + '.'
  return Promise.resolve({
    ad,
    target_secs: targetSecs,
    target_words: budget,
    estimated_secs: Math.round((kept.length / WORDS_PER_SEC) * 100) / 100,
    model: 'demo (local)',
  })
}

// ─── Voice preview — committed mp3 if baked, else a short silence fallback ──────
function projectDataPath(projectId: string): string | null {
  return useAppStore.getState().projects.find((p) => p.id === projectId)?.dataPath ?? null
}

export async function demoPreviewTts(
  projectId: string,
  sceneNumber: number,
  voice: VoiceId,
): Promise<Blob> {
  const dataPath = projectDataPath(projectId)
  if (dataPath) {
    // Optional baked preview: /data/<id>/tts/scene_<n>_<voice>.mp3
    const url = `${dataPath}/tts/scene_${sceneNumber}_${voice}.mp3`
    const res = await fetch(url).catch(() => null)
    if (res?.ok) return res.blob()
  }
  const silence = await fetch('/demo/silence.mp3').catch(() => null)
  if (silence?.ok) return silence.blob()
  return new Blob([], { type: 'audio/mpeg' })
}

// ─── Export / eyes-closed preview — serve the pre-baked described video ─────────
export function demoRequestExport(
  _projectId: string,
  _voice: VoiceId,
  format: ExportFmt,
): Promise<{ exportId: string; format: ExportFmt }> {
  return Promise.resolve({ exportId: 'demo', format })
}

export function demoPollExport(): Promise<ExportStatus> {
  return Promise.resolve({
    status: 'ready',
    progress: 100,
    stage: 'complete',
    download_url: 'demo',
  })
}

export function demoExportUrl(projectId: string): string {
  const dataPath = projectDataPath(projectId)
  // The committed, AD-mixed render for this clip; falls back to the source video.
  return dataPath
    ? `${dataPath}/export.mp4`
    : (useAppStore.getState().projects.find((p) => p.id === projectId)?.videoFile ?? '')
}
