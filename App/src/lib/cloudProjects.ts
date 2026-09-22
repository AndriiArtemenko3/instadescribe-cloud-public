// Cloud dashboard reconciliation (G7 Gate B2).
//
// GET /api/v1/jobs returns a map keyed by JOB id whose entries each carry the
// distinct durable projectId. Reconciliation:
//   - identifies existing store projects by entry.projectId (never the map key);
//   - retains the map-key jobId on the stored project;
//   - replaces cloud metadata from a successful authoritative snapshot;
//   - hides never-uploaded AWAITING_UPLOAD reservations while retaining an
//     explicitly source-verified/completion-pending job for same-job retry;
//   - uses the server created_at when present;
//   - is coalesced so React StrictMode double-mounts stay idempotent.
// Only durable identifiers and ordinary metadata are stored — never upload
// fields, presigned URLs, manifest bodies, tokens, or signed query strings.

import { useAppStore } from '@/store/appStore'
import { listCloudJobs, type CloudJobStatus } from './cloudApi'
import {
  getPortfolioSessionIdentity,
  isCurrentPortfolioSession,
  type PortfolioSessionIdentity,
} from './portfolioToken'
import type { Project } from '@/types'

const inFlightBySession = new Map<PortfolioSessionIdentity, Promise<void>>()
const reconciliationFenceBySession = new WeakMap<PortfolioSessionIdentity, number>()

/** Invalidate any jobs snapshot that started before a same-session cloud
    project mutation. This prevents an older AWAITING_UPLOAD response from
    hiding or regressing a card after upload completion was accepted. */
export function fenceCloudProjectReconciliation(): void {
  const identity = getPortfolioSessionIdentity()
  if (!identity) return
  reconciliationFenceBySession.set(
    identity,
    (reconciliationFenceBySession.get(identity) ?? 0) + 1,
  )
}

function toStatus(entry: CloudJobStatus, locallyUploaded: boolean): Project['status'] | null {
  switch (entry.canonicalState) {
    case 'UPLOAD_COMPLETE':
    case 'QUEUED':
    case 'PROCESSING':
    case 'EXPORT_QUEUED':
    case 'EXPORTING':
      return 'processing'
    case 'READY_FOR_REVIEW':
    case 'COMPLETED':
      return 'ready'
    case 'FAILED':
      return 'failed'
    case 'AWAITING_UPLOAD':
      return entry.sourceUploaded || locallyUploaded ? 'confirmation_pending' : null
    case 'CANCELLED':
      return null
  }
}

export async function reconcileCloudProjects(): Promise<void> {
  const identity = getPortfolioSessionIdentity()
  if (!identity || !useAppStore.getState().isAuthenticated) return
  const existing = inFlightBySession.get(identity)
  if (existing) return existing
  const startingFence = reconciliationFenceBySession.get(identity) ?? 0
  const request = (async () => {
    let map: Record<string, CloudJobStatus>
    try {
      map = await listCloudJobs()
    } catch {
      return // sanitized: reconciliation is best-effort and silent
    }
    const projects: Project[] = []
    const seenProjects = new Set<string>()
    const existingByProject = new Map(
      useAppStore.getState().projects.map((project) => [project.id, project]),
    )
    for (const [jobId, entry] of Object.entries(map)) {
      const existingProject = existingByProject.get(entry.projectId)
      // A successful S3 POST is client-observed durable evidence for this tab
      // even if the first verification request never produced a response.
      // Logout clears it; later sessions recover only the server marker.
      const locallyUploaded = existingProject?.jobId === jobId && existingProject.completionPending === true
      const status = toStatus(entry, locallyUploaded)
      if (status === null || seenProjects.has(entry.projectId)) continue
      seenProjects.add(entry.projectId)
      projects.push({
        id: entry.projectId, // durable product identity
        jobId, // the distinct processing-job identity (map key)
        name: entry.project_name || `Project ${entry.projectId.slice(0, 6)}`,
        status,
        completionPending: status === 'confirmation_pending' ? true : undefined,
        createdAt: entry.created_at ?? new Date().toISOString(),
        durationSecs: entry.duration_secs ?? undefined,
        model: entry.model ?? undefined,
        chunkSize: entry.chunk_size ?? undefined,
        starred: entry.starred,
      })
    }
    // A response belongs to the exact accepted token generation that started
    // it. Logout, token replacement, or a restored unauthenticated shell
    // invalidates it before any Zustand/sessionStorage mutation.
    if (
      !isCurrentPortfolioSession(identity) ||
      !useAppStore.getState().isAuthenticated ||
      (reconciliationFenceBySession.get(identity) ?? 0) !== startingFence
    ) return

    // A successful list is authoritative for cloud metadata. This single
    // replacement prunes fixture, stale, unsupported, and abandoned cards.
    // The catch above deliberately preserves the last valid view on failure.
    useAppStore.setState({ projects })
  })()
  inFlightBySession.set(identity, request)
  return request.finally(() => {
    if (inFlightBySession.get(identity) === request) inFlightBySession.delete(identity)
  })
}
