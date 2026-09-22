// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  fetchCloudOverrides: vi.fn(),
  patchCloudScene: vi.fn(),
  cloudEditorData: {
    manifest: { projectId: 'project-1', jobId: 'job-1' },
    rawScenes: [{
      id: 1,
      sceneNumber: 1,
      sceneKey: 'scene_alpha',
      startSecs: 0,
      endSecs: 4,
      durationSecs: 4,
      text: 'pipeline default',
      template: 'template',
      characterIds: [],
      locked: false,
      needsReview: false,
      active: true,
    }],
    audioEvents: [],
    adGaps: [],
    entities: [],
    scenesLoading: false,
    videoUrl: null,
  },
}))

vi.mock('@/lib/cloudMode', () => ({
  isCloudMode: () => true,
  isCloudSession: () => true,
  cloudApiBase: () => 'http://localhost:8000',
}))

vi.mock('@/lib/cloudApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/cloudApi')>()
  return {
    ...actual,
    fetchCloudOverrides: mocks.fetchCloudOverrides,
    patchCloudScene: mocks.patchCloudScene,
  }
})

vi.mock('../hooks/useCloudEditorData', () => ({
  useCloudEditorData: () => mocks.cloudEditorData,
}))

vi.mock('../components/SceneListPanel', () => ({
  SceneListPanel: ({
    scenes,
    onActiveToggle,
  }: {
    scenes: Array<{ id: number; text: string; active: boolean }>
    onActiveToggle: (sceneId: number) => void
  }) => (
    <div>
      <div data-testid="mounted-scene-state">
        {scenes.map((scene) => `${scene.text}|${scene.active ? 'active' : 'inactive'}`).join(',')}
      </div>
      {scenes.map((scene) => (
        <button
          key={scene.id}
          type="button"
          aria-label={`Toggle scene ${scene.id}`}
          onClick={() => onActiveToggle(scene.id)}
        >Toggle</button>
      ))}
    </div>
  ),
}))
vi.mock('../components/VideoPanel', () => ({ VideoPanel: () => <div /> }))
vi.mock('../components/ScriptPanel', () => ({
  ScriptPanel: ({
    scene,
    onAdChange,
    onApply,
    justApplied,
  }: {
    scene: { id: number; text: string } | null
    onAdChange: (sceneId: number, text: string) => void
    onApply: (sceneId: number) => void
    justApplied: boolean
  }) => scene ? (
    <div>
      <input
        aria-label="Description text"
        value={scene.text}
        onChange={(event) => onAdChange(scene.id, event.target.value)}
      />
      <button type="button" onClick={() => onApply(scene.id)}>Apply</button>
      {justApplied && <p>Changes applied</p>}
    </div>
  ) : null,
}))
vi.mock('../components/CharactersPanel', () => ({ CharactersPanel: () => <div /> }))
vi.mock('../components/QualityPanel', () => ({ QualityPanel: () => <div /> }))
vi.mock('@/features/study/EditorTour', () => ({ EditorTour: () => null }))
vi.mock('@/features/study/HelpPanel', () => ({ HelpPanel: () => null }))

import EditorPage from './EditorPage'
import { persistSceneActive, persistSceneText } from '@/lib/persistence'
import { useAppStore } from '@/store/appStore'

