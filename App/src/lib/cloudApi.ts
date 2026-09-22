// Cloud-core API client (G7, hardened by G7.1 B). The ONLY module that
// attaches the portfolio token. The constraint lives in cloudFetch ITSELF,
// not merely its path argument: production requests are same-origin;
// development permits only the documented loopback API origins; userinfo,
// query, fragment and unexpected base/path forms are rejected; protected
// requests use redirect:"error", credentials:"omit" and
// referrerPolicy:"no-referrer", so neither a malicious configured base nor
// a redirect can ever receive X-Portfolio-Token. Errors are typed and
// sanitized: only an ALLOWLISTED detail.code is parsed from API error JSON
// and every other body byte is discarded.

import { cloudApiBase } from './cloudMode'
import { getPortfolioToken } from './portfolioToken'

export type CloudErrorCategory =
  | 'auth' // missing/wrong portfolio token
  | 'validation' // the request was rejected by the contract
  | 'not_found'
  | 'capacity' // another job holds the processing slot (retryable)
  | 'service' // transient server/storage/queue condition (retryable)
  | 'conflict' // non-retryable conflict (terminal state, changed identity)
  | 'failed' // the pipeline reported a terminal failure
  | 'network' // fetch/transport failure

// The ONLY server codes the client will ever interpret; anything else in a
// response body is discarded unread.
const CODE_ALLOWLIST = new Set([
  'capacity_conflict',
  'source_not_visible',
  'terminal_conflict',
  'source_identity_changed',
  'source_mismatch',
  'artifacts_not_ready',
  'job_not_editable',
  'invalid_scene_id',
  'manifest_unavailable',
  'persistence_unavailable',
  'enqueue_unavailable',
  'storage_unavailable',
  'not_found',
])

export class CloudApiError extends Error {
  readonly category: CloudErrorCategory
  readonly status?: number
  readonly code?: string
  readonly retryable: boolean

  constructor(category: CloudErrorCategory, status?: number, code?: string) {
    super(`cloud api: ${category}${status ? ` (${status})` : ''}`)
    this.name = 'CloudApiError'
    this.category = category
    this.status = status
    this.code = code
    this.retryable = category === 'capacity' || category === 'service' || category === 'network'
  }
}

/** Extract ONLY an allowlisted detail.code; every other byte is discarded. */
async function allowlistedCode(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: { code?: unknown } }
    const code = body?.detail?.code
    return typeof code === 'string' && CODE_ALLOWLIST.has(code) ? code : undefined
  } catch {
    return undefined
  }
}

function categorize(status: number, code?: string): CloudErrorCategory {
  if (status === 401 || status === 403) return 'auth'
  if (status === 404) return 'not_found'
  if (status === 409) {
    // A generic 409 must NOT automatically mean capacity (G7.1 A).
    if (code === 'capacity_conflict') return 'capacity'
    if (code === 'source_not_visible') return 'service'
    return 'conflict' // terminal_conflict / source_identity_changed / unknown
  }
  if (status === 422 || status === 400) return 'validation'
  if (status === 503 || status === 502 || status === 504 || status === 500) return 'service'
  return 'service'
}

export async function errorFrom(res: Response): Promise<CloudApiError> {
  const code = await allowlistedCode(res)
  return new CloudApiError(categorize(res.status, code), res.status, code)
}

const DEV_ALLOWED_ORIGINS = new Set(['http://localhost:8000', 'http://127.0.0.1:8000'])

/** Validate base+path and build the final same-origin/loopback URL. */
function protectedUrl(path: string): string {
  if (!path.startsWith('/api/') || path.includes('?') || path.includes('#') || path.includes('..')) {
    throw new CloudApiError('validation')
  }
  const base = cloudApiBase()
  if (base === '') {
    return path // same-origin — the production cloud form
  }
  let parsed: URL
  try {
    parsed = new URL(base)
  } catch {
    throw new CloudApiError('validation')
  }
  if (
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    (parsed.pathname !== '/' && parsed.pathname !== '')
  ) {
    throw new CloudApiError('validation')
  }
  if (!import.meta.env.DEV || !DEV_ALLOWED_ORIGINS.has(parsed.origin)) {
    throw new CloudApiError('validation') // only documented loopback origins
  }
  return `${parsed.origin}${path}`
}

