import { Link } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import { Coins, Layers, Film, Cpu, Clock, ExternalLink } from 'lucide-react'
import { formatDuration, formatTokens, formatDate, STATUS_STYLES, STATUS_LABELS } from '../utils/formatters'

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-medium uppercase tracking-widest text-neutral-400">
      {children}
    </h2>
  )
}

function Stat({ label, value, icon, hint }: { label: string; value: React.ReactNode; icon: React.ReactNode; hint?: string }) {
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 bg-neutral-0 p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-neutral-400">
        {icon} {label}
      </div>
      <p className="text-2xl font-semibold text-neutral-900 tabular-nums">{value}</p>
      {hint && <p className="text-xs text-neutral-400">{hint}</p>}
    </article>
  )
}

export default function UsagePage() {
  const projects = useAppStore((s) => s.projects)
  const user = useAppStore((s) => s.currentUser)

  const ready = projects.filter((p) => p.status === 'ready')
  const totalTokens = ready.reduce((s, p) => s + (p.tokensUsed ?? 0), 0)
  const totalScenes = ready.reduce((s, p) => s + (p.sceneCount ?? 0), 0)
  const totalSecs = ready.reduce((s, p) => s + (p.durationSecs ?? 0), 0)
  const byModel = ready.reduce<Record<string, number>>((acc, p) => {
    const m = p.model ?? 'unknown'
    acc[m] = (acc[m] ?? 0) + (p.tokensUsed ?? 0)
    return acc
  }, {})

  const recent = [...projects]
    .sort((a, b) => (new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()))
    .slice(0, 10)

  return (
    <main className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 max-w-5xl">
        <div className="flex flex-col gap-10">

          <section className="flex flex-col gap-4">
            <SectionHeading>Totals</SectionHeading>
            <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
              <Stat
                icon={<Coins size={11} />}
                label="Tokens used"
                value={formatTokens(totalTokens)}
                hint={user?.tokenBalance != null
                  ? `Balance: ${user.tokenBalance.toLocaleString()}`
                  : undefined}
              />
              <Stat
                icon={<Film size={11} />}
                label="Projects"
                value={projects.length}
                hint={`${ready.length} ready`}
              />
              <Stat
                icon={<Layers size={11} />}
                label="Scenes generated"
                value={totalScenes.toLocaleString()}
              />
              <Stat
                icon={<Clock size={11} />}
                label="Video processed"
                value={formatDuration(totalSecs)}
              />
            </div>
          </section>

          {Object.keys(byModel).length > 0 && (
            <section className="flex flex-col gap-4">
              <SectionHeading>By model</SectionHeading>
              <article className="rounded-lg border border-neutral-200 bg-neutral-0 p-5">
                <div className="flex flex-col gap-3">
                  {Object.entries(byModel)
                    .sort((a, b) => b[1] - a[1])
                    .map(([model, tokens]) => {
                      const pct = totalTokens > 0 ? Math.round((tokens / totalTokens) * 100) : 0
                      return (
                        <div key={model} className="flex flex-col gap-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="flex items-center gap-1.5 font-medium text-neutral-900">
                              <Cpu size={12} className="text-neutral-400" />
                              {model}
                            </span>
                            <span className="text-neutral-500 tabular-nums">
                              {formatTokens(tokens)} · {pct}%
                            </span>
                          </div>
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-150">
                            <div
                              className="h-full bg-brand-400"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                </div>
              </article>
            </section>
          )}

          <section className="flex flex-col gap-4">
            <SectionHeading>Recent processing</SectionHeading>
            {recent.length === 0 ? (
              <article className="rounded-lg border border-neutral-200 bg-neutral-0 p-8 text-center">
                <p className="text-sm text-neutral-500">No projects processed yet.</p>
                <Link
                  to="/upload"
                  className="mt-2 inline-flex items-center gap-1 text-xs text-brand-500 hover:underline"
                >
                  Process a video <ExternalLink size={11} />
                </Link>
              </article>
            ) : (
              <article className="overflow-hidden rounded-lg border border-neutral-200 bg-neutral-0">
                <ul className="divide-y divide-neutral-100">
                  {recent.map((p) => (
                    <li key={p.id}>
                      <Link
                        to={`/editor/${p.id}`}
                        className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-neutral-50 transition-colors"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-neutral-900">{p.name}</p>
                          <p className="text-xs text-neutral-400">{formatDate(p.createdAt)}</p>
                        </div>
                        <span className={STATUS_STYLES[p.status]}>
                          {STATUS_LABELS[p.status]}
                        </span>
                        <div className="hidden sm:flex items-center text-xs text-neutral-500 tabular-nums">
                          <span className="flex w-16 items-center gap-1"><Layers size={11} /> {p.sceneCount ?? '—'}</span>
                          <span className="flex w-20 items-center gap-1"><Coins size={11} /> {formatTokens(p.tokensUsed)}</span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              </article>
            )}
          </section>

        </div>
      </div>
    </main>
  )
}
