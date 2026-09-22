# InstaScribe v0.1 Cloud Core — implementation plan

**Date:** 2026-08-06 · **Status:** Phase 0 output — no functional code written yet
**Inputs:** `docs/cloud-migration/repo-audit.md` (all citations there), `docs/implementation/INSTASCRIBE_STAGED_IMPLEMENTATION_HANDOFF.md` (fixed decisions), ADRs 0001–0007.

This plan covers **only** Milestone A (`v0.1.0-cloud-core`). Everything else is listed in `release-plan.md` as deferred. The mandatory v0.1 user journey (handoff §5): live Vite frontend → portfolio token → job create → direct-to-private-S3 upload → PostgreSQL state → SQS → ECS worker runs the existing pipeline via adapter → artifacts in S3 behind a manifest → editor opens scenes+video → one scene edit survives refresh/restart → fake-provider cloud smoke + one authorized real-provider test.

---

## 1. Architecture and key audit-driven decisions

1. **The pipeline is wrapped, not refactored** (ADR-0004). The audit confirmed `run_job.py` is a self-contained batch program: argv = `(job_id, settings.json path)`, outputs = files, progress = `status.json` (repo-audit §5 "Safest adapter seam"). The worker synthesizes the expected workspace tree (`modular_pipeline/` + sibling `App/public/{data,videos}` dirs), writes `settings.json` + a local `video.mp4` copy of the source object, launches the subprocess, polls `status.json`, mirrors progress to PostgreSQL, uploads outputs to S3. The env-at-import freeze (`config.py:12–48`) stays contained behind the process boundary. **Subprocess contract corrections:** imports and argv/settings parsing can fail *before* `run_job.py` enters its `__main__` `try/except` (run_job.py:27–114 precede it), so a non-zero or signal exit is **authoritative even when `status.json` is absent, stale, or still says `queued`/`processing`**. The adapter captures bounded stderr (tail-capped), classifies a safe public `error_code`/short message, and keeps full diagnostics only in worker logs. There is also a **success-order race**: `run_job.py` writes legacy `ready` into `status.json` *before* writing `result.json` (run_job.py:395 vs 398–410), so the worker must never key success off `status.json` — it waits for child exit, **validates the required artifact set, uploads objects, persists `artifacts` rows, and only then** transitions PostgreSQL to `READY_FOR_REVIEW`. Required v0.1 artifacts: the source video object and a valid, parseable `scenes.json` with ≥1 scene, plus `entities.json`, `audio_events.json`, `ad_placement_gaps.json`, and `transcript.json` present (empty arrays are legal when audio extraction is off, run_job.py:269–274). Optional (absence degrades, never fails): `poster.jpg`, `poster.avif`, LQIP placeholder, `system_info.json`. A missing required artifact is a **failure**, not success.
2. **Status vocabulary is preserved, not migrated** (ADR-0007). The frontend understands exactly `queued | processing | ready | failed` plus stage strings `initializing, extracting_frames, transcribing_audio, analyzing_frames, exporting, complete` (repo-audit §6 "Job status model"). The new API maps internal states onto these; zero frontend status-handling changes.
3. **The frontend change set is a loader change, not a redesign.** The audit found every artifact read is suffix-concatenation on `dataPath` and URLs are persisted in localStorage (repo-audit §6 "Hard-coded path assumptions") — both incompatible with expiring presigned URLs. v0.1 therefore introduces a **manifest** (`GET /api/v1/jobs/{id}/manifest`) and changes the fetchers to resolve logical names → URLs at request time, persisting only job IDs. The demo build is untouched: `demoApi.ts` short-circuits before any of these code paths and reads committed fixtures.
4. **One worker image carries the full ML stack.** The deployed Dockerfile has never contained the pipeline (`requirements-server.txt` excludes numpy/torch/faster-whisper — repo-audit §7 "Deploy surface"). The v0.1 worker image is a **first-time containerization**: `python:3.12-slim` + ffmpeg + `requirements.txt` + baked faster-whisper `medium` weights (avoids multi-GB cold-start downloads via `~/.cache/instascribe`, `audio_whisperx_pipeline.py:45`). The fake-provider path still exercises real ffmpeg + (with audio on) the real VAD/ASR stack, so one image serves smoke and real runs.
5. **Exports, TTS preview, Smart Fill, entity rename, provider picker, and study mode stay on the legacy path in v0.1** (release-plan defer list). The cloud v0.1 journey ends at `READY_FOR_REVIEW` + persisted scene edit. This is a visible product gap in the cloud deployment and is disclosed in the release note; the fixture demo continues to show the full editing story with zero keys.
6. **Provider pinning moves to the job row, defaulting to `fake`.** `POST /api/providers`' process-global `_OVERRIDE` (factory.py:29–43) does not survive restarts and cannot span containers. v0.1 records `provider` on the job at creation from a **server-side allowlist**, and the worker exports `INSTASCRIBE_BACKEND` from the job row — same mechanism the Flask server uses today (`server.py:111–112`). Local and test jobs default server-side to `fake`; production **must not default to a paid provider** until its secret and spend are explicitly approved (decision D5/G12). There is **no public provider selector in v0.1** — the Settings picker stays legacy/local.
7. **Dependencies are per-service and deterministic.** The root `requirements.txt` contains none of FastAPI/SQLAlchemy/Alembic/psycopg/boto3 and is floor-pinned, not locked (the `pyproject.toml` comment "dependencies are pinned" overstates — they are `>=` floors). Each new service owns its manifest: `services/api/requirements.in` and `services/worker/requirements.in`, compiled to fully pinned `requirements.txt` lockfiles with `uv pip compile` (uv 0.11.x is already the local toolchain). Persistence is **synchronous** SQLAlchemy 2 + psycopg 3 (no async engine for the bounded v0.1 path). API and worker images must build cleanly from their declared manifests alone.

