import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./cloudMode', () => ({
  isCloudMode: () => true,
  isCloudSession: () => true,
  cloudApiBase: () => 'http://localhost:8000',
}))

import {
  CloudDraftSaveDisposedError,
  CloudSceneSaveCoordinator,
} from './cloudDraftSave'
import { loadEdits } from './persistence'
import type { CloudPatchResponse, CloudSceneOverride } from './cloudApi'

const PROJECT = 'proj-1'
const JOB = 'job-1'
const SCENE = 1

interface PendingPatch {
  jobId: string
  sceneKey: string
  patch: CloudSceneOverride
  resolve: (value: CloudPatchResponse) => void
  reject: (reason: unknown) => void
}

function controlledPatches() {
  const pending: PendingPatch[] = []
  const wire: CloudSceneOverride[] = []
  const request = vi.fn((jobId: string, sceneKey: string, patch: CloudSceneOverride) =>
    new Promise<CloudPatchResponse>((resolve, reject) => {
      pending.push({ jobId, sceneKey, patch, resolve, reject })
    }),
  )
  const succeed = (index: number) => {
    const call = pending[index]
    wire.push(call.patch)
    call.resolve({
      projectId: PROJECT,
      jobId: call.jobId,
      sceneId: call.sceneKey,
      version: index + 1,
      updatedAt: '2026-08-07T12:00:00Z',
      override: call.patch,
    })
  }
  const fail = (index: number) => pending[index].reject(new Error('sanitized failure'))
  return { request, pending, wire, succeed, fail }
}

async function flush(): Promise<void> {
  await Promise.resolve()
  await Promise.resolve()
}

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
})

describe('CloudSceneSaveCoordinator', () => {
  it('serializes A then B so the final wire/server state and reconstruction are B', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const saveA = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'A' })
    const saveB = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'B' })

    await flush()
    expect(controlled.request).toHaveBeenCalledTimes(1)
    expect(controlled.pending[0].patch).toEqual({ ad: 'A' })
    controlled.succeed(0)
    const outcomeA = await saveA
    await flush()
    expect(outcomeA.latest).toBe(false)
    expect(controlled.request).toHaveBeenCalledTimes(2)
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]?.text).toBe('B')

    controlled.succeed(1)
    const outcomeB = await saveB
    expect(outcomeB.latest).toBe(true)
    expect(controlled.wire).toEqual([{ ad: 'A' }, { ad: 'B' }])
    expect(controlled.wire.at(-1)?.ad).toBe('B')
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toBeUndefined()
  })

  it('serializes active true then false and leaves false as final user intent', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const first = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { active: true })
    const second = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { active: false })

    await flush()
    controlled.succeed(0)
    await first
    await flush()
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]?.active).toBe(false)
    controlled.succeed(1)
    await second
    expect(controlled.wire.at(-1)?.active).toBe(false)
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toBeUndefined()
  })

  it('sends and applies B even when A fails', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const saveA = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'A' })
    const observedA = saveA.catch((error) => error)
    const saveB = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'B' })

    await flush()
    controlled.fail(0)
    expect(await observedA).toBeInstanceOf(Error)
    await flush()
    expect(controlled.request).toHaveBeenCalledTimes(2)
    controlled.succeed(1)
    await saveB
    expect(controlled.wire).toEqual([{ ad: 'B' }])
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toBeUndefined()
  })

  it('retains the latest B retry draft when B fails', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const saveA = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'A' })
    const saveB = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'B' })
    const observedB = saveB.catch((error) => error)

    await flush()
    controlled.succeed(0)
    await saveA
    await flush()
    controlled.fail(1)
    expect(await observedB).toBeInstanceOf(Error)
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toEqual({ text: 'B' })
  })

  it('runs unrelated scenes independently', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const first = coordinator.save(PROJECT, JOB, 1, 'scene_one', { ad: 'one' })
    const second = coordinator.save(PROJECT, JOB, 2, 'scene_two', { ad: 'two' })

    await flush()
    expect(controlled.request).toHaveBeenCalledTimes(2)
    controlled.succeed(1)
    await second
    expect(loadEdits(PROJECT, JOB).scenes[1]?.text).toBe('one')
    controlled.succeed(0)
    await first
  })

  it('clears an unchanged latest success and removes the empty edits key', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const save = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', {
      ad: 'only value',
      active: true,
    })
    await flush()
    expect(sessionStorage.getItem(`instascribe:${PROJECT}:${JOB}:edits`)).not.toBeNull()
    controlled.succeed(0)
    expect((await save).latest).toBe(true)
    expect(sessionStorage.getItem(`instascribe:${PROJECT}:${JOB}:edits`)).toBeNull()
  })

  it('marks an older success stale while a newer intent is pending', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const oldSave = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'old' })
    const newSave = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'new' })
    await flush()
    controlled.succeed(0)
    expect((await oldSave).latest).toBe(false)
    await flush()
    controlled.succeed(1)
    expect((await newSave).latest).toBe(true)
  })

  it('dispose prevents queued work and keeps its persisted latest draft', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const first = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'A' })
    const observedFirst = first.catch((error) => error)
    const second = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'B' })
    const observedSecond = second.catch((error) => error)
    await flush()
    coordinator.dispose()
    controlled.succeed(0)
    expect(await observedFirst).toBeInstanceOf(CloudDraftSaveDisposedError)
    expect(await observedSecond).toBeInstanceOf(CloudDraftSaveDisposedError)
    expect(controlled.request).toHaveBeenCalledTimes(1)
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toEqual({ text: 'B' })
  })

  it('dispose while a lone PATCH is pending preserves its remount draft after success', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const save = coordinator.save(PROJECT, JOB, SCENE, 'scene_alpha', { ad: 'B' })
    const observed = save.catch((error) => error)
    await flush()
    coordinator.dispose()
    controlled.succeed(0)
    expect(await observed).toBeInstanceOf(CloudDraftSaveDisposedError)
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toEqual({ text: 'B' })
  })

  it('keeps the draft when the response acknowledgement cannot be committed', async () => {
    const controlled = controlledPatches()
    const coordinator = new CloudSceneSaveCoordinator(controlled.request)
    const save = coordinator.save(
      PROJECT,
      JOB,
      SCENE,
      'scene_alpha',
      { ad: 'B' },
      () => { throw new Error('cache fence failed') },
    )
    const observed = save.catch((error) => error)
    await flush()
    controlled.succeed(0)
    expect(await observed).toBeInstanceOf(Error)
    expect(loadEdits(PROJECT, JOB).scenes[SCENE]).toEqual({ text: 'B' })
  })
})
