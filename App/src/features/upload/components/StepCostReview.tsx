import { Link } from 'react-router-dom'
import { HelpCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { FileHeader } from './FileHeader'
import { useAppStore } from '@/store/appStore'

function getInitials(name: string) {
  return name.split(' ').map((w) => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase()
}

interface StepCostReviewProps {
  file: File
  fileUrl: string
  estimatedTokens: number
  estimatedMinutes: number
  onReplace: () => void
  onBack: () => void
  onConfirm: () => void
}

export function StepCostReview({ file, fileUrl, estimatedTokens, estimatedMinutes, onReplace, onBack, onConfirm }: StepCostReviewProps) {
  const user = useAppStore((s) => s.currentUser)

  return (
    <div className="flex flex-col gap-6">
      <FileHeader file={file} fileUrl={fileUrl} onReplace={onReplace} />

      <div className="flex flex-col gap-4 rounded-xl border border-neutral-200 bg-neutral-50 px-5 py-5">
        <p className="text-sm font-medium text-neutral-700">Estimated Generation Cost:</p>

        <div>
          <p className="text-2xl font-semibold text-neutral-900">
            {estimatedTokens.toLocaleString()} <span className="text-base font-normal text-neutral-500">tokens</span>
          </p>
          <p className="mt-1 text-xs text-neutral-400">~{estimatedMinutes} minute{estimatedMinutes !== 1 ? 's' : ''} processing time</p>
        </div>

        {user && (
          <div className="flex items-center gap-3 rounded-lg border border-neutral-200 bg-white px-4 py-3">
            <Avatar className="h-8 w-8 rounded-full">
              <AvatarFallback className="rounded-full bg-brand-50 text-xs font-medium text-brand-500">
                {getInitials(user.name)}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-sm font-medium text-neutral-700">{user.name}</p>
              <p className="text-xs text-neutral-400">
                tokens available: {(user.tokenBalance ?? 1_000_000).toLocaleString()}
              </p>
            </div>
          </div>
        )}

        <p className="text-xs text-neutral-400">
          Cost estimate is approximate and may vary based on video content.
        </p>
      </div>

      <div className="flex items-center">
        <Link to="/dashboard/help#tokens-pricing" className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-600 transition-colors">
          <HelpCircle size={15} />
          Need Help?
        </Link>
        <div className="flex-1" />
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onBack}>Go Back</Button>
          <Button variant="default" size="sm" onClick={onConfirm}>Confirm</Button>
        </div>
      </div>
    </div>
  )
}
