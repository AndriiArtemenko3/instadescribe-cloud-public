import { useEffect, useState } from 'react'
import { AlertCircle, Check, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { isDemoBuild } from '@/lib/session'
import { fetchProviders, setProvider, type ProvidersState } from '@/lib/providersApi'

// Lets the operator switch the model backend (OpenAI / Claude / Gemini / local)
// at runtime. Readiness reflects which keys are present in the server's .env.
export function ProviderPicker() {
  const demo = isDemoBuild()
  const [state, setState] = useState<ProvidersState | null>(null)
  const [error, setError] = useState(false)
  const [pending, setPending] = useState<string | null>(null)

  useEffect(() => {
    if (demo) return
    fetchProviders()
      .then(setState)
      .catch(() => setError(true))
  }, [demo])

  async function choose(id: string) {
    if (!state || id === state.current || pending) return
    setPending(id)
    try {
      setState(await setProvider(id))
      setError(false)
    } catch {
      setError(true)
    } finally {
      setPending(null)
    }
  }

  if (demo) {
    return (
      <p className="text-sm text-neutral-500">
        This is the fixtures demo — model calls are served from committed data, so there is no
        provider to choose.
      </p>
    )
  }
  if (error && !state) {
    return (
      <p className="text-sm text-neutral-400">
        Provider info unavailable — start the server (`python3 server.py` in modular_pipeline/).
      </p>
    )
  }
  if (!state) return <p className="text-sm text-neutral-400">Loading providers…</p>

  return (
    <div className="flex flex-col gap-2">
      {state.backends.map((b) => {
        const active = b.id === state.current
        return (
          <button
            key={b.id}
            type="button"
            onClick={() => choose(b.id)}
            disabled={pending !== null}
            className={cn(
              'flex items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-colors',
              active
                ? 'border-brand-400 bg-brand-50'
                : 'border-neutral-200 hover:border-neutral-300',
              pending !== null && 'opacity-60',
            )}
          >
            <span className="flex min-w-0 items-center gap-2.5">
              <span
                className={cn(
                  'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
                  active
                    ? 'border-brand-400 bg-brand-400 text-white'
                    : 'border-neutral-300 text-transparent',
                )}
              >
                {pending === b.id ? (
                  <Loader2 size={12} className="animate-spin text-neutral-500" />
                ) : (
                  <Check size={12} />
                )}
              </span>
              <span className="truncate text-sm font-medium text-neutral-900">{b.label}</span>
            </span>
            <span className="shrink-0 pl-3 text-xs">
              {b.ready ? (
                <span className="text-success-400">ready</span>
              ) : (
                <span
                  className="inline-flex items-center gap-1 text-neutral-400"
                  title={b.reason}
                >
                  <AlertCircle size={11} /> not configured
                </span>
              )}
            </span>
          </button>
        )
      })}
      <p className="pt-1 text-xs text-neutral-400">
        Applies to new jobs and edits. API keys stay in the server's <code>.env</code> — never
        entered here. A backend marked “not configured” needs its key set (hover for details).
      </p>
    </div>
  )
}
