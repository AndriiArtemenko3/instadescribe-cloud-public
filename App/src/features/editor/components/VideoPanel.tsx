import { useRef, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { AdGap, AudioEvent, Scene } from '@/types'
import type { SceneCollision } from '@/lib/collisions'

function formatTime(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

interface VideoPanelProps {
  projectId: string
  videoSrc?: string
  duration: number
  scenes: Scene[]
  adGaps: AdGap[]
  audioEvents: AudioEvent[]
  collisions: Record<number, SceneCollision>
  currentTime: number
  onSeek: (secs: number) => void
  onTimeUpdate: (secs: number) => void
}

export function VideoPanel({
  videoSrc,
  duration,
  scenes,
  adGaps,
  audioEvents,
  collisions,
  currentTime,
  onSeek,
  onTimeUpdate,
}: VideoPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0
  const conflictCount = scenes.filter((s) => collisions[s.id]?.collides).length

  // Sync external currentTime (scene click) → video element
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    if (Math.abs(video.currentTime - currentTime) > 0.5) {
      video.currentTime = currentTime
    }
  }, [currentTime])

  function handleTimelineClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    const t = Math.max(0, Math.min(duration, ratio * duration))
    onSeek(t)
    if (videoRef.current) videoRef.current.currentTime = t
  }

  return (
    <div className="flex h-full flex-1 flex-col overflow-hidden">
      {/* Video area */}
      <div className="flex flex-1 items-center justify-center bg-neutral-950" data-tour="video-player">
        {videoSrc ? (
          <video
            ref={videoRef}
            src={videoSrc}
            className="h-full w-full object-contain"
            controls
            onTimeUpdate={(e) => onTimeUpdate(e.currentTarget.currentTime)}
          />
        ) : (
          <div className="flex flex-col items-center gap-3 text-neutral-500">
            <span className="text-sm">Video preview unavailable</span>
            <span className="text-xs text-neutral-600">Connect pipeline output to enable playback</span>
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="flex h-10 shrink-0 items-center gap-4 border-t border-neutral-200 bg-neutral-0 px-4">
        <span className="font-mono text-xs text-neutral-500 tabular-nums">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
        <div className="flex-1" />
        <span className="flex items-center gap-1 text-xs text-neutral-400">
          {adGaps.length} AD gaps · {audioEvents.length} audio events
          {conflictCount > 0 && (
            <span className="ml-1 flex items-center gap-1 font-medium text-danger-400">
              <AlertTriangle size={13} strokeWidth={2} />
              {conflictCount} {conflictCount === 1 ? 'conflict' : 'conflicts'}
            </span>
          )}
        </span>
      </div>

      {/* Timeline strip */}
      <div className="shrink-0 border-t border-neutral-200 bg-neutral-0 px-4 py-2" data-tour="video-timeline">
        {/* Dialogue / silence track */}
        <div className="relative mb-1 h-[18px] w-full overflow-hidden rounded-sm bg-neutral-150">
          {audioEvents.map((ev) => {
            const left = duration > 0 ? (ev.startSecs / duration) * 100 : 0
            const width = duration > 0 ? (ev.durationSecs / duration) * 100 : 0
            return (
              <div
                key={ev.id}
                className={
                  ev.type === 'dialogue'
                    ? 'absolute top-0 h-full bg-info-400 opacity-40'
                    : ev.type === 'music'
                    ? 'absolute top-0 h-full bg-warning-400 opacity-30'
                    : 'absolute top-0 h-full bg-neutral-300 opacity-40'
                }
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            )
          })}
          {/* Conflict markers: the span where a scene's narration talks over dialogue. */}
          {scenes.map((scene) => {
            const collision = collisions[scene.id]
            if (!collision?.collides || duration <= 0) return null
            if (collision.overlapStart === null || collision.overlapEnd === null) return null
            const left = (collision.overlapStart / duration) * 100
            const width = ((collision.overlapEnd - collision.overlapStart) / duration) * 100
            if (width <= 0) return null
            return (
              <div
                key={`overrun-${scene.id}`}
                className="absolute top-0 h-full bg-danger-400 opacity-50"
                style={{ left: `${left}%`, width: `${width}%` }}
                title={`Scene ${scene.sceneNumber} narration talks over dialogue for ~${collision.overlapSecs.toFixed(1)}s.`}
              />
            )
          })}
        </div>

        {/* AD gap track — clickable */}
        <div
          className="relative h-[18px] w-full cursor-pointer overflow-hidden rounded-sm bg-neutral-150"
          onClick={handleTimelineClick}
        >
          {adGaps.map((gap) => {
            const left = duration > 0 ? (gap.startSecs / duration) * 100 : 0
            const width = duration > 0 ? (gap.durationSecs / duration) * 100 : 0
            return (
              <div
                key={gap.id}
                className={
                  gap.isRecommended
                    ? 'absolute top-0 h-full bg-brand-400 opacity-60'
                    : 'absolute top-0 h-full bg-brand-200 opacity-40'
                }
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            )
          })}
          <div
            className="absolute top-0 h-full w-0.5 bg-neutral-900 opacity-70"
            style={{ left: `${progress}%` }}
          />
        </div>

        <div className="mt-1 flex items-center gap-4">
          <span className="flex items-center gap-1 text-xs text-neutral-400">
            <span className="inline-block h-2 w-3 rounded-sm bg-info-400 opacity-60" />
            Dialogue
          </span>
          <span className="flex items-center gap-1 text-xs text-neutral-400">
            <span className="inline-block h-2 w-3 rounded-sm bg-brand-400 opacity-70" />
            AD gap
          </span>
          {conflictCount > 0 && (
            <span className="flex items-center gap-1 text-xs text-neutral-400">
              <span className="inline-block h-2 w-3 rounded-sm bg-danger-400 opacity-50" />
              Overrun
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
