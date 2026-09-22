# InstaScribe release plan — three publishable milestones

**Date:** 2026-08-06 · **Source of authority:** `docs/implementation/INSTASCRIBE_STAGED_IMPLEMENTATION_HANDOFF.md` (§0, §5, §18)
**Rule:** acceptance gates override calendar dates. Nothing is claimed on the CV until its gate passes. Timeboxes are prioritization tools, not permission to skip evidence.

| Release | Branch | Tag (proposed) | Target window | Outcome |
|---|---|---|---|---|
| v0.1 Cloud Core | `feat/aws-cloud-core` | `v0.1.0-cloud-core` | ~7 focused days | Live AWS vertical slice, existing Vite frontend |
| v0.2 Portfolio Strong | `feat/aws-portfolio-hardening` (from accepted v0.1 tag) | `v0.2.0-portfolio-strong` | next 5–7 focused days | Parity + reliability + IaC + CI/CD + observability + evidence |
| v0.3 (conditional decision gate — Next.js is the retained candidate, ADR-0008 §6) | `feat/nextjs-migration` (from accepted v0.2 tag, if selected) | `v0.3.0-nextjs` (if selected) | next 4–6 focused days, if selected | Third-release content decided after v0.2 evidence; candidate: Next.js App Router frontend on ECS, FastAPI unchanged |

Every task below is assigned to exactly one milestone. Anything not listed for v0.1 is **deferred by default** — the Day-7 gate is protected by keeping v0.1's scope at the mandatory user journey and nothing else.

---

## 1. v0.1 Cloud Core — task list (the only work permitted before the first gate)

### Critical path (ordered; the Day-7 line)

| # | Task | Day (target) |
|---|---|---|
| A0 | Container-feasibility gate (first blocking): **G0a** runtime/builder/control-image/platform proof (`linux/amd64`), then **G0b** minimal pipeline-probe worker image (owns `services/worker/{Dockerfile,requirements.in,requirements.txt}` + smoke script) run on the fixture with measurements — stop if the fixture cannot complete | 1 |
| A1 | Local scaffolding: `docker-compose.yml` (PostgreSQL + LocalStack S3/SQS, dual internal/browser endpoints), `services/api` FastAPI skeleton with `/healthz` (health-only; DB-backed `/readyz` lands with A2) | 1 |
| A2 | `jobs` + `artifacts` + `scene_overrides` tables, SQLAlchemy models, Alembic init + first migration | 1 |
| A3 | Job create endpoint with presigned POST (LocalStack), portfolio limits, demo-token check | 1–2 |
| A4 | `upload-complete` (HeadObject verify → `UPLOAD_COMPLETE` → SQS send → `QUEUED`, enqueue-failure recorded), job get/list, status mapping to legacy frontend strings | 2 |
| A5 | Worker service: SQS consume, conditional-claim SQL, temp workspace, S3 download, subprocess pipeline adapter (fake provider), progress mirroring to PostgreSQL | 2–3 |
| A6 | Artifact upload with deterministic keys + `artifacts` rows; manifest endpoint with presigned GETs | 3 |
| A7 | Frontend data loader: manifest consumption + upload flow switch to presigned POST + status polling against new API (smallest possible diff; no redesign) | 3 |
| A8 | Scene-override PATCH → PostgreSQL upsert; editor save path wired; survives refresh/restart | 3 |
| A9 | Local end-to-end green: create → upload → process (fake provider) → editor loads → edit persists; existing pytest/vitest/fixture-demo still green | 3 |
| A10 | Minimal Terraform (explicit, not modularized): VPC/subnets/SGs, ALB, ECS cluster + API/worker services, ECR ×2, RDS single-AZ encrypted, S3 frontend + private media buckets, CloudFront + SPA fallback, SQS + DLQ + redrive, task/execution IAM roles, CloudWatch log groups, secrets, AWS Budget | 4–5 |
| A11 | Separately approved bootstrap plan/apply with API=0/worker=0; build/push full-SHA images; run the declared one-shot Alembic task to verified head; separately reviewed API=1 plan/apply; readiness; Vite build to S3; CloudFront smoke | 5–6 |
| A12 | Cloud smoke: fake-provider end-to-end job in AWS; API-restart persistence check; scene-edit refresh check | 6 |
| A13 | One explicitly authorized real-provider short-video test (owner approval + key required) | 7 |
| A14 | Evidence packet `docs/releases/v0.1-cloud-core.md`: deployed commit/image tags, URL, smoke evidence, cost snapshot, screenshots, limitations, CV bullets; stop for review | 7 |