function renderMountedEditor() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/editor/project-1']}>
        <Routes>
          <Route path="/editor/:projectId" element={<EditorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  mocks.fetchCloudOverrides.mockReset()
  mocks.patchCloudScene.mockReset()
  mocks.fetchCloudOverrides.mockResolvedValue({
    scene_alpha: { ad: 'server A', active: true },
  })
  mocks.patchCloudScene.mockResolvedValue({
    projectId: 'project-1',
    jobId: 'job-1',
    sceneId: 'scene_alpha',
    version: 1,
    updatedAt: '2026-08-07T12:00:00Z',
    override: {},
  })
  useAppStore.setState({
    projects: [{
      id: 'project-1',
      jobId: 'job-1',
      name: 'Editor reconstruction',
      status: 'ready',
      createdAt: '2026-08-07T10:00:00Z',
      durationSecs: 4,
    }],
    isAuthenticated: true,
  })
  persistSceneText('project-1', 1, 'local B', 'job-1')
  persistSceneActive('project-1', 1, false, 'job-1')
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('mounted cloud editor reconstruction', () => {
  it('renders local draft B over server override A after initial mount and remount', async () => {
    const first = renderMountedEditor()
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledWith('job-1'))
    expect((await screen.findByTestId('mounted-scene-state')).textContent).toContain('local B|inactive')
    expect(screen.getByTestId('mounted-scene-state').textContent).not.toContain('server A')
    first.unmount()

    renderMountedEditor()
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledTimes(2))
    expect((await screen.findByTestId('mounted-scene-state')).textContent).toContain('local B|inactive')
    expect(screen.getByTestId('mounted-scene-state').textContent).not.toContain('server A')
  })

  it('does not show Changes applied for A while newer B is queued', async () => {
    sessionStorage.clear()
    persistSceneText('project-1', 1, 'A', 'job-1')
    const first = deferredPatch()
    const second = deferredPatch()
    mocks.patchCloudScene
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    renderMountedEditor()
    const input = await screen.findByRole('textbox', { name: 'Description text' })
    await waitFor(() => expect((input as HTMLInputElement).value).toBe('A'))

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    fireEvent.change(input, { target: { value: 'B' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    await waitFor(() => expect(mocks.patchCloudScene).toHaveBeenCalledTimes(1))

    await act(async () => first.resolve(patchResponse('A', 1)))
    await waitFor(() => expect(mocks.patchCloudScene).toHaveBeenCalledTimes(2))
    expect(screen.queryByText('Changes applied')).toBeNull()
    expect((screen.getByRole('textbox', { name: 'Description text' }) as HTMLInputElement).value).toBe('B')

    await act(async () => second.resolve(patchResponse('B', 2)))
    expect(await screen.findByText('Changes applied')).toBeTruthy()
    expect(mocks.patchCloudScene.mock.calls.map(([, , patch]) => patch.ad)).toEqual(['A', 'B'])
    expect(sessionStorage.getItem('instascribe:project-1:job-1:edits')).toBeNull()

    const mounted = screen.getByTestId('mounted-scene-state')
    expect(mounted.textContent).toContain('B|active')
    cleanup()
    mocks.fetchCloudOverrides.mockResolvedValueOnce({
      scene_alpha: { ad: 'B', active: true },
    })
    renderMountedEditor()
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledTimes(2))
    expect((await screen.findByRole('textbox', { name: 'Description text' }) as HTMLInputElement).value).toBe('B')
    expect(screen.getByTestId('mounted-scene-state').textContent).toContain('B|active')
  })

  it('serializes active true then false, clears the final draft, and remounts inactive', async () => {
    sessionStorage.clear()
    persistSceneActive('project-1', 1, false, 'job-1')
    mocks.fetchCloudOverrides.mockReset().mockResolvedValue({
      scene_alpha: { ad: 'server A', active: false },
    })
    const first = deferredPatch()
    const second = deferredPatch()
    mocks.patchCloudScene
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    renderMountedEditor()
    const toggle = await screen.findByRole('button', { name: 'Toggle scene 1' })
    await waitFor(() => expect(screen.getByTestId('mounted-scene-state').textContent).toContain('inactive'))

    fireEvent.click(toggle)
    await waitFor(() => {
      expect(mocks.patchCloudScene).toHaveBeenCalledTimes(1)
      expect(screen.getByTestId('mounted-scene-state').textContent).toContain('active')
    })
    fireEvent.click(screen.getByRole('button', { name: 'Toggle scene 1' }))
    await waitFor(() => expect(screen.getByTestId('mounted-scene-state').textContent).toContain('inactive'))
    expect(mocks.patchCloudScene).toHaveBeenCalledTimes(1)

    await act(async () => first.resolve(activePatchResponse(true, 1)))
    await waitFor(() => expect(mocks.patchCloudScene).toHaveBeenCalledTimes(2))
    expect(sessionStorage.getItem('instascribe:project-1:job-1:edits')).toContain('false')
    await act(async () => second.resolve(activePatchResponse(false, 2)))
    expect(mocks.patchCloudScene.mock.calls.map(([, , patch]) => patch.active)).toEqual([true, false])
    await waitFor(() => {
      expect(sessionStorage.getItem('instascribe:project-1:job-1:edits')).toBeNull()
      expect(screen.getByTestId('mounted-scene-state').textContent).toContain('inactive')
    })

    cleanup()
    mocks.fetchCloudOverrides.mockResolvedValueOnce({
      scene_alpha: { ad: 'server A', active: false },
    })
    renderMountedEditor()
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledTimes(2))
    await waitFor(() => {
      expect(screen.getByTestId('mounted-scene-state').textContent).toContain('server A|inactive')
    })
  })

  it('fences a stale mount GET after B succeeds, clears only the draft, and remounts from server B', async () => {
    const staleGet = deferredValue<Record<string, { ad: string; active: boolean }>>()
    mocks.fetchCloudOverrides.mockReset().mockReturnValueOnce(staleGet.promise)
    mocks.patchCloudScene.mockResolvedValueOnce(patchResponse('local B', 2))

    const first = renderMountedEditor()
    const input = await screen.findByRole('textbox', { name: 'Description text' })
    await waitFor(() => expect((input as HTMLInputElement).value).toBe('local B'))
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(await screen.findByText('Changes applied')).toBeTruthy()
    expect(sessionStorage.getItem('instascribe:project-1:job-1:edits')).toBeNull()
    expect((screen.getByRole('textbox', { name: 'Description text' }) as HTMLInputElement).value).toBe('local B')

    await act(async () => staleGet.resolve({
      scene_alpha: { ad: 'server A', active: true },
    }))
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledTimes(1))
    expect((screen.getByRole('textbox', { name: 'Description text' }) as HTMLInputElement).value).toBe('local B')
    expect(screen.queryByDisplayValue('server A')).toBeNull()
    first.unmount()

    mocks.fetchCloudOverrides.mockResolvedValueOnce({
      scene_alpha: { ad: 'local B', active: true },
    })
    renderMountedEditor()
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledTimes(2))
    expect((await screen.findByRole('textbox', { name: 'Description text' }) as HTMLInputElement).value).toBe('local B')
    expect(sessionStorage.getItem('instascribe:project-1:job-1:edits')).toBeNull()
  })

  it('preserves B across unmount while PATCH B and the next mount stale GET A are pending', async () => {
    const patch = deferredPatch()
    mocks.patchCloudScene.mockReturnValueOnce(patch.promise)
    const first = renderMountedEditor()
    const firstInput = await screen.findByRole('textbox', { name: 'Description text' })
    await waitFor(() => expect((firstInput as HTMLInputElement).value).toBe('local B'))
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    await waitFor(() => expect(mocks.patchCloudScene).toHaveBeenCalledTimes(1))
    first.unmount()

    const staleGet = deferredValue<Record<string, { ad: string; active: boolean }>>()
    mocks.fetchCloudOverrides.mockReset().mockReturnValueOnce(staleGet.promise)
    renderMountedEditor()
    const remountedInput = await screen.findByRole('textbox', { name: 'Description text' })
    await waitFor(() => expect((remountedInput as HTMLInputElement).value).toBe('local B'))

    await act(async () => patch.resolve(patchResponse('local B', 2)))
    expect(sessionStorage.getItem('instascribe:project-1:job-1:edits')).toContain('local B')
    await act(async () => staleGet.resolve({
      scene_alpha: { ad: 'server A', active: true },
    }))
    await waitFor(() => expect(mocks.fetchCloudOverrides).toHaveBeenCalledTimes(1))
    expect((screen.getByRole('textbox', { name: 'Description text' }) as HTMLInputElement).value).toBe('local B')
    expect(screen.queryByDisplayValue('server A')).toBeNull()
  })
})

function deferredPatch() {
  let resolve: (value: ReturnType<typeof patchResponse>) => void = () => {}
  const promise = new Promise<ReturnType<typeof patchResponse>>((done) => { resolve = done })
  return { promise, resolve }
}

function deferredValue<T>() {
  let resolve: (value: T) => void = () => {}
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function patchResponse(ad: string, version: number) {
  return {
    projectId: 'project-1',
    jobId: 'job-1',
    sceneId: 'scene_alpha',
    version,
    updatedAt: '2026-08-07T12:00:00Z',
    override: { ad, active: true },
  }
}

function activePatchResponse(active: boolean, version: number) {
  return {
    projectId: 'project-1',
    jobId: 'job-1',
    sceneId: 'scene_alpha',
    version,
    updatedAt: '2026-08-07T12:00:00Z',
    override: { ad: 'server A', active },
  }
}