## 2. New/changed file map (target layout, handoff §6)

```text
services/api/app/{main.py, core/{config.py,security.py}, db/{base.py,session.py},
                  models/{job.py,artifact.py,scene_override.py},
                  repositories/{jobs.py,artifacts.py,overrides.py},
                  schemas/{jobs.py,manifest.py,queue.py},
                  services/{s3.py,sqs.py,state.py},
                  api/{jobs.py,manifest.py,scenes.py,health.py}}
services/api/{Dockerfile, requirements.in, requirements.txt}   # requirements.txt compiled+pinned via `uv pip compile`
services/worker/app/{main.py,consumer.py,claim.py,executor.py,workspace.py,artifact_uploader.py}   # G5
services/worker/app/g0_smoke.py                                 # G0 container-feasibility probe
services/worker/{Dockerfile, requirements.in, requirements.txt} # created at G0; pinned via `uv pip compile`; full pipeline stack
packages/contracts/queue_message.py
migrations/ (alembic.ini, env.py, versions/0001_core_tables.py)
infrastructure/terraform/portfolio/*.tf        (explicit, un-modularized — §6 below)
docker-compose.yml
Makefile                                        (new targets: bootstrap, dev, migrate, smoke-cloud)
tests/unit/…  tests/integration/…
App/src/lib/{api.ts, uploadApi.ts, manifest.ts(new), queryKeys.ts}
App/src/features/upload/hooks/useUploadFlow.ts
App/src/features/upload/components/{StepFileUpload.tsx or StepSettings.tsx}   (token input only)
App/src/store/appStore.ts                       (persist IDs, not URLs)
App/src/features/editor/pages/EditorPage.tsx    (hasData gate → manifest presence)
```

