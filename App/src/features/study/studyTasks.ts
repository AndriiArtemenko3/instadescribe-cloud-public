// Single source of truth for the guided tour steps shown in the editor banner and
// the Help panel checklist. Keep the copy short, plain, and imperative — product
// voice, not research-task voice.

export interface StudyTask {
  id: string
  label: string
  /** Optional second line, rendered small + italic under the label. */
  note?: string
}

export const STUDY_TASKS: StudyTask[] = [
  { id: 'rename', label: 'Rename a character and watch the script update' },
  { id: 'activate', label: 'Activate a described scene' },
  { id: 'apply', label: 'Edit a description and apply it' },
  { id: 'voiceline', label: 'Preview a single narration line' },
  { id: 'preview', label: 'Render the full video, then close your eyes' },
]
