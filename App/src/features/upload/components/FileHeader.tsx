import { Check, Plus } from 'lucide-react'

interface FileHeaderProps {
  file: File
  fileUrl: string
  onReplace?: () => void
}

export function FileHeader({ file, fileUrl, onReplace }: FileHeaderProps) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-success-400 bg-success-400 text-white">
        <Check size={13} strokeWidth={2.5} />
      </div>
      <video
        src={fileUrl}
        className="h-9 w-16 shrink-0 rounded object-cover bg-neutral-900"
        muted
        preload="metadata"
      />
      <p className="flex-1 truncate text-sm font-medium text-neutral-700">{file.name}</p>
      {onReplace && (
        <button
          type="button"
          onClick={onReplace}
          className="flex items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
        >
          <Plus size={12} />
          Upload More Files
        </button>
      )}
    </div>
  )
}