The Flask server, pipeline modules, fixture demo, and study mode are **not modified** in v0.1 (only read by the worker's vendored copy of `modular_pipeline/`).

## 3. File-by-file gate sequence

Each gate: **Files · Prerequisite · Outcome · Verification · Rollback · Critical-path · Approval**.

### G0 — Container-feasibility gate (Day 1, first blocking gate)
- **Rationale:** the Phase 0 environment had no Docker CLI/daemon, so every image claim is unverified (repo-audit §2 item 13); the worker image is a first-time ML-stack containerization (risk R1).
- **G0 owns the initial worker-container files** (moved here from G5 so the gate can prove itself): `services/worker/Dockerfile`, `services/worker/requirements.in`, the compiled/pinned `services/worker/requirements.txt`, and a minimal container smoke entrypoint/script. **No** SQS consumer, PostgreSQL integration, or production worker orchestration — those remain G5, which builds its modules on top of this image foundation.

**G0a — runtime, builder, control-image, and platform proof:**
- Record `docker version`/`docker info`, active builder and BuildKit/buildx versions, host architecture and CPU/memory/disk.
- Declare the ECS image target explicitly: **`linux/amd64`** (ARM64 only after the torch/faster-whisper stack is verified on Fargate ARM).
- Build the **existing** root `Dockerfile` as a control (or record the exact classified reason it cannot build).
- Verify no credentials, `.env` files, runtime job data, or unrelated assets enter either image context (`.dockerignore` review).
- If the runtime is unavailable or the control build exposes an environmental prerequisite, stop and report without starting G0b.

**G0b — minimal pipeline-probe worker image and fixture execution:**
- Python 3.12 Linux amd64 base; ffmpeg/ffprobe; deterministic pinned dependencies covering the full pipeline stack; pipeline code plus only the fixture assets/layout `run_job.py` requires; non-root runtime user; writable bounded workspace/cache paths; faster-whisper `medium` weights baked reproducibly (no unplanned multi-GB runtime download).
- Run the committed fixture with `INSTASCRIBE_BACKEND=fake` and audio extraction **on**, through the unrefactored `run_job.py` subprocess contract in a synthesized job workspace; require exit 0 plus validation of the required artifact set; demonstrate a deliberately broken pre-`main()` case is detected from the nonzero exit even with `status.json` absent/stale.
- Record build duration, compressed-size estimate and unpacked size, peak container memory/CPU, peak temporary-workspace use, processing duration, image architecture, and whether all weights were baked.

- **Stop condition:** if the fixture job cannot complete in the local worker container, **stop Phase 1 and report** — do not proceed to AWS-facing work on an unproven image.
- **Prereq:** none. **Critical-path:** yes — blocks everything. **Approval:** none.

### G1 — Local stack scaffolding (Day 1)
- **Files:** `docker-compose.yml` (PostgreSQL 16, LocalStack S3+SQS, api; worker joins at G5 — if a compose entry exists earlier it is a clearly labelled no-op placeholder), `services/api/app/main.py` (+`api/health.py`), `services/api/{Dockerfile,requirements.in,requirements.txt}`, Makefile targets.
- **Prereq:** G0. **Outcome:** `docker compose up --build` starts PG/LocalStack and a **health-only** API: `GET /healthz` (process alive, no dependencies) returns 200, with an `/api/healthz` alias for the CloudFront-coherent path (§6). DB-backed `GET /readyz` belongs to G2. **LocalStack bootstrap is owned by a compose-run init script** (idempotent, versioned in the repo) that creates: the private media bucket with **browser CORS** (local Vite origin, `POST`/`GET`/`HEAD` methods, headers needed by presigned POST, and exposed Range/Accept-Ranges headers so `<video>` seeking works), the work queue, the DLQ, and the redrive policy (`maxReceiveCount=3`). S3 clients use **path-style addressing** with **two endpoint views** — container-internal (`http://localstack:4566`) for API/worker SDK calls and the host-browser endpoint (`http://localhost:4566`) for **presigning**, so browser-visible presigned URLs never leak the `localstack:4566` hostname.
- **Verify:** `curl :8000/healthz`; API image builds cleanly from its declared manifest alone; existing `pytest -q` + `npm test` remain green (nothing touched).
- **Rollback:** delete new files; zero impact on legacy app. **Critical-path:** yes. **Approval:** none.

### G2 — Database foundation (Day 1)
- **Files:** `migrations/*`, `models/{job,artifact,scene_override}.py`, `db/*`, `repositories/jobs.py`, `services/state.py` (legal-transition table per ADR-0007), `api/health.py` (`GET /readyz`: DB connectivity + essential config, plus the `/api/readyz` alias), unit tests `tests/unit/test_state_machine.py`.
- **Prereq:** G1. **Outcome:** `alembic upgrade head` builds `jobs`, `artifacts`, `scene_overrides` per handoff §7 (v0.1-lean: `pipeline_runs`/`pipeline_stage_runs` deferred); illegal transitions raise domain errors; `/readyz` goes live here.
- **Verify:** `make migrate` against empty compose PG; state-transition unit tests; `curl :8000/readyz`.
- **Rollback:** `alembic downgrade base`. **Critical-path:** yes. **Approval:** none.

> **G3/G4 semantics (ADR-0008 §1–2):** `POST /api/v1/jobs` creates one durable **project** plus its initial **processing job** atomically (distinct IDs; legacy summary adapter documented). Because `AWAITING_UPLOAD` sits outside `uq_jobs_one_compute_active`, creation does **not** reserve the compute slot and multiple pending reservations may coexist; the database guarantee begins when G4's conditional transition into `UPLOAD_COMPLETE`/`QUEUED` hits the partial index — G4 catches that unique violation and returns a safe conflict/retry response. Any G3 active-job preflight is advisory UX, never race-safe enforcement.

### G3 — Job creation, portfolio token, presigned upload (Days 1–2)
- **Files:** `api/jobs.py` (`POST /api/v1/jobs`, `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}` — **no general PATCH/DELETE in v0.1**; rename/star/delete parity is v0.2), `core/security.py` (constant-time token hash compare, header `X-Portfolio-Token`; the dependency is **mounted centrally on the `/api/v1` router**, so every present and future route on it — including G6's manifest/override routes — inherits the check by construction; only `/healthz`/`/readyz` and their `/api/` aliases live outside the router — decision D6 default), `services/s3.py` (presigned **POST** with content-length ≤ 250 MB and content-type conditions), `schemas/jobs.py` (server-side **allowlists/bounds** for provider, model, fps, chunk size, detail level, frame quality, language, and custom-prompt length — a token holder cannot select unplanned spend or workload settings), narrow FastAPI CORS for the local Vite origin only (methods + `X-Portfolio-Token` preflight).
- **Prereq:** G2. **Outcome:** job row in `AWAITING_UPLOAD` + presigned POST against LocalStack; canonical object key **`uploads/{job_id}/source/{sanitized_filename}`** persisted on the job (`input_object_key`); the one-active-processing-job portfolio limit is enforced **atomically** — a partial unique index over the active statuses makes the conflicting insert/transition fail in the database itself, never a race-prone count-then-insert check; size/type limits enforced by the POST policy conditions; client-declared duration and MIME are recorded as **untrusted hints** — the 5-minute duration limit is **not** expressible as a POST-policy condition and is enforced by the worker's `ffprobe` check (G5); list/get responses carry the legacy summary shape (`status`, `progress`, `stage`, `project_name`, …) so the existing dashboard reconcile keeps working.
- **Verify:** unit tests for limits, allowlists + token; scripted browser-style presigned **POST** upload to LocalStack succeeds; oversize rejected by the POST policy; missing/wrong token rejected on every route.
- **Rollback:** endpoints are additive; legacy `/api/jobs` untouched. **Critical-path:** yes. **Approval:** none.

### G4 — Upload-complete and safe enqueue (Day 2)
- **Files:** `api/jobs.py` (`POST /api/v1/jobs/{id}/upload-complete`), `services/sqs.py`, `packages/contracts/queue_message.py` (`{schemaVersion:1, messageId, taskType:"ANALYZE", jobId, requestedAt}`).
- **Prereq:** G3. **Outcome:** HeadObject verify (size/type vs job row) → `UPLOAD_COMPLETE` → SQS send → `QUEUED`; on send failure job stays `UPLOAD_COMPLETE` with `enqueue_failed_at`/`enqueue_error` and a retry path; repeat calls idempotent. **Both publication races are covered:** (a) `SendMessage` fails → recovery above; (b) send **succeeds** but the final `UPLOAD_COMPLETE → QUEUED` update fails → the worker's claim set includes `UPLOAD_COMPLETE`, and the API's `→ QUEUED` update is **conditional** (`WHERE status = 'UPLOAD_COMPLETE'`) so it can never overwrite a later worker state (`PROCESSING`, terminal) with `QUEUED`.
- **Verify:** integration tests (compose, these are v0.1 work, not deferred): full create→upload→complete→message-visible; kill-SQS test leaves job retryable, never lost; **API-side fault injection** for race (b): simulate the post-send update failing, then set the job to a later state directly and assert the conditional `→ QUEUED` update no-ops. (The full worker-in-the-loop version of this race test — worker actually claims `UPLOAD_COMPLETE` and reaches `PROCESSING` before the late API update — needs the G5 worker and runs there.)
- **Rollback:** additive. **Critical-path:** yes. **Approval:** none.

### G5 — Worker with subprocess pipeline adapter (Days 2–3)
- **Files:** `services/worker/app/*` (consumer: long-poll SQS; claim: one conditional `UPDATE jobs SET status='PROCESSING', worker_id=…, attempt_count=attempt_count+1 WHERE id=… AND status IN ('QUEUED','UPLOAD_COMPLETE') RETURNING …`; workspace: synthesize `modular_pipeline/` tree + `jobs/{id}/{video.mp4,settings.json}` + seeded `status.json`, downloading the source object by its persisted `input_object_key` (`uploads/{job_id}/source/{sanitized_filename}`) into the local workspace name `video.mp4`; executor: `Popen([python, run_job.py, job_id, settings_path], cwd=workspace/modular_pipeline)` owning the handle with timeout; poll `status.json` → mirror `status/progress/stage` to PostgreSQL; artifact_uploader: **attempt-scoped** keys `jobs/{id}/attempts/{attempt}/analysis/*.json`, `jobs/{id}/attempts/{attempt}/posters/poster.jpg` + `artifacts` upsert (G5.1: unscoped keys would let a stale attempt overwrite a winner's bytes; rows select the winning attempt atomically); `finally:` workspace deletion) — built **on top of the G0 image foundation** (`services/worker/{Dockerfile,requirements.in,requirements.txt}` already exist from G0; G5 adds the consumer/claim/executor modules, not the image). **G5 must produce a production image target/CMD that excludes the Sintel fixture and the G0 smoke script** (multi-stage or named build target — the G0 probe assets never ship in the deployed image), and — before G9 — the production target pins the whisper model revision (`08e178d48790749d25932bbc082711ddcfdfbc4f` at G0) and the base-image digest instead of the moving `medium` alias and `python:3.12-slim` tag.
- **Input validation before any model call:** the worker runs `ffprobe` on the downloaded source and **rejects** invalid/corrupt/non-video input, actual duration over 5 minutes, and container/extension/MIME pairing mismatches — client-declared duration and MIME are untrusted hints (G3), **a false declaration cannot bypass the actual duration cap, and the measured duration replaces the hint** (persisted under the claim guard before model work — G5.1 C3). The worker also binds to an explicit `INSTASCRIBE_PIPELINE_REVISION` (`dev` locally): a job persisted for a different revision fails as non-retryable `pipeline_revision_mismatch` before any source/model work, never silently processing under false provenance. Rejection is a non-retryable validation failure.
- **Success path ordering (subprocess contract, §1.1):** wait for child exit → exit code authoritative (even if `status.json` is stale — parse/import failures precede run_job's `try/except`) → validate the required artifact set (§1.1) → upload objects → persist `artifacts` rows → only then `PROCESSING → READY_FOR_REVIEW`. Bounded stderr tail is captured; the public error is a classified `error_code` + short message; full diagnostics go to worker logs only.
- **Retry semantics (DB attempts aligned with SQS receive/redrive):** `maxReceiveCount` = `jobs.max_attempts` = 3; `attempt_count` increments on claim. **Complete failure classification:**
  - *Deterministic input/settings validation failures* (ffprobe rejection, corrupt/oversize/over-duration media, unparseable or out-of-allowlist settings): **non-retryable** — `PROCESSING → FAILED`, message **deleted**. Retrying deterministic failures only burns attempts.
  - *Everything else* — unexpected child nonzero exits, adapter timeouts, transient AWS/network/provider errors, and **missing-required-artifact failures** — uses one documented bounded default: **retryable up to `max_attempts`**, each classification covered by a test.
  - *Retryable path without a crash gap:* the requeue is **one durable atomic transition** `PROCESSING → QUEUED` (attempt count + safe error metadata updated in the same statement); `RETRYING` is a logical/logged phase, never a durable intermediate state, so no crash between two writes can strand a job in an unclaimable status. The message is **not** deleted (visibility lapses for redelivery).
  - *Exhausted attempts*: `PROCESSING → FAILED`, message **left undeleted** so SQS redrives it to the DLQ; terminal-duplicate handling is scoped so it **never consumes a failure message before redrive** — duplicates of *successful* terminal jobs are acknowledged/deleted, duplicates of *failed-exhausted* jobs are left to the redrive policy.
- **Logging:** minimal structured JSON envelope (timestamp, level, service, job_id, message_id, attempt, stage, duration_ms, error_code) with explicit redaction of tokens, secrets, presigned URLs, prompts, and raw tracebacks from anything client-visible. Dashboards/custom metrics remain v0.2.
- **Prereq:** G4 (+ G0 image evidence). **Outcome:** fake-provider job runs end-to-end in compose: `QUEUED→PROCESSING→READY_FOR_REVIEW` with artifacts in LocalStack S3.
- **Verify:** integration tests (v0.1 work) — happy path; duplicate delivery of a completed job's message is a no-op; **first attempt fails → redelivery succeeds**; **max attempts produces both a durable `FAILED` job and a DLQ message**; poison message reaches the DLQ; corrupt media / spoofed type / falsely declared duration / oversize are rejected as validation failures; API restart mid-processing does not lose the job (state in PG); **worker-in-the-loop DB/SQS race test (moved from G4):** post-send API update fails → worker claims `UPLOAD_COMPLETE` and reaches `PROCESSING` → the late API update must not overwrite the worker state.
- **Rollback:** additive. **Critical-path:** yes — the single riskiest gate; its image work starts at G0. **Approval:** none.

### G6 — Manifest and scene-override persistence (Day 3)
- **Files:** `api/manifest.py` (`GET /api/v1/jobs/{id}/manifest` → `{expiresAt, artifacts:{video,scenes,entities,audioEvents,placementGaps,transcript,poster}}` as short-lived presigned GETs; keys stored, URLs never stored), `api/scenes.py` (`PATCH /api/v1/jobs/{id}/scenes/{scene_id}` → atomic upsert with `version` bump; `GET /api/v1/jobs/{id}/overrides` returning the legacy `{scene_id: override}` map), `repositories/overrides.py`.
- **Prereq:** G5. **Outcome:** editor data loadable entirely from manifest URLs; one scene edit persists across API restart. Scene overrides use a **last-write-wins atomic row upsert** per `(job_id, scene_id)` in v0.1 — this already eliminates the legacy whole-file lost-update race; the `version` column is recorded but stale-version **conflict rejection (409) is explicitly deferred to v0.2** (the current editor sends no version; see ADR-0002). **Upsert note (ADR-0008 §3):** Core `ON CONFLICT DO UPDATE` statements must explicitly set `updated_at = now()` and increment `version` — ORM `onupdate` does not apply to Core upserts. Original generated scene artifacts stay immutable; overrides live separately; the v0.1 claim is "persistent human edit".
- **Verify:** integration (v0.1 work) — manifest URLs fetch from LocalStack **via the host-browser endpoint** (no `localstack:4566` leakage); override upsert visible after `docker compose restart api`; concurrency test: parallel PATCHes to different scenes all land (replaces the per-process lock, repo-audit §4 note 1); **explicit unauthorized tests**: manifest and override routes inherit the router-mounted token check and return 401/403 without a valid `X-Portfolio-Token`.
- **Rollback:** additive. **Critical-path:** yes. **Approval:** none.

### G7 — Frontend cloud integration (Day 3, smallest possible diff)
- **Files:** as listed in §2. Changes: (a) `uploadApi.ts` — create job via `/api/v1/jobs` (JSON metadata + token header), presigned POST upload, `upload-complete`, then poll `GET /api/v1/jobs/{id}` (legacy-shaped response); (b) new `manifest.ts` + `api.ts` fetchers resolving scenes/entities/audio/gaps/video/poster through the manifest (TanStack query keyed `['projects', id, 'manifest']`, `staleTime` below URL expiry); (c) `appStore.ts` persists job IDs and re-resolves URLs on load (fixes the stale-presigned-URL trap, repo-audit §6 item 2); (d) a token input field in the upload flow with **centralized token injection** — one client helper attaches `X-Portfolio-Token` to create, upload-complete, poll/list/get, manifest, and scene-override requests; the token lives in memory plus `sessionStorage` for refresh continuity and **never** in localStorage, URLs/query strings, logs, build-time variables, or error bodies; (e) `EditorPage.tsx` `hasData` gate keyed on manifest availability. **Adapter rule:** the client retains BOTH `projectId` and `jobId` end-to-end through G7 — they are never collapsed or treated as interchangeable (ADR-0008 §1).
- **Prereq:** G6. **Outcome:** the existing Vite app performs the whole journey against the local cloud stack; demo build (`--mode demo`) byte-for-byte unaffected in behavior — `demoApi.ts` branches run before any new code path.
- **Verify:** `npm run lint`, `npx tsc -b`, `npm test`, production build, demo build + preview smoke (same as baseline §2); manual local E2E; a vitest unit for the manifest resolver.
- **Rollback:** git revert of the frontend commit restores the pure-legacy client. **Critical-path:** yes. **Approval:** none.

### G8 — Local acceptance freeze (Day 3–4)
- **Outcome:** everything in Phase 1's acceptance list green locally (handoff §18 Phase 1) — the checkpoint where the local vertical slice is demonstrably done. (No tag of any kind; tags require explicit owner authorization, §8.)
- **Mandatory sizing check (R2):** a local **five-minute fake-provider memory test** in the 8 GB worker container must pass before G8 closes. If it cannot pass within 8 GB, either the task memory is raised or the advertised v0.1 duration limit is lowered — one of the two, decided before any public deployment.
- **Mandatory evaluation contract (ADR-0008 §4):** before G8 closes, freeze the evaluation manifest — 3–5 rights-cleared **cases** with source/licence/hash, deterministic structural expectations, and a short manual groundedness/usefulness rubric. Non-overlapping bounded windows from one verified rights-cleared source are the permitted G8 safe minimum (harness/provenance/rubric frozen, not corpus diversity — distinct clips are v0.2 and need owner/licence review). No media added without verified rights.
- **Verify:** scripted `make smoke-local`: create→upload→process(fake)→manifest→edit→restart→edit persists; full existing suites green.
- **Approval:** none. **Critical-path:** yes.

### G9 — Terraform minimum (Days 4–5)
- **Files:** `infrastructure/terraform/portfolio/{providers,versions,variables,vpc,alb,ecs,rds,s3,cloudfront,sqs,ecr,iam,logs,secrets,budget,outputs}.tf` — explicit single-environment config (no modules yet, per handoff §14).
- **Resources:** §6 below. **Prereq:** G8; the owner has selected region `eu-west-2`, while the exact AWS account/IAM identity remains D1. **Before `terraform init`:** ensure ignore rules cover `.terraform/`, `*.tfstate*`, saved plan files, crash logs, and secret `*.tfvars`; commit `.terraform.lock.hcl` once Terraform work is authorized. **Image reproducibility prereqs (both services): COMPLETED LOCALLY at G8.1/G8.2.** The production API and worker use digest-pinned bases, explicit `linux/amd64` builds, complete source-input binding and local image proofs; the worker additionally pins the Whisper revision. Remote ECR manifest digests remain a later authorized-push/deploy boundary.
- **G9.1 forward correction (2026-08-08):** local Terraform now defaults API/worker services to zero,
  provides a dedicated immutable API-image Alembic task, and requires a second reviewed plan/apply
  before enabling one API. One full lowercase 40-hex SHA binds both images and job provenance.
  Origin verification uses an exact 64-hex active value plus a one/two-value overlap list. Worker
  ephemeral storage is explicitly 40 GiB and costed provisionally. S3 three-day rules are lifecycle
  eligibility, not a 72-hour deletion promise. See `g9-1-local-correction-evidence.md`. Credentialed
  planning remains **NO-GO** pending owner gates and review.
- **G9.2 forward correction (2026-08-08):** credentialed execution remains NO-GO, but the later
  authorized migration boundary is now a fail-closed account-pinned runner: it enforces service-zero
  outputs, structured network JSON, zero ECS failures, exactly one stopped migration container and
  numeric exit 0 before log evidence. Post-enable verification is a separate read-only script using
  `services-stable` plus bounded readiness retry; neither script plans, applies, enables or mutates
  state. Deterministic mocks cover all failure/success paths; see `g9-2-local-runner-evidence.md`.
- **Verify:** `terraform fmt -check`, `terraform validate` and mocked `terraform test` (no credentials needed); `terraform plan` **requires owner credentials — approval point**; the pre-apply estimate is `g9-pre-apply-cost-model.md` (see also §6).
- **Rollback:** nothing applied yet. **Critical-path:** yes. **Approval:** plan may run read-only with owner creds; **apply requires explicit authorization**.

### G10 — Deploy and wire (Days 5–6) — **owner approval required (paid resources)**
- **Prereq (pre-public-deployment triage):** classify the recorded `npm audit` findings (14 advisories incl. 9 high, baseline §2 item 6) into runtime vs development-only exposure; update only through reviewed and tested dependency changes; record justified residual risk. **No indiscriminate `npm audit fix`.**
- **Steps (each plan/apply/run separately authorized):** reviewed bootstrap plan/apply with API=0 and
  worker=0 → build/push both immutable full-SHA images → run the declared no-service Alembic ECS task
  and require exit 0 plus `current --check-heads` → reviewed enablement plan/apply with API=1 →
  `services-stable` and bounded readiness verification → build Vite with **`VITE_API_BASE=""`** →
  sync frontend → smoke. No API is intentionally
  routable before migration success and the enablement apply.
- **Verify:** `/healthz`+`/readyz` through CloudFront `/api/*`; CloudFront serves the app; an API error path returns JSON (never rewritten to `index.html`); recorded: deployed commit, image digests, plan file.
- **Rollback:** *application rollback* = redeploy the previous image tags / previous frontend build (non-destructive, the default recovery); *environment teardown* = `terraform destroy`, a separate destructive decision (§8).

### G11 — Cloud smoke: fake provider + persistence (Day 6)
- The scripted gate test in §5, run against AWS with `provider=fake`. **Approval:** none beyond G10 (no model spend).

### G12 — Authorized real-provider test + evidence packet (Day 7) — **owner approval required (model spend)**
- One short video (≤2 min) with `provider=openai` (needs `OPENAI_API_KEY` in Secrets Manager; note the `MAX_CALLS=100` per-process cap comfortably exceeds a 2-min/60 s-chunk job). Capture cost snapshot, screenshots, latency, tokens. Write `docs/releases/v0.1-cloud-core.md`. **No tag is created — even locally — without explicit owner authorization**; the proposed name `v0.1.0-cloud-core` is applied only when the owner authorizes it. **Stop for review.**

## 4. API compatibility map (v0.1)

| Legacy (Flask) | v0.1 cloud | Notes |
|---|---|---|
| `POST /api/jobs` multipart | `POST /api/v1/jobs` JSON + presigned POST + `upload-complete` | upload no longer transits the API (ADR-0003) |
| `GET /api/jobs/{id}` | same path shape on `/api/v1`, legacy response fields preserved; `data_path` replaced by manifest indirection | status/stage strings identical (ADR-0007) |
| `GET /api/jobs` | `GET /api/v1/jobs` legacy-shaped summaries | dashboard reconcile unchanged |
| `PATCH/DELETE /api/jobs/{id}` | **not in cloud v0.1** — rename/star/delete parity is v0.2 | when it lands, delete must also remove the S3 prefix (fixes the orphan bug, repo-audit §4 "Deletion") |
| `PATCH /api/jobs/{id}/scenes/{sid}`, `GET …/overrides` | same contracts, PG-backed | lock-free atomic upsert |
| `/data/*`, `/videos/*` | manifest presigned GETs | fixture demo keeps static paths |
| smart-fill, tts-preview, export*, entities, providers, evaluation, study* | **not in cloud v0.1** — legacy/local only | v0.2 parity work |

## 5. The v0.1 cloud release gate (exact test)

Automated (`make smoke-cloud`, fake provider) + manual checks:

1. Clean browser (no localStorage) → CloudFront URL loads the dashboard.
2. Upload without token → rejected (401/403). With token → job created (`AWAITING_UPLOAD` in PG — verify via API, not DB access).
3. Browser uploads the short fixture clip directly to S3 (network tab shows S3 POST, not the ALB).
4. `upload-complete` → job `QUEUED` → SQS delivery observable in worker logs.
5. Worker processes with fake provider; progress advances through the real stage strings; PG rows update.
6. Manifest returns presigned URLs; editor opens scenes + video (Range requests work).
7. Edit one scene → refresh → edit persists. Force a new API task (ECS stop) → poll + edit still present.
8. Duplicate SQS redelivery of the completed job's message → acknowledged, no second processing (worker log assertion).
9. Invalid input rejected: a corrupt/oversize/type-spoofed/over-duration upload fails with a classified validation error, not a hang or a model call.
10. DLQ empty; CloudWatch shows API+worker structured logs with no token/secret/presigned-URL/prompt leakage; budget alert armed and its notification confirmed received.
11. Record: deployed commit SHA, image digests, terraform plan hash, cost snapshot, screenshots.
12. Separately approved: one real-provider job (G12) — scenes contain genuine model output; token/cost recorded.

## 6. Terraform: v0.1 minimum and v0.2 delta

**v0.1 baseline surface (as corrected immediately below):** VPC (2 AZ public subnets for tasks/ALB
**plus 2 isolated/private DB subnets across AZs** feeding the RDS subnet group; IGW, routes; **no
NAT** — ADR-0005), security groups (ALB→API only; worker egress-only; RDS from task SGs only), **ALB
origin protection in two layers**: ingress restricted to the CloudFront origin-facing managed prefix
list **plus** a secret custom origin header injected by the CloudFront origin config and checked by an
ALB listener rule (non-matching requests get a fixed 403; rotation uses an overlap window; the prefix
list admits all CloudFront customers and the header is readable by account principals with
distribution-config access, so this prevents direct-origin bypass but is **not** an authentication
substitute), ALB + target group + health checks, ECS cluster + API/worker task definitions/services
(API ~0.25 vCPU/512 MB; worker **2 vCPU/8 GB** `linux/amd64` — G0 measured a 6.57 GiB container
peak and a 4 GB cap OOM-killed transcription; see `g0-container-feasibility.md` and R2), ECR ×2,
RDS PostgreSQL single-AZ encrypted (`db.t4g.micro`, private subnets, no public access, automated
backups), S3 ×2 (frontend; private media with BPA, SSE, **versioning enabled** for pinned `VersionId`,
CORS to the CloudFront origin, current and noncurrent lifecycle rules for abandoned uploads and
generated evidence media), **one CloudFront distribution**: default → Vite S3/OAC with a path-scoped
SPA rewrite only; uncached `/api/*` → ALB forwarding required methods, query strings and
`X-Portfolio-Token`; same-origin frontend URLs; `/api/healthz` and `/api/readyz` through CloudFront
while ALB target health uses `/healthz`. Also: SQS + DLQ (redrive 3, visibility 30 min), separate
execution/task IAM roles including exact-version worker reads, 14-day log groups, mandatory DLQ > 0
alarm, Secrets Manager (RDS-managed DB credentials, token hash, origin values, empty G12 OpenAI
shell), and a USD 25 AWS Budget with owner-designated alert recipient/test.

**G9.1 v0.1 corrections to the surface above:** API and worker services bootstrap at zero; a third,
one-shot migration task uses the immutable API image, a dedicated no-ingress SG, an empty task role,
least-privilege execution role, RDS-managed credentials, logs and an Alembic head check. One full
40-hex SHA is the only image/provenance input. Origin rotation is exact `[A] → [A,B]` with A active
→ `[A,B]` with B active → `[B]`, using 64-lowercase-hex values only. Worker storage is an explicit
provisional 40 GiB. Media current/noncurrent rules use separate three-day eligibility windows with
UTC rounding/asynchronous processing; they do not guarantee 72-hour deletion. The CloudFront
default certificate carries no claimed `TLSv1.2_2021` floor; R20 requires an owner acceptance or a
later authorized DNS + `us-east-1` ACM design. R19's HTTP origin leg remains separate.

**v0.2 hardening delta:** remote state + locking bootstrap, module extraction, OIDC deploy role,
queue-depth scale-to-zero worker, dashboard + remaining alarms, lifecycle/backup review and
private-subnet option. G9.1 moves the migration-task role and explicit plan/apply rollout separation
into v0.1 because they are bootstrap safety requirements.

**Cost-incurring / cannot-scale-to-zero:** ALB, RDS, API when enabled, public IPv4, Secrets Manager,
CloudFront/S3/SQS/ECR/logs/data transfer and any enabled worker. D7 is a maximum 72-hour environment
target with both services zero at bootstrap. The 2-vCPU/8-GiB worker adds a provisioned 40-GiB
filesystem; the charged extra 20 GiB plus the second origin secret brings the warning-case estimates
to about $5.63/24 h, $16.88/72 h and $39.38/7 d. This is planning, not measured billing.

## 7. Secrets, approvals, and prohibited-without-authorization actions

**Prerequisites owned by the owner:** AWS account + IAM identity for Terraform; approved Budget/SNS
recipient; portfolio token; one 40-hex release SHA; 64-hex active/accepted origin inputs; R19 HTTP
origin-leg decision; R20 default-certificate decision; `OPENAI_API_KEY` for G12 only.
**Explicit approval needed for:** `terraform plan` with real credentials (read-only), `terraform apply` (G10), any deploy/redeploy, adding the OpenAI key, the G12 real-provider run, git push/tag/release at any point.
**Never in v0.1:** DNS changes, NAT gateway, multi-AZ, autoscaling, GitHub OIDC (v0.2), Next.js (v0.3).

## 8. Rollback / recovery summary

Local gates G0–G8: additive code, revertible per commit; legacy app untouched throughout.

**Application rollback (non-destructive, the default):** redeploy the previous immutable image tags and/or the previous frontend build; Alembic downgrade only when a migration is implicated. This never touches infrastructure.

**Environment teardown (destructive, separate decision):** `terraform destroy` removes billed infrastructure but does **not** guarantee a zero-cost state — RDS final snapshots, retained CloudWatch logs, ECR image layers, non-empty S3 buckets (destroy fails or skips them until emptied), Secrets Manager secrets in their recovery window, and any Terraform state storage can all persist and bill until explicitly removed. A teardown checklist enumerating these residuals is part of the G10 runbook notes.

The fixture demo and Fly study deployment are independent of all of it. **No release tag is created — even locally — without explicit owner authorization** (this supersedes the spec §0 "tag the tested commit locally" step, per the Phase 0 correction gate); abandoning the release is a branch delete plus teardown, and nothing public changes without the owner's push/tag authorization.
