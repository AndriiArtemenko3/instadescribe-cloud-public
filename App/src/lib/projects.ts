import type { Project } from '@/types'

// Project registry. In the normal app, projects are created by uploading a clip
// (see uploadApi.ts) and are persisted in the app store. The guided demo seeds
// its own project from the tutorial registry (lib/tutorials.ts) when a tutorial
// starts, so this list is intentionally empty: a fresh clone opens on the
// upload-first empty state rather than a card that points at an absent file.
export const PROJECTS: Project[] = []

export function getProject(id: string): Project | undefined {
  return PROJECTS.find((p) => p.id === id)
}
