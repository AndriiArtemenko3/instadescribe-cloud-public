import { Link } from 'react-router-dom'
import { HelpCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FileHeader } from './FileHeader'

interface StepPromptProps {
  file: File
  fileUrl: string
  customPrompt: string
  onPromptChange: (v: string) => void
  onReplace: () => void
  onBack: () => void
  onNext: () => void
}

export function StepPrompt({ file, fileUrl, customPrompt, onPromptChange, onReplace, onBack, onNext }: StepPromptProps) {
  return (
    <div className="flex flex-col gap-6">
      <FileHeader file={file} fileUrl={fileUrl} onReplace={onReplace} />

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium text-neutral-700">Add Custom Prompt:</p>
        <textarea
          value={customPrompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder={`Optional context for the AD generator. Examples:\n• "Focus on character expressions and background details"\n• "Sports match — prioritise action descriptions"\n• "British English, avoid American idioms"`}
          className="min-h-36 w-full resize-none rounded-xl border-2 border-dashed border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-700 placeholder:text-neutral-400 outline-none focus:border-neutral-400 focus:bg-white transition-colors"
        />
      </div>

      <div className="flex items-center">
        <Link to="/dashboard/help#custom-prompt" className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-600 transition-colors">
          <HelpCircle size={15} />
          Need Help?
        </Link>
        <div className="flex-1" />
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onBack}>Go Back</Button>
          <Button variant="default" size="sm" onClick={onNext}>Next</Button>
        </div>
      </div>
    </div>
  )
}
