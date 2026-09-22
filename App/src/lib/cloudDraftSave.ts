import {
  patchCloudScene,
  type CloudPatchResponse,
  type CloudSceneOverride,
} from './cloudApi'
import {
  clearSceneDraftFieldsIfUnchanged,
  persistSceneActive,
  persistSceneText,
  type SceneEdit,
} from './persistence'

type PatchRequest = (
  jobId: string,
  sceneKey: string,
  patch: CloudSceneOverride,
) => Promise<CloudPatchResponse>

type AppliedCallback = (response: CloudPatchResponse) => void | Promise<void>

export interface CloudDraftSaveOutcome {
  response: CloudPatchResponse
  /** True only when no newer draft-backed value superseded this request. */
  latest: boolean
}

export class CloudDraftSaveDisposedError extends Error {
  constructor() {
    super('cloud draft save coordinator disposed')
    this.name = 'CloudDraftSaveDisposedError'
  }
}

interface SaveLane {
  tail: Promise<void>
  sequence: number
  latestByField: Partial<Record<keyof SceneEdit, number>>
}

function submittedDraft(patch: CloudSceneOverride): SceneEdit {
  const submitted: SceneEdit = {}
  if (typeof patch.ad === 'string') submitted.text = patch.ad
  if (typeof patch.active === 'boolean') submitted.active = patch.active
  return submitted
}

/**
 * One coordinator is owned by one mounted cloud editor. Requests are
 * serialized independently per (jobId, sceneId), so an older PATCH can never
 * become the final server write after a newer user intent. Failures do not
 * poison a lane: the next queued intent is still sent. Draft-backed values are
 * persisted before enqueue and compare-cleared only after their own success.
 */
export class CloudSceneSaveCoordinator {
  private readonly lanes = new Map<string, SaveLane>()
  private disposed = false

  constructor(private readonly request: PatchRequest = patchCloudScene) {}

  dispose(): void {
    this.disposed = true
  }

  save(
    projectId: string,
    jobId: string,
    sceneId: number,
    sceneKey: string,
    patch: CloudSceneOverride,
    onApplied?: AppliedCallback,
  ): Promise<CloudDraftSaveOutcome> {
    if (this.disposed) return Promise.reject(new CloudDraftSaveDisposedError())

    const submitted = submittedDraft(patch)
    // Persist at enqueue time. This also covers Apply, which may submit an
    // active value that was not previously toggled in the scene list.
    if (submitted.text !== undefined) persistSceneText(projectId, sceneId, submitted.text, jobId)
    if (submitted.active !== undefined) persistSceneActive(projectId, sceneId, submitted.active, jobId)

    const laneKey = `${jobId}\u0000${sceneKey}`
    const lane = this.lanes.get(laneKey) ?? {
      tail: Promise.resolve(),
      sequence: 0,
      latestByField: {},
    }
    this.lanes.set(laneKey, lane)
    const sequence = ++lane.sequence
    for (const field of Object.keys(submitted) as Array<keyof SceneEdit>) {
      lane.latestByField[field] = sequence
    }

    const execution = lane.tail.then(async () => {
      if (this.disposed) throw new CloudDraftSaveDisposedError()
      let response: CloudPatchResponse
      try {
        response = await this.request(jobId, sceneKey, patch)
      } catch (error) {
        if (this.disposed) throw new CloudDraftSaveDisposedError()
        throw error
      }
      if (this.disposed) throw new CloudDraftSaveDisposedError()
      // Fence any older overrides GET before removing the local reconstruction
      // draft. If the acknowledgement cannot be committed to the mounted
      // editor, the draft stays available for a safe retry/remount.
      if (onApplied) await onApplied(response)
      if (this.disposed) throw new CloudDraftSaveDisposedError()
      if (Object.keys(submitted).length > 0) {
        clearSceneDraftFieldsIfUnchanged(projectId, sceneId, submitted, jobId)
      }
      const submittedFields = Object.keys(submitted) as Array<keyof SceneEdit>
      const latest = !this.disposed && (
        submittedFields.length > 0
          ? submittedFields.every((field) => lane.latestByField[field] === sequence)
          : lane.sequence === sequence
      )
      return { response, latest }
    })

    // A rejected request is observed by its caller but never poisons the
    // serialized lane. A later queued intent always gets its turn.
    lane.tail = execution.then(
      () => undefined,
      () => undefined,
    )
    void lane.tail.finally(() => {
      if (this.lanes.get(laneKey) === lane && lane.sequence === sequence) {
        this.lanes.delete(laneKey)
      }
    })
    return execution
  }
}
