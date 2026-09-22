// G7 B1/B7: protected calls carry X-Portfolio-Token; the helper rejects
// absolute/external URLs so it cannot be reused for S3; errors are typed and
// sanitized (no raw bodies, URLs, tokens, XML or tracebacks).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearPortfolioToken, setPortfolioToken } from './portfolioToken'
import {
  CloudApiError,
  cloudFetch,
  completeCloudUpload,
  createCloudJob,
  listCloudJobs,
  probeCloudHealth,
  validatePortfolioToken,
} from './cloudApi'

const TOKEN = 'unit-test-token'
const VALID_JOB_ID = '11111111-1111-4111-8111-111111111111'
const VALID_PROJECT_ID = '22222222-2222-4222-8222-222222222222'

const VALID_JOB = {
  id: VALID_JOB_ID,
  projectId: VALID_PROJECT_ID,
  project_name: 'Contract clip',
  starred: false,
  status: 'ready',
  canonicalState: 'READY_FOR_REVIEW',
  sourceUploaded: true,
  progress: 100,
  stage: 'complete',
  duration_secs: 120,
  model: 'gpt-4.1',
  chunk_size: 60,
  pipeline_revision: 'dev',
  created_at: '2026-08-07T10:00:00+00:00',
  updated_at: null,
  error: null,
  error_code: null,
}

const WRONG_JOB_FIELD: Record<keyof typeof VALID_JOB, unknown> = {
  id: null,
  projectId: [],
  project_name: null,
  starred: 'false',
  status: 'complete',
  canonicalState: 'UNKNOWN',
  sourceUploaded: 1,
  progress: 101,
  stage: 7,
  duration_secs: '120',
  model: false,
  chunk_size: 60.5,
  pipeline_revision: null,
  created_at: 'yesterday',
  updated_at: 0,
  error: {},
  error_code: [],
}

beforeEach(() => {
  setPortfolioToken(TOKEN)
})

afterEach(() => {
  clearPortfolioToken()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function stubFetch(status = 200, body: unknown = {}) {
  const spy = vi.fn(async () => new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  }))
  vi.stubGlobal('fetch', spy)
  return spy
}

describe('cloudFetch', () => {
  it('attaches the portfolio token header to protected API paths', async () => {
    const spy = stubFetch()
    await cloudFetch('/api/v1/jobs')
    const [, init] = spy.mock.calls[0] as [string, RequestInit]
    expect(new Headers(init.headers).get('X-Portfolio-Token')).toBe(TOKEN)
  })

  it('rejects absolute and external URLs (cannot be reused for S3)', async () => {
    const spy = stubFetch()
    for (const bad of [
      'http://localhost:4566/instascribe-media',
      'https://s3.example.com/x',
      '//evil.example/api/v1/jobs',
      'jobs/123',
    ]) {
      await expect(cloudFetch(bad)).rejects.toBeInstanceOf(CloudApiError)
    }
    expect(spy).not.toHaveBeenCalled() // nothing ever reached the network
  })

  it('fails with an auth category when no token is present', async () => {
    clearPortfolioToken()
    const spy = stubFetch()
    await expect(cloudFetch('/api/v1/jobs')).rejects.toMatchObject({ category: 'auth' })
    expect(spy).not.toHaveBeenCalled()
  })

  it('maps statuses to sanitized categories without exposing bodies', async () => {
    for (const [status, category] of [
      [401, 'auth'],
      [404, 'not_found'],
      [422, 'validation'],
      [503, 'service'],
    ] as const) {
      stubFetch(status, { detail: 'SECRET-BODY dsn=postgresql://u:pw@db' })
      const err = await createCloudJob({} as never).catch((e) => e)
      expect(err).toBeInstanceOf(CloudApiError)
      expect(err.category).toBe(category)
      expect(String(err.message)).not.toContain('SECRET-BODY')
      expect(String(err.message)).not.toContain('pw@db')
    }
  })

  it('interprets ONLY allowlisted detail.code values (G7.1 A)', async () => {
    // capacity_conflict is the only 409 that means capacity (retryable).
    stubFetch(409, { detail: { code: 'capacity_conflict' } })
    let err = await createCloudJob({} as never).catch((e) => e as CloudApiError)
    expect(err.category).toBe('capacity')
    expect(err.retryable).toBe(true)

    stubFetch(409, { detail: { code: 'source_not_visible' } })
    err = await createCloudJob({} as never).catch((e) => e as CloudApiError)
    expect(err.category).toBe('service')
    expect(err.retryable).toBe(true)

    for (const code of ['terminal_conflict', 'source_identity_changed']) {
      stubFetch(409, { detail: { code } })
      err = await createCloudJob({} as never).catch((e) => e as CloudApiError)
      expect(err.category).toBe('conflict')
      expect(err.retryable).toBe(false)
    }

    // A generic 409 must NOT automatically mean capacity.
    stubFetch(409, { detail: 'no code here' })
    err = await createCloudJob({} as never).catch((e) => e as CloudApiError)
    expect(err.category).toBe('conflict')
    expect(err.retryable).toBe(false)

    // A hostile non-allowlisted code is discarded, never echoed.
    stubFetch(409, { detail: { code: 'EVIL http://internal:4566?sig=x' } })
    err = await createCloudJob({} as never).catch((e) => e as CloudApiError)
    expect(err.category).toBe('conflict')
    expect(err.code).toBeUndefined()
    expect(String(err.message)).not.toContain('internal:4566')
  })

  it('protected requests pin redirect/credentials/referrer (G7.1 B)', async () => {
    const spy = stubFetch()
    await cloudFetch('/api/v1/jobs')
    const [, init] = spy.mock.calls[0] as [string, RequestInit]
    expect(init.redirect).toBe('error')
    expect(init.credentials).toBe('omit')
    expect(init.referrerPolicy).toBe('no-referrer')
  })

  it('a malicious configured base can never receive the token (G7.1 B)', async () => {
    const spy = stubFetch()
    for (const evil of [
      'https://evil.example',
      'http://localhost:8000@evil.example',
      'http://user:pw@localhost:8000',
      'http://localhost:8000/?q=1',
      'http://localhost:8000/#frag',
      'http://localhost:9999',
    ]) {
      vi.stubEnv('VITE_API_BASE', evil)
      await expect(cloudFetch('/api/v1/jobs')).rejects.toMatchObject({ category: 'validation' })
    }
    vi.unstubAllEnvs()
    expect(spy).not.toHaveBeenCalled() // nothing ever reached the network
  })

  it('rejects query/fragment/traversal path forms', async () => {
    const spy = stubFetch()
    for (const bad of ['/api/v1/jobs?x=1', '/api/v1/jobs#f', '/api/v1/../secret']) {
      await expect(cloudFetch(bad)).rejects.toMatchObject({ category: 'validation' })
    }
    expect(spy).not.toHaveBeenCalled()
  })

  it('upload-complete treats both 200 and 202 as success', async () => {
    stubFetch(202, {})
    await expect(completeCloudUpload('job-1')).resolves.toBeUndefined()
    stubFetch(200, {})
    await expect(completeCloudUpload('job-1')).resolves.toBeUndefined()
    stubFetch(409, { detail: { code: 'capacity_conflict' } })
    await expect(completeCloudUpload('job-1')).rejects.toMatchObject({ category: 'capacity' })
  })
})