### v0.1 supporting requirements (on the path, not deferrable)

- Private media bucket: block-public-access, encryption, CORS to frontend origin, presigned POST size/type conditions (250 MB); the 5-minute duration limit is enforced by the worker's `ffprobe` validation (duration/MIME from the client are untrusted hints).
- Worker-side input validation before any model call: reject corrupt/non-video/over-duration/type-mismatched media as non-retryable failures.
- Server-side allowlists/bounds on provider, model, fps, chunk size, detail, frame quality, language, and prompt length; portfolio token required on every cloud API route except `/healthz`/`/readyz` (D6).
- Minimal structured JSON log envelope with redaction of tokens, secrets, presigned URLs, prompts, and tracebacks.
- Pre-public-deployment npm-audit triage (runtime vs dev exposure; reviewed updates only; no blanket `npm audit fix`).
- DLQ + bounded redrive (`maxReceiveCount` aligned to `max_attempts=3`); terminal-duplicate acknowledgement.
- Basic CloudWatch logs for API and worker; AWS Budget guardrail.
- Task-role separation (API vs worker vs execution), least privilege to prefixes/queue/secrets.
- Enqueue-failure recovery path (job never silently lost: `enqueue_failed_at`/`enqueue_error` + safe retry; worker may claim stuck `UPLOAD_COMPLETE`).
- Fixture demo and existing test suites stay green throughout.

## 2. v0.1 → v0.2 explicit defer list (not allowed to block the Day-7 gate)

| Deferred item | Reason it can wait |
|---|---|
| Smart Fill cloud parity | Editor works without it; fixture demo covers the UX story |
| TTS preview cloud parity | Deferrable per the fixed spec (§5), though the endpoint audit rates per-line preview core to the authoring loop (repo-audit §3) — the gap is disclosed in the release note; see risk R4 for the pre-agreed escalation |
| Asynchronous final export (`EXPORT_QUEUED`/`EXPORTING`/`COMPLETED` path) | v0.1 gate ends at `READY_FOR_REVIEW` + persisted edit; export stays a documented limitation |
| Character/entity rename parity (`PATCH …/entities/…`) | Editor read path suffices for the v0.1 journey |
| Project rename/star/delete parity (general job PATCH/DELETE) | Not in the mandatory v0.1 journey; v0.1 ships list/get only — client-driven reconcile works against those |
| Scene-override optimistic conflict rejection (stale-version 409) | v0.1 uses last-write-wins atomic row upserts (already strictly better than the legacy whole-file race); the current editor sends no version — see ADR-0002 |
| Processing leases, visibility heartbeats, expired-claim reclaim, cancellation | Single worker, one job at a time, generous visibility timeout in v0.1 |
| `pipeline_runs`/`pipeline_stage_runs` full telemetry | v0.1 mirrors coarse status/progress only |
| Transactional outbox | Direct enqueue + recorded failure is the v0.1 contract |
| Terraform modules and remote state/bootstrap backend | v0.1 ships explicit single-environment Terraform; G9.1 already includes the required service-zero bootstrap/migration/API-enable sequence |
| GitHub Actions OIDC deploy pipeline | v0.1 permits controlled manual deployment with recorded versions |
| CloudWatch dashboard + alarms beyond logs/budget/the mandatory DLQ>0 alarm | The DLQ>0 alarm is v0.1 (canonical mandatory alarm); dashboard and remaining alarms are v0.2 |
| Broader integration matrix + Playwright end-to-end suite | **Core PostgreSQL/LocalStack integration tests for the create→enqueue→process→manifest→override path (G4–G6) are v0.1 work, not deferred** — only the wider matrix and Playwright are v0.2 |
| Full structured-logging schema, dashboards, custom metrics | **A minimal structured JSON log envelope with explicit redaction (tokens, secrets, presigned URLs, prompts, raw tracebacks) is v0.1 work** — only dashboards/metrics/alarm tuning defer |
| Worker run-mode hardening beyond the D7 choice | **D7 selected at G9:** maximum 72-hour ephemeral evidence environment, worker disabled by default and manually enabled at max one only for controlled G11/G12 tests. Queue-depth autoscaling/automatic scale-to-zero remains v0.2 and is not claimed in v0.1. |
| S3 lifecycle fine-tuning beyond the v0.1 rules | Three-day current eligibility plus a subsequent three-day noncurrent window ships in v0.1; UTC rounding/asynchronous processing and manual teardown mean no 72-hour deletion guarantee |
| Broader operational runbook, benchmarks, latency/reliability tables, demo video and case study | G9 now includes the bounded cost/rollback/teardown runbook required for safe v0.1 operation; the broader reliability/deployment runbook and measured evidence remain v0.2. |
| Entity/character rename parity (`PATCH …/entities/…` rewrites two served JSON artifacts, repo-audit §3) | Not in the mandatory v0.1 journey; needs an S3-artifact rewrite or DB-backed scenes design — v0.2 |
| Provider picker persistence (`POST /api/providers` is process-memory today, factory.py:29–43) | v0.1 pins the provider on the job row at creation; the Settings picker stays legacy/local |
| `GET /api/jobs/{id}/evaluation` + `?ids=` batch list | Frontend-orphaned today (repo-audit §3 "Anything unroutable") |
| Study-mode cloud parity (sessions, event logs, questionnaire config) | Study runs stay on the legacy local/Fly deployment; cloud v0.1 explicitly excludes them from its claim |
| Structured JSON access/error responses beyond `error_code`/`error_message` | Full log schema lands with v0.2 observability |