/**
 * Fetch a PROTECTED cloud API path. By construction the token can only
 * travel to the same-origin `/api/*` surface (production) or the documented
 * loopback API (development) — never S3, signed URLs, foreign origins, or
 * across a redirect.
 */
export async function cloudFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const url = protectedUrl(path)
  const token = getPortfolioToken()
  if (!token) throw new CloudApiError('auth')
  const headers = new Headers(init.headers)
  headers.set('X-Portfolio-Token', token)
  let res: Response
  try {
    res = await fetch(url, {
      ...init,
      headers,
      redirect: 'error',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
    })
  } catch {
    throw new CloudApiError('network')
  }
  return res
}

async function cloudJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await cloudFetch(path, init)
  if (!res.ok) throw await errorFrom(res)
  return (await res.json()) as T
}

// ── Contracts (G3–G6, authoritative on the server) ─────────────────────────

export interface CloudCreateSettings {
  model: string
  frameQuality: string
  fps: number
  chunkSizeSecs: number
  audioExtraction: boolean
  customPrompt: string
  detailLevel: number
  presetStyle: string
  language: string | null
}

export interface CloudCreateRequest {
  name: string
  durationSecs: number
  fileName: string
  contentType: string
  fileSizeBytes: number
  settings: CloudCreateSettings
}

export interface CloudCreateResponse {
  projectId: string
  jobId: string
  upload: {
    url: string
    fields: Record<string, string>
    expiresAt: string
  }
}

export interface CloudJobStatus {
  id: string
  projectId: string
  project_name: string
  starred: boolean
  status: 'queued' | 'processing' | 'ready' | 'failed'
  canonicalState:
    | 'AWAITING_UPLOAD'
    | 'UPLOAD_COMPLETE'
    | 'QUEUED'
    | 'PROCESSING'
    | 'READY_FOR_REVIEW'
    | 'EXPORT_QUEUED'
    | 'EXPORTING'
    | 'COMPLETED'
    | 'FAILED'
    | 'CANCELLED'
  /** Durable source-verification identity exists, independently of slot state. */
  sourceUploaded: boolean
  progress: number
  stage: string | null
  duration_secs: number | null
  model: string | null
  chunk_size: number | null
  pipeline_revision: string
  created_at: string | null
  updated_at: string | null
  error: string | null
  error_code: string | null
}