describe('validatePortfolioToken (G7.1 B)', () => {
  it('a rejected CANDIDATE never touches sessionStorage', async () => {
    clearPortfolioToken()
    sessionStorage.clear()
    stubFetch(401, {})
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(false)
    expect(sessionStorage.getItem('instascribe:portfolioToken')).toBeNull()
  })

  it('accepts only an exact 200 JSON jobs map; transport failure fails closed', async () => {
    stubFetch(200, {})
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(true)
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('net down') }))
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(false)
    await expect(validatePortfolioToken('')).resolves.toBe(false)
  })

  it.each([
    ['204', () => new Response(null, { status: 204 })],
    ['200 HTML SPA fallback', () => new Response('<html>app</html>', {
      status: 200, headers: { 'Content-Type': 'text/html' },
    })],
    ['malformed JSON', () => new Response('{', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
    ['array', () => new Response('[]', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
    ['null', () => new Response('null', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
    ['primitive', () => new Response('true', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
    ['malformed entry', () => new Response('{"job-1":{"status":"ready"}}', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
  ])('rejects hostile response: %s', async (_label, response) => {
    vi.stubGlobal('fetch', vi.fn(async () => response()))
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(false)
  })

  it('rejects redirect/transport failure and never persists the candidate', async () => {
    clearPortfolioToken()
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('redirect mode error') }))
    await expect(validatePortfolioToken('candidate-secret')).resolves.toBe(false)
    expect(sessionStorage.getItem('instascribe:portfolioToken')).toBeNull()
  })
})

describe('jobs-map contract validator', () => {
  async function expectRejectedByCandidateAndNormalList(body: unknown): Promise<void> {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })))
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(false)
    await expect(listCloudJobs()).rejects.toMatchObject({ category: 'service' })
  }

  it('accepts a valid empty map through both candidate and authenticated list paths', async () => {
    stubFetch(200, {})
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(true)
    await expect(listCloudJobs()).resolves.toEqual({})
  })

  it('accepts a server-valid 200-code-point project name containing astral characters', async () => {
    const body = {
      [VALID_JOB_ID]: { ...VALID_JOB, project_name: '🎬'.repeat(200) },
    }
    stubFetch(200, body)
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(true)
    await expect(listCloudJobs()).resolves.toEqual(body)
  })

  it.each(Object.keys(VALID_JOB) as Array<keyof typeof VALID_JOB>)(
    'rejects a missing mandatory %s field through both paths',
    async (field) => {
      const corrupted = { ...VALID_JOB } as Record<string, unknown>
      delete corrupted[field]
      await expectRejectedByCandidateAndNormalList({ [VALID_JOB_ID]: corrupted })
    },
  )

  it.each(Object.entries(WRONG_JOB_FIELD) as Array<[keyof typeof VALID_JOB, unknown]>)(
    'rejects wrong type/domain for mandatory %s through both paths',
    async (field, wrong) => {
      await expectRejectedByCandidateAndNormalList({
        [VALID_JOB_ID]: { ...VALID_JOB, [field]: wrong },
      })
    },
  )

  it.each([
    ['non-object entry', { [VALID_JOB_ID]: null }],
    ['array entry', { [VALID_JOB_ID]: [] }],
    ['hostile extra field', { [VALID_JOB_ID]: { ...VALID_JOB, signedUrl: 'https://storage.invalid/?X-Amz-Signature=x' } }],
    ['malformed map-key id', { 'not-a-uuid': { ...VALID_JOB, id: 'not-a-uuid' } }],
    ['malformed project id', { [VALID_JOB_ID]: { ...VALID_JOB, projectId: '../project' } }],
    ['interchanged identifiers', { [VALID_JOB_ID]: { ...VALID_JOB, projectId: VALID_JOB_ID } }],
    ['legacy/canonical mismatch', { [VALID_JOB_ID]: { ...VALID_JOB, status: 'processing' } }],
    ['fractional progress', { [VALID_JOB_ID]: { ...VALID_JOB, progress: 12.5 } }],
    ['calendar-invalid created timestamp', { [VALID_JOB_ID]: { ...VALID_JOB, created_at: '2026-02-31T12:00:00Z' } }],
    ['invalid timezone offset', { [VALID_JOB_ID]: { ...VALID_JOB, created_at: '2026-02-28T12:00:00+24:00' } }],
  ])('rejects hostile shape: %s', async (_label, body) => {
    await expectRejectedByCandidateAndNormalList(body)
  })

  it('accepts distinct job versions that belong to the same durable project', async () => {
    const secondJob = '33333333-3333-4333-8333-333333333333'
    const body = {
      [VALID_JOB_ID]: VALID_JOB,
      [secondJob]: { ...VALID_JOB, id: secondJob },
    }
    stubFetch(200, body)
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(true)
    await expect(listCloudJobs()).resolves.toEqual(body)
  })

  it('accepts a representative entry for every closed canonical state', async () => {
    const states = [
      ['AWAITING_UPLOAD', 'queued', false],
      ['UPLOAD_COMPLETE', 'queued', true],
      ['QUEUED', 'queued', true],
      ['PROCESSING', 'processing', true],
      ['READY_FOR_REVIEW', 'ready', true],
      ['EXPORT_QUEUED', 'processing', true],
      ['EXPORTING', 'processing', true],
      ['COMPLETED', 'ready', true],
      ['FAILED', 'failed', false],
      ['CANCELLED', 'failed', false],
    ] as const
    const body = Object.fromEntries(states.map(([canonicalState, status, sourceUploaded], index) => {
      const suffix = String(index + 10).padStart(12, '0')
      const jobId = `00000000-0000-4000-8000-${suffix}`
      const projectId = `00000000-0000-4001-8000-${suffix}`
      return [jobId, {
        ...VALID_JOB,
        id: jobId,
        projectId,
        canonicalState,
        status,
        sourceUploaded,
      }]
    }))
    stubFetch(200, body)
    await expect(validatePortfolioToken('candidate-token')).resolves.toBe(true)
    await expect(listCloudJobs()).resolves.toEqual(body)
  })
})

describe('probeCloudHealth (G7.1 D8)', () => {
  it('probes /api/healthz with hardened options and NO token', async () => {
    const spy = stubFetch(200, { status: 'ok' })
    await expect(probeCloudHealth()).resolves.toBe(true)
    const [url, init] = spy.mock.calls[0] as [string, RequestInit]
    expect(String(url).endsWith('/api/healthz')).toBe(true)
    expect(init.redirect).toBe('error')
    expect(init.credentials).toBe('omit')
    expect(init.referrerPolicy).toBe('no-referrer')
    expect(new Headers(init.headers).get('X-Portfolio-Token')).toBeNull()
  })

  it.each([
    ['204', () => new Response(null, { status: 204 })],
    ['200 HTML SPA fallback', () => new Response('<html>app</html>', {
      status: 200, headers: { 'Content-Type': 'text/html' },
    })],
    ['malformed JSON', () => new Response('{', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
    ['wrong JSON shape', () => new Response('{"status":"ready"}', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
    ['extra JSON field', () => new Response('{"status":"ok","detail":"x"}', {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })],
  ])('rejects hostile health response: %s', async (_label, response) => {
    vi.stubGlobal('fetch', vi.fn(async () => response()))
    await expect(probeCloudHealth()).resolves.toBe(false)
  })

  it('rejects redirect/transport failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('redirect mode error') }))
    await expect(probeCloudHealth()).resolves.toBe(false)
  })

  it('refuses a malicious configured base without any network call', async () => {
    const spy = stubFetch(200, {})
    vi.stubEnv('VITE_API_BASE', 'https://evil.example')
    await expect(probeCloudHealth()).resolves.toBe(false)
    vi.unstubAllEnvs()
    expect(spy).not.toHaveBeenCalled()
  })
})