## 3. v0.2 Portfolio Strong — task list

> **Benchmark contract (ADR-0008 §4):** the v0.2 benchmark explicitly reports completion rate, structured-output validity, dialogue-gap/timing fit, TTS overflow, loudness/assembly validation, retries/failures, latency and estimated cost per source minute, a qualitative error taxonomy, and version-to-version comparisons. Review states (generated/edited/approved/rejected + timestamps/versioning) also land in v0.2 — `active` is never overloaded as review status.

Route parity (rename/star/delete/reconcile, entities, overrides GET), Smart Fill + TTS preview parity,
async export + signed download, full state machine + illegal-transition tests, conditional claims +
leases + heartbeats + duplicate handling + retries + cancellation + DLQ tests, complete Alembic
schema review + indexes, Terraform modules + remote state, GitHub Actions OIDC + deploy automation,
structured logs + dashboard + alarms + budget review, integration tests + Playwright E2E,
benchmark/cost/latency/reliability evidence, architecture diagrams + ADR updates + README + runbook +
demo video + case study. The immutable migration task and manual plan/apply separation already ship
in v0.1 after G9.1 and are not deferred.

## 4. v0.3 — conditional decision gate (Next.js is the candidate, not the definition)

> **ADR-0008 §6:** after the v0.2 evidence gate, the owner compares this Next.js candidate against editor UX, evaluation depth, accessibility validation, reliability and cost work, and decides the third release's content. The plan below is retained as the candidate's design.

Branch from accepted v0.2 tag; Next.js App Router compatibility build; route-segment migration (per the v0.3 inventory in `repo-audit.md` §8); editor stays a Client Component subtree; Server Components only for shells/layouts/metadata; no business logic in Route Handlers; Next.js lint/type/build/test + Docker image + ECR; ECS service + ALB path routing (`/api/*` → FastAPI) + CloudFront behaviors + health checks; route-parity + Playwright + cloud smoke; cutover with v0.2 retained as rollback; `docs/releases/v0.3-nextjs.md`; archive Vite app only after rollback validation.

## 5. Stop-and-publish gates

After each milestone: stop implementation → run the acceptance suite → write `docs/releases/<milestone>.md` (proposed tag, SHA, URL, architecture-as-deployed, smoke evidence, one measured result, screenshots, limitations, CV bullets, README wording) → wait for explicit owner authorization before creating **any** tag (even a local one — this supersedes the spec §0 local-tag step per the Phase 0 correction gate), pushing, releasing, or starting the next milestone.

CV claims permitted per gate are exactly the handoff's §18 wordings (as amended: "persistent human edit") — nothing stronger, "production-style" never "production-grade". Every public evidence packet states fixture licensing, which stages are real versus fake, what is pre-generated, and exact keyless replay/checksum commands (ADR-0008 §4).