export function createCloudJob(payload: CloudCreateRequest): Promise<CloudCreateResponse> {
  return cloudJson<CloudCreateResponse>('/api/v1/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/** upload-complete has NO body; both 200 and 202 are success. */
export async function completeCloudUpload(jobId: string): Promise<void> {
  const res = await cloudFetch(`/api/v1/jobs/${jobId}/upload-complete`, { method: 'POST' })
  if (res.status === 200 || res.status === 202) return
  throw await errorFrom(res)
}

export function getCloudJob(jobId: string): Promise<CloudJobStatus> {
  return cloudJson<CloudJobStatus>(`/api/v1/jobs/${jobId}`)
}

/** Map keyed by JOB id; each entry carries the distinct projectId. */
export async function listCloudJobs(): Promise<Record<string, CloudJobStatus>> {
  const res = await cloudFetch('/api/v1/jobs')
  if (!res.ok) throw await errorFrom(res)
  const parsed = await parseJsonResponse(res)
  if (!isJobsMap(parsed)) throw new CloudApiError('service', res.status)
  return parsed
}

const CANONICAL_STATES = new Set<CloudJobStatus['canonicalState']>([
  'AWAITING_UPLOAD', 'UPLOAD_COMPLETE', 'QUEUED', 'PROCESSING',
  'READY_FOR_REVIEW', 'EXPORT_QUEUED', 'EXPORTING', 'COMPLETED',
  'FAILED', 'CANCELLED',
])

const JOB_FIELDS = new Set<keyof CloudJobStatus>([
  'id', 'projectId', 'project_name', 'starred', 'status', 'canonicalState',
  'sourceUploaded', 'progress', 'stage', 'duration_secs', 'model', 'chunk_size',
  'pipeline_revision', 'created_at', 'updated_at', 'error', 'error_code',
])
const LEGACY_STATUSES = new Set<CloudJobStatus['status']>(['queued', 'processing', 'ready', 'failed'])
const ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ISO_TIMESTAMP_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|[+-](\d{2}):(\d{2}))$/

const EXPECTED_LEGACY_STATUS: Record<CloudJobStatus['canonicalState'], CloudJobStatus['status']> = {
  AWAITING_UPLOAD: 'queued',
  UPLOAD_COMPLETE: 'queued',
  QUEUED: 'queued',
  PROCESSING: 'processing',
  READY_FOR_REVIEW: 'ready',
  EXPORT_QUEUED: 'processing',
  EXPORTING: 'processing',
  COMPLETED: 'ready',
  FAILED: 'failed',
  CANCELLED: 'failed',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isTimestamp(value: unknown): value is string | null {
  if (value === null) return true
  if (typeof value !== 'string') return false
  const match = ISO_TIMESTAMP_RE.exec(value)
  if (!match || !Number.isFinite(Date.parse(value))) return false
  const [, yearRaw, monthRaw, dayRaw, hourRaw, minuteRaw, secondRaw, offsetHourRaw, offsetMinuteRaw] = match
  const year = Number(yearRaw)
  const month = Number(monthRaw)
  const day = Number(dayRaw)
  const hour = Number(hourRaw)
  const minute = Number(minuteRaw)
  const second = Number(secondRaw)
  const offsetHour = offsetHourRaw === undefined ? 0 : Number(offsetHourRaw)
  const offsetMinute = offsetMinuteRaw === undefined ? 0 : Number(offsetMinuteRaw)
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const monthLengths = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  const daysInMonth = month >= 1 && month <= 12 ? monthLengths[month - 1] : 0
  return day >= 1 && day <= daysInMonth &&
    hour <= 23 && minute <= 59 && second <= 59 &&
    offsetHour <= 23 && offsetMinute <= 59
}

function hasExactJobFields(candidate: Record<string, unknown>): boolean {
  const fields = Object.keys(candidate)
  return fields.length === JOB_FIELDS.size && fields.every((field) => JOB_FIELDS.has(field as keyof CloudJobStatus))
}

function isJobsMap(value: unknown): value is Record<string, CloudJobStatus> {
  if (!isRecord(value)) return false
  return Object.entries(value).every(([jobId, candidate]) => {
    if (!ID_RE.test(jobId) || !isRecord(candidate) || !hasExactJobFields(candidate)) return false
    if (
      typeof candidate.projectId !== 'string' ||
      !ID_RE.test(candidate.projectId) ||
      candidate.projectId === jobId
    ) return false
    if (
      typeof candidate.canonicalState !== 'string' ||
      !CANONICAL_STATES.has(candidate.canonicalState as CloudJobStatus['canonicalState']) ||
      typeof candidate.status !== 'string' ||
      !LEGACY_STATUSES.has(candidate.status as CloudJobStatus['status']) ||
      EXPECTED_LEGACY_STATUS[candidate.canonicalState as CloudJobStatus['canonicalState']] !== candidate.status
    ) return false
    return candidate.id === jobId &&
      typeof candidate.project_name === 'string' &&
      Array.from(candidate.project_name).length > 0 &&
      Array.from(candidate.project_name).length <= 200 &&
      typeof candidate.starred === 'boolean' &&
      typeof candidate.sourceUploaded === 'boolean' &&
      typeof candidate.progress === 'number' && Number.isInteger(candidate.progress) &&
      candidate.progress >= 0 && candidate.progress <= 100 &&
      isNullableString(candidate.stage) &&
      (candidate.duration_secs === null || (
        typeof candidate.duration_secs === 'number' && Number.isFinite(candidate.duration_secs) && candidate.duration_secs > 0
      )) &&
      (candidate.model === null || (typeof candidate.model === 'string' && candidate.model.length > 0)) &&
      (candidate.chunk_size === null || (
        typeof candidate.chunk_size === 'number' && Number.isInteger(candidate.chunk_size) && candidate.chunk_size > 0
      )) &&
      typeof candidate.pipeline_revision === 'string' && candidate.pipeline_revision.length > 0 &&
      isTimestamp(candidate.created_at) &&
      isTimestamp(candidate.updated_at) &&
      isNullableString(candidate.error) &&
      isNullableString(candidate.error_code)
  })
}

function hasJsonMediaType(res: Response): boolean {
  return (res.headers.get('Content-Type') ?? '').split(';', 1)[0].trim().toLowerCase() === 'application/json'
}

async function parseJsonResponse(res: Response): Promise<unknown> {
  if (!hasJsonMediaType(res)) throw new CloudApiError('service', res.status)
  try {
    return await res.json()
  } catch {
    throw new CloudApiError('service', res.status)
  }
}

/** G7.1 B: validate a CANDIDATE token against a protected endpoint BEFORE
    it is persisted anywhere — the candidate travels only on this one
    request; nothing rejected can survive a mid-flight reload. True only
    when the server accepts it. */
export async function validatePortfolioToken(candidate: string): Promise<boolean> {
  if (!candidate) return false
  try {
    const url = protectedUrl('/api/v1/jobs')
    const res = await fetch(url, {
      headers: { 'X-Portfolio-Token': candidate },
      redirect: 'error',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
    })
    if (res.status !== 200) return false
    const parsed = await parseJsonResponse(res)
    return isJobsMap(parsed)
  } catch {
    // Transport/service problems are not proof of a wrong token, but they
    // must not admit a session either — fail closed.
    return false
  }
}

/** Cloud health probe (Settings): same base validation as every protected
    call, hardened fetch options, and NO token — /api/healthz is public. */
export async function probeCloudHealth(): Promise<boolean> {
  let target: string
  try {
    const base = cloudApiBase()
    if (base === '') {
      target = '/api/healthz'
    } else {
      const parsed = new URL(base)
      if (
        parsed.username || parsed.password || parsed.search || parsed.hash ||
        (parsed.pathname !== '/' && parsed.pathname !== '') ||
        !import.meta.env.DEV || !DEV_ALLOWED_ORIGINS.has(parsed.origin)
      ) {
        return false
      }
      target = `${parsed.origin}/api/healthz`
    }
    const res = await fetch(target, {
      method: 'GET',
      redirect: 'error',
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
    })
    if (res.status !== 200) return false
    const parsed = await parseJsonResponse(res)
    return isRecord(parsed) && Object.keys(parsed).length === 1 && parsed.status === 'ok'
  } catch {
    return false
  }
}

export interface CloudSceneOverride {
  ad?: string
  active?: boolean
  locked?: boolean
  voice?: string
  speed?: number
}

export function fetchCloudOverrides(jobId: string): Promise<Record<string, CloudSceneOverride>> {
  return cloudJson<Record<string, CloudSceneOverride>>(`/api/v1/jobs/${jobId}/overrides`)
}

export interface CloudPatchResponse {
  projectId: string
  jobId: string
  sceneId: string
  version: number
  updatedAt: string
  override: CloudSceneOverride
}

/** PATCH the EXACT canonical pipeline scene id — never a synthesized index. */
export function patchCloudScene(
  jobId: string,
  sceneId: string,
  patch: CloudSceneOverride,
): Promise<CloudPatchResponse> {
  return cloudJson<CloudPatchResponse>(`/api/v1/jobs/${jobId}/scenes/${sceneId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}
