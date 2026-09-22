# InstaScribe AWS/PostgreSQL/Next.js Commercial-Style Migration
## Milestone-based implementation handoff for a coding agent

**Repository:** `AndriiArtemenko3/InstaScribe_Video_Description_Pipeline`  
**Release branches:** `feat/aws-cloud-core` → `feat/aws-portfolio-hardening` → `feat/nextjs-migration`  
**Primary AWS region:** `eu-west-2`  
**Goal:** Deliver three independently releasable upgrades: (A) a live AWS cloud vertical slice, (B) a strong production-style portfolio implementation with reliability evidence, and (C) a third release decided at a **conditional post-v0.2 gate** (ADR-0008 §6) for which the controlled Vite → Next.js App Router migration is the retained candidate — while preserving the working AI pipeline, editor, demo fixture, provider abstraction, visual design, and existing tests.

**Release targets (timeboxes, not promises):** Milestone A in ~7 focused days; Milestone B in the following 5–7 focused days; Milestone C in the following 4–6 focused days. Acceptance gates override calendar dates.


## 0. Delivery model: three public, CV-usable releases

This project must not remain invisible until a final "perfect" version. Implement it as three separately demonstrable releases, each with a Git tag, release note, evidence packet, live deployment, and CV-safe claim.

| Release | Target window | Primary outcome | New evidence available to the user |
|---|---:|---|---|
| **v0.1 — Cloud Core** | **7 focused days** | A live end-to-end AWS version of InstaScribe's core workflow using the existing Vite frontend | AWS deployment, FastAPI, PostgreSQL/RDS, S3, SQS, ECS, Docker, asynchronous processing |
| **v0.2 — Portfolio Strong** | **next 5–7 focused days** | Reliability, infrastructure as code, CI/CD, observability, tests, benchmarks, and polished public documentation | Production-style cloud engineering, Terraform, GitHub Actions OIDC, CloudWatch, idempotency, retries/DLQ, measured cost/latency |
| **v0.3 — conditional decision gate (Next.js candidate)** | **next 4–6 focused days, if selected** | Third-release content decided after the v0.2 evidence gate (ADR-0008 §6); the retained candidate is the controlled Vite → Next.js App Router migration on AWS without changing the Python backend | If Next.js is selected: App Router, Server/Client Component judgement, containerized TypeScript frontend, stronger full-stack/product-engineering evidence |

The time windows are planning constraints, not substitutes for evidence. Never claim a release on the CV until its acceptance gate has passed. If a target date is missed, publish the narrower truthful claim that the completed evidence supports.

### Release-stop rule

After each release gate:

1. Stop implementation of the next release.
2. Tag the tested commit locally using the proposed release tag.
3. Produce the milestone evidence packet described below.
4. Return the exact CV-safe bullet(s), live URL, test results, architecture snapshot, limitations, and next-release plan.
5. Do not begin the next release until the user has had the opportunity to update the CV, README, GitHub profile, and applications.

### Mandatory milestone evidence packet

Create one document per release:

- `docs/releases/v0.1-cloud-core.md`
- `docs/releases/v0.2-portfolio-strong.md`
- `docs/releases/v0.3-nextjs.md`

Each document must contain:

- release tag and commit SHA;
- deployed URL and health endpoint;
- exact architecture actually deployed;
- successful smoke-test evidence;
- tests/lint/build status;
- one measured result such as latency, processing duration, success rate, or estimated cost;
- screenshots or a shot list for visible evidence;
- known limitations and claims that are **not yet** justified;
- one short CV bullet and one stronger two-bullet version;
- README/GitHub profile wording that is accurate for that release.


---

## 1. Agent operating instruction

You are implementing a **three-release platform program**, not one long invisible rewrite. Each milestone must end in a demonstrable, tagged, independently truthful release that the owner can immediately reflect in the CV, GitHub README, portfolio site, and applications.

Work in this order:

1. **Milestone A — Cloud v1:** deploy the core workflow on AWS using the existing Vite frontend.
2. **Milestone B — Portfolio v2:** complete feature parity, reliability, infrastructure, CI/CD, observability, testing, benchmarks, and portfolio evidence.
3. **Milestone C — Next.js v3:** migrate the stable frontend to Next.js App Router without redesigning the product or replacing FastAPI.

Do not start Milestone C while cloud/backend architecture is still changing. Do not combine the Vite-to-Next.js migration with the initial FastAPI/PostgreSQL/S3/SQS migration.

Start by auditing the repository and running the current test/build baseline. Then implement the phases below in order. Keep the application usable and tests green after every phase. Make small, reviewable commits. Do not make a big-bang rewrite.

Before editing functional code, create:

- `docs/cloud-migration/repo-audit.md`
- `docs/cloud-migration/implementation-plan.md`
- `docs/cloud-migration/release-plan.md`
- `docs/cloud-migration/risk-register.md`
- `docs/adr/` entries for the fixed decisions in this document

The release plan must map every task to **A, B, or C**, identify the critical path to the Day-7 cloud release, and mark all non-critical work as deferred rather than silently expanding Milestone A.

### Branch and release discipline

- Build Milestone A on `feat/aws-cloud-core`, then branch Milestone B from the accepted v0.1 tag as `feat/aws-portfolio-hardening`.
- Tag the first accepted cloud release as `v0.1.0-cloud-core` (or an equivalent semantic version).
- Tag the hardened portfolio release as `v0.2.0-portfolio-strong`.
- Branch Milestone C from the accepted Milestone B tag using `feat/nextjs-migration`.
- Tag the deployed Next.js release as `v0.3.0-nextjs`.
- Do not push, merge, tag, create releases, or deploy without the owner’s explicit authorization.
- At each milestone gate, stop implementation and produce a release evidence pack before proceeding.

### Mandatory safety rules

- Never commit secrets, generated user media, Terraform state, `.env` files, or AWS credentials.
- Do not run `terraform apply`, create paid cloud resources, modify DNS, or push to `main` without explicit user authorization.
- Use GitHub Actions OIDC for AWS access by Milestone B; do not use long-lived AWS keys in GitHub secrets.
- Preserve the existing static fixture demo and its attribution.
- Preserve the current model-provider seam and fake provider.
- Do not change prompts, model quality logic, audio-description behavior, or visual design unless required for cloud/framework compatibility.
- Run the relevant tests before every commit and the full suite at each phase gate.
- Never describe the system as “production-grade.” Use “production-style” unless real production operation and evidence justify a stronger term.
- Never add a technology to the CV before the repository and deployed release visibly use it.

Do not replace any fixed decision without documenting a concrete blocker and choosing the smallest compatible alternative.

## 2. Current-state summary

The current application has these useful assets that must be preserved:

- React + Vite + TypeScript frontend.
- Flask API serving the SPA, media, data files, and JSON routes from one process.
- A working pipeline launched by `server.py` through `run_job.py` as a detached subprocess.
- Filesystem persistence under per-job directories for status, settings, generated JSON, videos, scene overrides, TTS cache, and exports.
- Provider abstraction supporting hosted, local, and fake backends.
- Dockerfile, Fly.io deployment configuration, backend tests, frontend tests, linting, and GitHub Actions CI.
- A committed zero-key fixture demo that must continue to work.

The migration must address these current architectural limitations:

1. Uploaded media passes through the API process.
2. Durable state is stored in local JSON files and directories.
3. Background jobs are tied to the API host through detached subprocesses.
4. Generated files are served from local application directories.
5. In-process locks only protect one Python process and cannot coordinate multiple containers.
6. The existing pipeline reads substantial configuration from process environment variables at import time.

---

## 3. Fixed technology decisions

### Milestones A and B: preserve the current frontend

- **Frontend:** React 19, Vite, TypeScript, React Router, TanStack Query, Zustand, Tailwind, shadcn/ui.
- **Hosting:** static build on S3 behind CloudFront.
- Do not rewrite, redesign, or reorganize the frontend while the cloud/backend vertical slice is being established.

### Backend/platform stack for Milestones A and B

- **API:** Python 3.12, FastAPI, Pydantic v2, Uvicorn/Gunicorn.
- **Database:** PostgreSQL on Amazon RDS.
- **Persistence:** SQLAlchemy 2.x, Alembic, psycopg 3.
- **Media/artifacts:** Amazon S3 with private buckets and presigned upload/download access.
- **Async processing:** Amazon SQS standard queue plus dead-letter queue.
- **Compute:** Amazon ECS Fargate for API and worker; Amazon ECR for images.
- **Infrastructure:** Terraform.
- **CI/CD:** GitHub Actions; add AWS OIDC by Milestone B.
- **Observability:** structured JSON logs and CloudWatch; full dashboard/alarms by Milestone B.
- **Secrets:** AWS Secrets Manager or SSM Parameter Store for non-database application secrets; RDS-managed/generated credentials may be stored in Secrets Manager.
- **Local development:** Docker Compose with PostgreSQL and LocalStack for S3/SQS.
- **AI/media pipeline:** preserve the existing Python pipeline, FFmpeg, VAD/ASR, provider interfaces, and fake-provider path.
- **Testing:** preserve pytest, Vitest, Ruff, ESLint; add integration tests and one Playwright smoke path.

### Milestone C: controlled Next.js migration

- **Framework:** current stable Next.js available at implementation time, App Router, React 19, TypeScript.
- **Deployment:** self-hosted Node.js/Docker build on ECS Fargate behind CloudFront and an ALB; use the framework’s standalone/container output where appropriate.
- **Backend boundary:** FastAPI remains the authoritative application/business API. Do not move pipeline, persistence, queue, artifact, or domain logic into Next.js.
- **State/data:** preserve TanStack Query and Zustand where they remain useful.
- **Editor:** keep the browser-heavy video editor as a focused Client Component subtree; do not force browser APIs, media controls, polling, local state, or timeline interactions into Server Components.
- **Server Components:** use them selectively for layouts, metadata, dashboard/project shells, and request-time data where this produces a real benefit.
- **Route Handlers/BFF:** optional and narrowly scoped to cookie/auth mediation or frontend-specific aggregation; never duplicate FastAPI business logic.
- **Migration style:** framework/routing migration, not a visual or product rewrite.

### Explicitly excluded through Milestone C

- Kubernetes/EKS.
- Redis.
- Celery.
- SageMaker.
- pgvector or a new RAG feature.
- Full OpenTelemetry distributed tracing.
- Cognito/full account system.
- Billing/subscriptions.
- Multi-region or multi-cloud deployment.
- Model fine-tuning or prompt-quality work.
- A component-library rewrite, state-management rewrite, or new visual design.

These can be considered only after all three release gates are accepted.

## 4. Target architecture

### Milestones A and B — Vite cloud application

```text
Browser
  |
  | static application
  v
CloudFront -> S3 Vite frontend bucket
  |
  | HTTPS REST
  v
ALB -> FastAPI service on ECS Fargate
        |              |                |
        | SQLAlchemy   | presigned POST | SendMessage
        v              v                v
   RDS PostgreSQL   private S3       SQS work queue
                                        |
                                        v
                              ECS Fargate worker service
                              (initially max 1 for portfolio)
                                        |
                        download source / run pipeline / upload outputs
                              |         |          |
                              v         v          v
                             S3    PostgreSQL   CloudWatch
                                        |
                                        v
                                      DLQ
```

### Milestone C — Next.js cutover

```text
Browser
  |
  v
CloudFront
  |
  v
Application Load Balancer
  |-------------------------------|
  | default routes                | /api/*
  v                               v
Next.js service               FastAPI service
ECS Fargate                   ECS Fargate
  |                               |
  | server-rendered shells        | domain/API operations
  | client-heavy editor           |
  |                               v
  |----------------------> PostgreSQL / S3 / SQS / worker
```

CloudFront should cache immutable `/_next/static/*` assets aggressively while forwarding dynamic application requests to the Next.js service. The existing Vite/S3 release must remain deployable as a rollback target until the Next.js release passes its acceptance gate.

### Deployment-cost decisions

Milestones A/B:

- API service: one small always-on Fargate task.
- Worker service: one task for the first cloud release; add queue-depth scale-to-zero behavior by Milestone B if reliable.
- RDS: smallest suitable encrypted PostgreSQL instance, single-AZ for the portfolio environment.
- RDS remains private.
- To avoid a permanent NAT Gateway charge in the portfolio environment, API/worker tasks may run in public subnets with public IPs but **no direct inbound access**; the API accepts inbound traffic only from the ALB security group and the worker accepts no inbound traffic. Document that a higher-budget production deployment would move tasks to private subnets with controlled egress.

Milestone C:

- Add one small Next.js Fargate service and ECR repository.
- Reuse CloudFront, ALB, VPC, DNS, logging, and deployment foundations where practical.
- Keep a single Next.js task initially; multi-instance cache coordination is out of scope unless the service is scaled beyond one task.
- Retain the Vite build and previous release artifacts long enough to perform a clean rollback.

## 5. Release-first migration strategy

Use a strangler-style migration with **three public evidence releases**.

### Milestone A — `v0.1.0-cloud-core` (~7 focused days)

Objective: ship a genuine live cloud vertical slice quickly enough to update the CV without waiting for every production-style enhancement.

Required user journey:

1. Open a live Vite frontend.
2. Enter the portfolio processing token.
3. Create a job and upload a short video directly to private S3.
4. Persist job state in PostgreSQL.
5. Enqueue analysis through SQS.
6. Run the existing pipeline in an ECS worker through the adapter.
7. Persist artifacts to S3 and expose them through a manifest.
8. Poll progress and open the generated scenes/source video in the existing editor.
9. Persist at least one scene edit and survive a browser refresh.
10. Complete one successful fake-provider cloud test and one explicitly authorized real-provider short-video test.

Milestone A may defer:

- complete Flask route parity;
- Smart Fill/TTS preview cloud parity if they threaten the release;
- final asynchronous export;
- sophisticated leases/heartbeats/autoscaling;
- complete CI/CD automation;
- polished Terraform module structure;
- full dashboards, alarms, benchmark suite, and portfolio write-up.

Milestone A must still include:

- minimal checked-in Terraform for the resources it actually uses;
- private media storage and least-privilege task roles;
- basic CloudWatch logs;
- a DLQ and bounded retry configuration;
- an AWS Budget guardrail;
- no large upload passing through the API container;
- a reproducible release note and honest CV bullet.

### Milestone B — `v0.2.0-portfolio-strong` (following 5–7 focused days)

Objective: convert the working cloud vertical slice into strong, inspectable commercial-style engineering evidence.

Add and prove:

- remaining editor/API route parity;
- Smart Fill and TTS preview parity;
- asynchronous final export;
- robust conditional claims, processing leases, visibility heartbeats, duplicate-delivery handling, retries, cancellation, and DLQ behavior;
- complete SQLAlchemy/Alembic schema and migrations;
- Terraform cleanup/modules, remote state/bootstrap documentation, and reproducible environment plan;
- GitHub Actions OIDC, immutable images, migration task, deployment smoke test, and rollback notes;
- structured logs, metrics, dashboard, alarms, and budget controls;
- integration and Playwright end-to-end tests;
- benchmark, cost, latency, and reliability evidence;
- architecture diagrams, ADRs, README, runbook, demo video, screenshots, and case-study material.

### Milestone C — `v0.3.0-nextjs` (following 4–6 focused days)

> **Amendment (Phase 1 G3 reconciliation, ADR-0008 §6):** Next.js is a **conditional post-v0.2 decision gate**, not the definition of completion. This migration plan is retained as the candidate's design; after the v0.2 evidence gate its employability value is compared against editor UX, evaluation, accessibility validation, reliability and cost work, and the owner decides the third release's content.

Objective: add commercially valuable Next.js evidence only after the backend/cloud contract is stable.

Migration sequence:

1. Branch from the accepted Milestone B release.
2. Establish a Next.js App Router compatibility build while preserving the existing client application behavior.
3. Migrate React Router routes to App Router route segments incrementally.
4. Preserve the interactive editor as Client Components and move only appropriate shells/layouts/data fetching to Server Components.
5. Preserve FastAPI as the business backend and existing API contracts.
6. Add Next.js lint/type/build/test coverage and a Docker image.
7. Add the Next.js ECS service, ALB routing, CloudFront behavior, health checks, and deployment workflow.
8. Run route-parity, Playwright, and cloud smoke tests.
9. Cut traffic over only after parity; retain `v0.2.0-portfolio-strong` as the rollback release.
10. Produce a Next.js-specific architecture note, before/after trade-off analysis, and updated CV/portfolio evidence.

### Stop-and-publish rule

At the end of each milestone:

- stop feature implementation;
- run the milestone’s acceptance suite;
- produce `docs/releases/<milestone>.md`;
- record exact deployed commit/image versions;
- capture screenshots and a short demo;
- update the README architecture/stack section;
- generate the CV bullet and website wording supported by that release;
- list known limitations honestly;
- wait for explicit authorization before starting the next milestone.

This prevents the project from remaining invisible while later improvements are still underway.

### Pipeline-adapter rule

Do **not** begin by rewriting `run_job.py` and every pipeline module into a new framework.

For the first cloud-complete version:

- The worker handles one job at a time.
- It creates an isolated temporary working directory.
- It writes the expected settings file/environment variables.
- It invokes the existing pipeline through a CLI/subprocess adapter.
- It polls or receives the pipeline’s progress status and writes progress to PostgreSQL.
- It uploads final artifacts to S3 and records them in PostgreSQL.
- It deletes the temporary working directory in a `finally` block.

After Milestone A is released, extracting a pure `process_job(context, progress_sink, artifact_sink)` function may be undertaken in Milestone B only when it directly improves testing, cancellation, progress reporting, or reliability.

## 6. Repository target layout

Do not move files merely for aesthetics, and do not block Milestone A on the final monorepo layout.

### Milestones A and B

```text
App/                              # existing React/Vite app; source of truth through v0.2.0-portfolio-strong
modular_pipeline/                 # existing AI/media pipeline, minimally changed
services/
  api/
    app/
      api/
      core/
      db/
      models/
      repositories/
      schemas/
      services/
      main.py
    Dockerfile
  worker/
    app/
      consumer.py
      executor.py
      heartbeat.py
      artifact_uploader.py
      main.py
    Dockerfile
packages/
  contracts/                      # queue schemas / shared Python contracts
migrations/                       # Alembic
infrastructure/
  terraform/
    bootstrap/
    modules/
      network/
      database/
      storage/
      queue/
      ecr/
      ecs/
      frontend/
      observability/
    environments/
      portfolio/
docs/
  adr/
  cloud-migration/
  releases/
  runbooks/
tests/
  integration/
  contract/
  e2e/
.github/workflows/
docker-compose.yml
Makefile
```

### Milestone C final target

```text
apps/
  web/                             # Next.js App Router frontend after cutover
services/
  api/
  worker/
modular_pipeline/
packages/
  contracts/
migrations/
infrastructure/
docs/
tests/
```

Migration rule for the frontend:

- Build Next.js on a dedicated branch from `v0.2.0-portfolio-strong`.
- A short-lived parallel `apps/web/` directory is permitted while route parity is verified.
- Freeze feature work in the Vite app during the migration.
- Do not maintain two active frontend implementations after cutover.
- Remove/archive the Vite implementation only after the Next.js cloud release and rollback test pass.

## 7. PostgreSQL data model

Use UUID primary keys, UTC `TIMESTAMPTZ`, foreign keys, check constraints, and explicit indexes. Prefer text/check constraints over PostgreSQL enum types unless an ADR justifies enums.

### `jobs`

> **Amendment (Phase 1 G3 reconciliation, ADR-0008 §1):** each `jobs` row is a **processing job** (one execution/version), not the whole user work item. The table and route names stay for bounded v0.1 compatibility.

#### `projects` (durable work item — added by migration `0002`)

- `id UUID PRIMARY KEY`
- `name VARCHAR(200) NOT NULL` (authoritative here, no longer on `jobs`)
- `starred BOOLEAN NOT NULL DEFAULT FALSE` (authoritative here, no longer on `jobs`)
- `version INTEGER NOT NULL DEFAULT 1`
- `created_at`, `updated_at` `TIMESTAMPTZ NOT NULL` with server defaults
- listing/updated index

Required fields:

- `id UUID PRIMARY KEY`
- `project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE`
- `pipeline_revision VARCHAR(120) NOT NULL` (immutable, server-supplied provenance)
- `status VARCHAR(40) NOT NULL`
- `stage VARCHAR(80)`
- `progress SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100)`
- `settings JSONB NOT NULL`
- `input_object_key TEXT`
- `input_content_type TEXT`
- `input_size_bytes BIGINT`
- `duration_secs NUMERIC`
- `provider VARCHAR(40)`
- `model VARCHAR(120)`
- `attempt_count INTEGER NOT NULL DEFAULT 0`
- `max_attempts INTEGER NOT NULL DEFAULT 3`
- `enqueue_failed_at TIMESTAMPTZ`
- `enqueue_error TEXT`
- `lease_expires_at TIMESTAMPTZ`
- `worker_id TEXT`
- `version INTEGER NOT NULL DEFAULT 1`
- `error_code TEXT`
- `error_message TEXT`
- `created_at`, `updated_at`, `started_at`, `completed_at`

Indexes:

- `(status, created_at)`
- `(updated_at)`
- optional partial index for active statuses

### `pipeline_runs`

- `id UUID PRIMARY KEY`
- `job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
- `attempt_number INTEGER NOT NULL`
- `task_type VARCHAR(30) NOT NULL` (`ANALYZE` or `EXPORT`)
- `status VARCHAR(30) NOT NULL`
- `worker_id TEXT`
- `input_tokens`, `output_tokens`, `total_tokens`
- `estimated_cost_usd NUMERIC(12,6)`
- `started_at`, `finished_at`
- `error_code`, `error_message`
- unique constraint on `(job_id, task_type, attempt_number)`

### `pipeline_stage_runs`

- `id UUID PRIMARY KEY`
- `pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE`
- `stage_name VARCHAR(80) NOT NULL`
- `status VARCHAR(30) NOT NULL`
- `progress_start`, `progress_end`
- `started_at`, `finished_at`
- `duration_ms BIGINT`
- `metadata JSONB NOT NULL DEFAULT '{}'`

### `artifacts`

- `id UUID PRIMARY KEY`
- `job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
- `artifact_type VARCHAR(60) NOT NULL`
- `object_key TEXT NOT NULL`
- `content_type TEXT NOT NULL`
- `size_bytes BIGINT`
- `checksum_sha256 TEXT`
- `metadata JSONB NOT NULL DEFAULT '{}'`
- `created_at TIMESTAMPTZ NOT NULL`
- unique constraint suitable for one current artifact per `(job_id, artifact_type)` or add an explicit version

Expected artifact types include:

- `source_video`
- `scenes_json`
- `entities_json`
- `audio_events_json`
- `ad_placement_gaps_json`
- `transcript_json`
- `poster_jpg`
- `poster_avif`
- `tts_preview`
- `described_video`
- `audio_export`
- `subtitle_export`
- `document_export`

### `scene_overrides`

- `id UUID PRIMARY KEY`
- `job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
- `scene_id VARCHAR(120) NOT NULL`
- `text TEXT`
- `active BOOLEAN NOT NULL DEFAULT TRUE`
- `voice VARCHAR(80)`
- `speed NUMERIC(4,2)`
- `version INTEGER NOT NULL DEFAULT 1`
- `updated_at TIMESTAMPTZ NOT NULL`
- unique `(job_id, scene_id)`

This table replaces the local whole-file read/modify/write override mechanism and should use optimistic versioning or an atomic upsert.

### Optional after core: `outbox_events`

Implement a transactional outbox only after the direct enqueue path is working and tested. Until then, explicitly record and expose an enqueue failure so it can be retried safely.

---

## 8. Job state machine

Internal states:

```text
AWAITING_UPLOAD
    -> UPLOAD_COMPLETE
    -> QUEUED
    -> PROCESSING
    -> READY_FOR_REVIEW
    -> EXPORT_QUEUED
    -> EXPORTING
    -> COMPLETED

PROCESSING -> QUEUED (retry: one durable atomic transition; attempt count and
                      safe error metadata update in the same operation.
                      "RETRYING" is a logical/logged phase, never a persisted
                      status — amended at the Phase 1 G2 reconciliation)
UPLOAD_COMPLETE -> PROCESSING (queue-publication recovery: send succeeded but
                      the final UPLOAD_COMPLETE -> QUEUED update failed and the
                      worker claimed the job directly)
Any non-terminal state -> FAILED
Any non-terminal state -> CANCELLED
```

Rules:

- State transitions must occur through a service/repository method, not arbitrary assignment.
- Illegal transitions return a domain error and are tested.
- The public API may map internal states to the frontend’s existing lower-case `queued | processing | ready | failed` values during migration.
- `READY_FOR_REVIEW` means the generated scene/artifact set is available to the editor.
- `COMPLETED` means a final described export exists.
- Terminal duplicate queue messages are acknowledged without reprocessing.

---

## 9. API contract

Version new routes under `/api/v1`, but preserve temporary compatibility wrappers for the existing frontend routes while migrating.

### Health

- `GET /healthz` — process is alive; no dependency checks.
- `GET /readyz` — verifies DB connectivity and essential configuration.

### Create and upload

#### `POST /api/v1/jobs`

Request JSON:

```json
{
  "name": "Sintel description",
  "durationSecs": 120,
  "fileName": "sintel.mp4",
  "contentType": "video/mp4",
  "fileSizeBytes": 12345678,
  "settings": {
    "model": "gpt-4.1",
    "frameQuality": "low",
    "fps": 1.0,
    "chunkSizeSecs": 60,
    "audioExtraction": true,
    "customPrompt": "",
    "language": null,
    "detailLevel": 3,
    "presetStyle": "documentary"
  }
}
```

Behavior:

1. Validate metadata and portfolio limits.
2. Insert a PostgreSQL job in `AWAITING_UPLOAD`.
3. Generate an S3 presigned **POST** with content-type and content-length conditions.
4. Return job ID, project ID, upload fields, and expiry.

#### `POST /api/v1/jobs/{job_id}/upload-complete`

Behavior:

1. Idempotently verify ownership/access token.
2. `HeadObject` the expected S3 key.
3. Verify size and content type against the job record.
4. Atomically move the job to `UPLOAD_COMPLETE`.
5. Send an SQS message.
6. On successful publication, move the job to `QUEUED`.
7. If publication fails, keep the job in retryable `UPLOAD_COMPLETE`, store `enqueue_failed_at`/`enqueue_error`, and expose a safe retry path; never silently lose the job. If the SQS send succeeds but the final status update fails, the worker must also be allowed to claim `UPLOAD_COMPLETE`.

### Job management

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `PATCH /api/v1/jobs/{job_id}`
- `DELETE /api/v1/jobs/{job_id}` — idempotent; deletes or schedules deletion of S3 objects and cascades DB records.
- `POST /api/v1/jobs/{job_id}/retry`
- `POST /api/v1/jobs/{job_id}/cancel`

### Artifact manifest

#### `GET /api/v1/jobs/{job_id}/manifest`

Return logical artifact names and short-lived presigned GET URLs. Store S3 keys, not expiring URLs, in PostgreSQL.

Example:

```json
{
  "jobId": "uuid",
  "expiresAt": "ISO-8601",
  "artifacts": {
    "video": {"url": "...", "contentType": "video/mp4"},
    "scenes": {"url": "...", "contentType": "application/json"},
    "entities": {"url": "...", "contentType": "application/json"},
    "audioEvents": {"url": "...", "contentType": "application/json"},
    "placementGaps": {"url": "...", "contentType": "application/json"},
    "transcript": {"url": "...", "contentType": "application/json"}
  }
}
```

Update the frontend data loader to consume the manifest rather than assuming `/data/{job_id}` and `/videos/{job_id}.mp4` local paths.

### Existing editor functionality

Migrate with route parity and characterization tests:

- scene override update
- smart fill
- TTS preview
- export request/status/download
- project rename/star/delete/list/reconcile
- provider status/selection where still appropriate
- study/demo-only routes must remain isolated and functional

Final export must run through the asynchronous queue rather than blocking the API process.

---

## 10. Queue contract and worker behavior

### Message schema

```json
{
  "schemaVersion": 1,
  "messageId": "uuid",
  "taskType": "ANALYZE",
  "jobId": "uuid",
  "requestedAt": "ISO-8601"
}
```

The message should contain identifiers, not full mutable job settings or secrets. The worker loads the current job/settings from PostgreSQL.

### Worker claim

Claim through one conditional SQL statement or a transaction with row locking. It must support:

- normal `QUEUED`/`EXPORT_QUEUED` claims and `UPLOAD_COMPLETE` recovery after a successful send followed by a failed status update;
- reclaim after an expired processing lease;
- duplicate messages for terminal jobs;
- one active worker per job;
- attempt counting.

### Heartbeat

During long processing, every 30–60 seconds:

- extend the SQS visibility timeout;
- extend `jobs.lease_expires_at`;
- write current stage/progress;
- emit a structured heartbeat log.

### Failure policy

Classify errors as:

- validation/non-retryable;
- external-provider retryable;
- transient AWS/network retryable;
- internal pipeline failure;
- cancellation.

For retryable failures, do not acknowledge the message until retry behavior is applied. After the configured receive/attempt limit, mark the job `FAILED` and allow the message to enter the DLQ. A DLQ message count alarm is mandatory.

### Idempotency

- Terminal jobs: acknowledge duplicates immediately.
- Artifact upload: deterministic object keys plus upsert/unique constraints.
- Scene override: atomic upsert with version check.
- Upload-complete: safe to call repeatedly.
- Export request: return the existing active export task instead of creating duplicates.

---

## 11. S3 layout and retention

Use separate buckets or clearly separated prefixes for frontend and private media.

```text
frontend bucket:
  index.html
  assets/*

private media bucket:
  uploads/{job_id}/source/{sanitized_filename}
  jobs/{job_id}/analysis/scenes.json
  jobs/{job_id}/analysis/entities.json
  jobs/{job_id}/analysis/audio_events.json
  jobs/{job_id}/analysis/ad_placement_gaps.json
  jobs/{job_id}/analysis/transcript.json
  jobs/{job_id}/posters/poster.jpg
  jobs/{job_id}/previews/{hash}.mp3
  jobs/{job_id}/exports/{export_id}/described.mp4
  jobs/{job_id}/exports/{export_id}/*
```

Requirements:

- Block all public access on the media bucket.
- Enable default encryption.
- Restrict CORS to the CloudFront/custom frontend origin.
- Use short-lived presigned GET URLs.
- Use presigned POST conditions for upload size/type.
- Apply lifecycle expiry to abandoned uploads, temporary previews, and portfolio demo artifacts.
- Keep the committed local fixture demo independent of S3.

---

## 12. Portfolio limits and access control

Core portfolio limits:

- maximum upload: 250 MB;
- maximum video duration: 5 minutes;
- maximum active processing jobs: 1 initially;
- maximum attempts: 3;
- worker max capacity: 1 initially;
- automatic S3 cleanup for uploaded/generated demo data;
- AWS Budget and billing alarm.

Do not build a full user-account system in this migration. Protect paid processing with a **server-side demo access token**:

- user enters the token in the UI when requesting an upload;
- frontend sends it in a header;
- API compares a constant-time hash against a value stored in Secrets Manager;
- the token is never embedded in the frontend bundle or committed;
- the fixture demo remains publicly viewable without the token.

Document that this is portfolio access control, not a multi-tenant authentication system.

---

## 13. Local development

### Milestones A and B

`docker compose up --build` must start:

- PostgreSQL;
- LocalStack with S3/SQS;
- FastAPI;
- worker;
- Vite frontend dev server or a documented separate frontend command.

Local behavior must support the fake provider so an end-to-end job can run without paid model calls.

### Milestone C

Add a Next.js local service and preserve the same FastAPI/PostgreSQL/LocalStack contracts. During the short migration window, provide explicit commands for the legacy and new frontends; after cutover, `make dev` must start Next.js by default.

Required Make targets (names may be adapted):

```text
make bootstrap
make dev
make dev-vite                 # temporary during Milestone C only
make dev-next                 # temporary during Milestone C only
make test
make test-integration
make test-e2e
make lint
make migrate
make seed-demo
make smoke-cloud
make terraform-plan
```

The fake-provider local flow and committed fixture demo must remain available through all milestones.

## 14. Terraform scope by release

### Milestone A — minimal reproducible cloud foundation

Terraform must define the resources used by the cloud vertical slice, without requiring polished module abstraction:

- VPC, subnets, routing, and security groups;
- ALB and FastAPI target group;
- ECS cluster and API/worker task definitions/services;
- ECR repositories for API and worker;
- RDS PostgreSQL, subnet group, encryption, backups, and security group;
- S3 Vite frontend bucket and private media bucket;
- CloudFront distribution and SPA fallback;
- SQS queue, DLQ, and redrive policy;
- essential IAM task/execution roles;
- essential CloudWatch log groups;
- required secrets/parameters;
- AWS Budget guardrail where supported.

Keep the first implementation simple and explicit. Do not delay the cloud release to build generalized Terraform modules.

### Milestone B — infrastructure hardening

Complete/refine:

- reusable modules where they reduce duplication;
- remote-state bootstrap and locking documentation;
- queue-depth worker autoscaling with min `0`, max `1` initially, if verified reliable;
- full CloudWatch dashboard and alarms;
- GitHub Actions OIDC deployment role/policies;
- lifecycle, retention, backup, and deletion policies;
- migration-task permissions;
- plan/apply separation and approval flow;
- least-privilege review and documented threat/cost trade-offs.

### Milestone C — Next.js infrastructure

Add:

- Next.js ECR repository;
- Next.js ECS task definition/service;
- health check and target group;
- ALB path routing: `/api/*` to FastAPI and application routes to Next.js;
- CloudFront behavior/caching for Next.js assets and dynamic requests;
- Next.js logs, deployment role access, and rollback controls;
- retention of the Milestone B static release until cutover is accepted.

Use an explicit bootstrap path for remote Terraform state. Do not commit state or silently create the state backend.

### IAM separation

At minimum separate:

- FastAPI task role;
- worker task role;
- Next.js task role in Milestone C;
- ECS execution roles;
- GitHub deployment role;
- Terraform plan/apply permissions if separated;
- event/auto-scaling roles created by AWS/Terraform.

The worker may access only the required S3 prefixes, queue operations, job secret reads, logs/metrics, and database network path. The API may generate presigned operations, read/write permitted job objects, send queue messages, and access its secrets. The Next.js role should not receive direct database, worker-queue, model-provider, or broad S3 permissions unless a narrowly documented BFF requirement justifies them.

## 15. CI/CD by milestone

Preserve the existing CI throughout.

### Pull requests from Milestone A onward

- Ruff check and format check;
- pytest unit/contract tests;
- frontend lint/typecheck/Vitest;
- integration tests with PostgreSQL and LocalStack as they become available;
- build API and worker Docker images;
- `terraform fmt -check` and `terraform validate`;
- Alembic migration validation.

### Milestone A deployment

A controlled manual deployment or explicitly triggered workflow is acceptable to meet the first release gate, provided:

- deployed commit/image versions are recorded;
- images are tagged immutably with the commit SHA;
- migrations are run explicitly;
- health checks and one cloud smoke test pass;
- no long-lived AWS credentials are committed or exposed.

Do not claim automated CI/CD at this milestone unless it genuinely exists.

### Milestone B deployment

Implement the complete path:

1. Authenticate to AWS through GitHub OIDC.
2. Build immutable API/worker images tagged with commit SHA.
3. Push to ECR.
4. Build Vite frontend and sync versioned assets to S3.
5. Apply or use an explicitly approved Terraform plan.
6. Run Alembic as a one-off ECS migration task.
7. Update ECS services.
8. Wait for health checks.
9. Run a fake-provider smoke test.
10. Invalidate only required CloudFront paths.
11. Preserve the prior release for rollback.

### Milestone C deployment

Add:

- Next.js lint, typecheck, tests, and production build;
- Next.js Docker image build and ECR push;
- framework/environment validation;
- Next.js ECS rolling deployment and health checks;
- route-parity and Playwright smoke tests against the new frontend;
- controlled CloudFront/ALB cutover;
- automated rollback instructions to `v0.2.0-portfolio-strong`.

Do not use `latest` as the only deployment tag in any milestone.

## 16. Observability

### Structured logs

Every API/worker log should be JSON and include relevant fields:

- timestamp;
- level;
- service;
- environment;
- request_id or message_id;
- job_id;
- task_type;
- worker_id;
- attempt;
- stage;
- duration_ms;
- error_code.

Never log API keys, access tokens, presigned URL query strings, full transcripts by default, or user media content.

### Metrics/dashboard

Create one useful dashboard covering:

- API request count, latency, 4xx, 5xx;
- ECS running task count;
- SQS visible/in-flight messages and age of oldest message;
- DLQ message count;
- jobs completed/failed and processing duration;
- RDS CPU, connections, storage;
- estimated provider usage/cost where data is available.

### Alarms

At minimum:

- DLQ messages > 0;
- oldest queue message above threshold;
- API 5xx threshold;
- RDS storage/CPU concern;
- AWS Budget threshold.

---

## 17. Test plan

### Preserve throughout

All existing backend/frontend tests, provider abstractions, study mode, and fixture-demo behavior.

### Unit tests for Milestones A/B

- state transition table;
- job DTO validation;
- queue message parsing/version rejection;
- duplicate/terminal message behavior;
- lease claim and expiry logic;
- scene-override optimistic concurrency;
- artifact key generation and path sanitization;
- error classification;
- upload limit validation.

### Integration tests for Milestones A/B

Using real PostgreSQL and LocalStack:

- Alembic upgrade on an empty database;
- create job -> presigned upload -> upload complete -> SQS message;
- worker claim -> fake pipeline -> S3 artifacts -> DB terminal state;
- duplicate SQS delivery does not duplicate processing/artifacts;
- failed job retries then reaches DLQ/failed behavior;
- manifest returns usable signed URLs;
- one scene edit persists across API restart/browser reload;
- delete removes or schedules removal of job artifacts;
- API restart does not lose jobs.

### Playwright smoke flow by Milestone B

With fake provider/local services:

1. Open app.
2. Create a job.
3. Upload committed short fixture.
4. Observe processing.
5. Open editor when ready.
6. Edit one scene.
7. Request export.
8. Download or verify final artifact.

### Next.js migration tests for Milestone C

- route inventory parity between React Router and App Router;
- direct navigation and refresh on every dynamic route;
- client-only browser/media code never executes in an invalid server context;
- Zustand/TanStack Query provider hydration and persistence behavior;
- environment-variable boundary tests (`NEXT_PUBLIC_*` only where intentionally public);
- metadata/layout rendering tests;
- FastAPI contract tests remain unchanged;
- Playwright smoke flow passes through the Next.js deployment;
- rollback to the Vite release is documented and tested;
- optional bundle/performance comparison recorded without inventing gains.

## 18. Milestone phases, timeboxes, and acceptance gates

Timeboxes are prioritization tools, not permission to skip acceptance criteria or fabricate completion. When the calendar target and quality gate conflict, report the blocker and ship the smallest honest release.

### Phase 0 — Audit, baseline, and critical path (target: 0.5–1 day)

Acceptance:

- baseline test, lint, frontend build, Docker build, and demo results recorded;
- endpoint and filesystem inventory complete;
- pipeline environment-at-import coupling mapped;
- feature branch created;
- every task assigned to Milestone A, B, or C;
- a Day-7 critical path and explicit defer list created;
- no functional migration code yet.

### Phase 1 — Local cloud vertical slice (target: Days 1–3)

Acceptance:

- FastAPI health/readiness and core job endpoints;
- PostgreSQL/SQLAlchemy/Alembic jobs foundation;
- direct S3-compatible upload and artifact manifest through LocalStack;
- SQS/DLQ and one worker adapter path;
- existing pipeline runs in an isolated workspace with the fake provider;
- existing Vite frontend can create, poll, and open one processed job locally;
- at least one scene override persists in PostgreSQL;
- legacy fixture demo remains green.

### Phase 2 — Minimal AWS deployment (target: Days 4–6)

Acceptance:

- minimal Terraform for used resources;
- Vite on S3/CloudFront;
- FastAPI and worker on ECS Fargate;
- RDS PostgreSQL;
- private media S3 bucket;
- SQS/DLQ and ECR;
- task roles and secrets;
- basic CloudWatch logs and budget guardrail;
- successful fake-provider cloud smoke test.

### Phase 3 — Milestone A release gate: `v0.1.0-cloud-core` (target: Day 7)

Acceptance:

- live URL works from a clean browser;
- protected direct upload works;
- asynchronous cloud analysis completes;
- progress survives API restart;
- generated video/scenes load in the existing editor;
- one scene edit survives refresh;
- one authorized real-provider short-video job succeeds;
- deployed commit, image tags, Terraform plan, cost snapshot, limitations, screenshots, and demo are recorded;
- README and CV evidence pack updated;
- implementation stops for review.

#### Honest CV claim available after Milestone A

Use only after the gate passes, with service names adjusted to what is actually deployed:

> Deployed InstaScribe’s core multimodal audio-description workflow on AWS using FastAPI, PostgreSQL/RDS, S3, SQS, Docker and ECS Fargate, supporting direct video uploads, asynchronous processing and persistent human edit.
>
> *(Wording amended at the Phase 1 G3 reconciliation: "persistent human edit", not "review", until explicit review decisions exist — ADR-0008 §3.)*

Do not yet claim full feature parity, automated CI/CD, advanced reliability, Next.js, or production-grade operation.

---

### Phase 4 — Feature parity and reliability hardening (target: next 3–4 days)

Acceptance:

- project list/rename/star/delete/reconcile parity;
- Smart Fill and TTS preview parity;
- asynchronous export and signed download;
- complete job state machine;
- conditional claims, leases, heartbeats, cancellation, retries, terminal duplicate handling, and DLQ behavior;
- S3 lifecycle/cleanup;
- database indexes/constraints and migration review;
- route characterization tests and integration tests.

### Phase 5 — Infrastructure, CI/CD, observability, and evidence (target: next 2–3 days)

Acceptance:

- reproducible Terraform/remote-state plan;
- GitHub Actions OIDC deployment with immutable images;
- Alembic migration task and rollback process;
- queue autoscaling/scale-to-zero if verified;
- structured logs, dashboard, alarms, and budget controls;
- Playwright end-to-end flow;
- benchmark table for latency, success rate, stage duration, and estimated cost;
- architecture/state-machine/database diagrams;
- runbook, ADRs, cost model, two-minute demo, and screenshots.

### Phase 6 — Milestone B release gate: `v0.2.0-portfolio-strong` (target: 5–7 days after Milestone A)

Acceptance:

- complete core workflow is demonstrable in the cloud;
- reliability failure scenarios are tested rather than only described;
- clean-clone local setup works;
- CI/CD deploys the accepted release;
- architecture and trade-offs are inspectable by an employer;
- quantified evidence is captured;
- README, CV, website, and release note are updated;
- implementation stops for review before Next.js work begins.

#### Strong CV claim available after Milestone B

Fill placeholders only from measured evidence:

> Architected and deployed a production-style multimodal AI platform on AWS with FastAPI, PostgreSQL, S3, SQS and ECS Fargate; added infrastructure as code, CI/CD, idempotent background processing, retries/DLQ, observability and asynchronous media export, achieving [measured result].

Do not use “production-grade” or invent scale, uptime, cost, or latency figures.

---

### Phase 7 — Next.js compatibility migration (target: 1–2 days)

Acceptance:

- branch begins from accepted `v0.2.0-portfolio-strong`;
- current stable Next.js and App Router installed/configured;
- existing React UI runs under Next.js with visual/behavioral parity;
- Tailwind, shadcn/ui, Zustand, TanStack Query, tests, aliases, assets, and environment variables work;
- no product redesign;
- FastAPI contracts unchanged;
- Vite release remains deployable for rollback.

### Phase 8 — App Router and server/client boundaries (target: 2–3 days)

Acceptance:

- React Router routes migrated to App Router route segments;
- dynamic job/editor routes support direct navigation and refresh;
- editor/media/browser logic isolated in Client Components;
- layouts, metadata, and appropriate dashboard/project shells use Server Components;
- no duplicated business logic in Route Handlers;
- route parity and Playwright tests pass;
- obsolete Vite-only code identified for removal after cutover.

### Phase 9 — Next.js AWS deployment and cutover (target: 1 day)

Acceptance:

- Next.js production Docker image built and deployed to ECS;
- CloudFront/ALB routing works;
- `/_next/static/*` caching and health checks verified;
- API, upload, editor, and export smoke flows pass;
- previous Vite release remains a tested rollback;
- Next.js architecture/trade-off note and evidence screenshots complete.

### Phase 10 — Milestone C release gate: `v0.3.0-nextjs` (target: 4–6 days after Milestone B)

Acceptance:

- Next.js App Router is the deployed production-style frontend;
- existing functionality and visual design are preserved;
- FastAPI remains the authoritative backend;
- Vite implementation is removed or explicitly archived after rollback validation;
- CI/CD, documentation, README, CV, website, and demo reflect the deployed release;
- implementation stops for final review.

#### Additional CV claim available after Milestone C

> Migrated a React/Vite video-authoring application to Next.js App Router, preserving a client-intensive editor while introducing server-rendered layouts/data boundaries and deploying the containerized frontend on AWS ECS behind CloudFront and an ALB.

Use this only after the Next.js version is actually deployed and tested.

## 19. Definitions of done

### Milestone A — cloud application done

- A reviewer can open a live Vite frontend and authenticate for paid processing with the portfolio demo token.
- A video uploads directly to private S3 rather than through the API container.
- PostgreSQL is the durable source of truth for job state.
- SQS mediates asynchronous analysis work.
- An ECS worker runs the existing pipeline in an isolated workspace and stores outputs in S3.
- Generated artifacts load in the existing editor.
- At least one human edit persists across refresh/restart.
- Basic Terraform, logs, cost guardrails, smoke evidence, and a release note exist.

### Milestone B — strong portfolio implementation done

- The complete core editor, Smart Fill, preview, and asynchronous export workflow works.
- Duplicate messages do not duplicate completed work.
- Worker death or API restart does not lose durable state.
- Long jobs extend queue visibility and a DB processing lease.
- Retries, DLQ, cancellation, and failure classifications are tested.
- Terraform defines the complete cloud infrastructure.
- GitHub Actions use OIDC and deploy immutable image tags.
- CloudWatch exposes logs, operational metrics, a dashboard, and meaningful alarms.
- Integration and Playwright tests cover the critical flow.
- Cost, latency, stage timing, and reliability results are measured and documented.
- Existing tests and zero-key fixture demo remain green.
- A clean-clone local setup and documented cloud deployment both work.
- README, architecture, ADRs, trade-offs, benchmark, case study, and demo evidence are complete.

### Milestone C — Next.js migration done

- Next.js App Router serves the deployed application.
- FastAPI remains the business backend.
- The browser-heavy editor remains a deliberate Client Component boundary.
- Appropriate layouts/shells/metadata use Server Components.
- Direct navigation, refresh, upload, polling, editing, preview, and export work through Next.js.
- The Next.js container is deployed on ECS behind CloudFront/ALB with health checks and CI/CD.
- Route parity and Playwright tests pass.
- The Milestone B Vite release can be restored through the documented rollback path.
- The CV/portfolio mentions Next.js only after this gate passes.

## 20. First task for the coding agent

Execute **Phase 0 only**, with the v0.1 seven-day Cloud Core gate as the immediate target.

Return:

1. Baseline command results.
2. Exact current endpoint inventory.
3. Exact filesystem read/write inventory.
4. Pipeline coupling map, especially environment-at-import behavior.
5. Frontend assumptions about `/data`, `/videos`, multipart uploads, and job states.
6. The smallest file-by-file sequence that can deliver the mandatory v0.1 user journey within the release window.
7. A clearly separated v0.1 deferred list for v0.2.
8. Risks that would require narrowing the v0.1 CV claim or changing this specification.
9. Proposed Terraform minimum for v0.1 and hardening delta for v0.2.
10. A Next.js migration inventory for v0.3 only: routes, browser-only components, shared code, likely Server Components, and deployment implications. Do not implement it yet.
11. A commit containing only audit/plan/ADR documents and no migration code.

Do not start functional implementation until the Phase 0 plan demonstrates a credible route to the v0.1 gate. Do not begin Next.js implementation before the v0.2 evidence gate is complete.

### Initial instruction to paste into the coding agent

```text
Work in the repository:
AndriiArtemenko3/InstaScribe_Video_Description_Pipeline

Read docs/implementation/INSTASCRIBE_STAGED_IMPLEMENTATION_HANDOFF.md completely.

Execute Phase 0 only. Optimize the implementation plan for three independently
shippable releases:

1. v0.1 Cloud Core in a target seven focused days,
2. v0.2 Portfolio Strong in the next five to seven focused days,
3. v0.3 Next.js migration in the next four to six focused days.

The immediate critical path is a live Vite + FastAPI + PostgreSQL/RDS + S3 +
SQS + ECS end-to-end workflow. Do not let CI/CD polish, full observability,
non-core route parity, or Next.js block the first cloud release.

Create the requested audit, implementation plan, risk register, ADRs, release
folder, baseline results, endpoint/filesystem inventory, pipeline coupling map,
and file-by-file v0.1 sequence. Separate v0.1 requirements from v0.2 hardening
and v0.3 Next.js work.

Do not run Terraform apply, create AWS resources, modify DNS, push, merge,
change prompts, redesign the UI, or implement Next.js yet.

Return only the Phase 0 documentation and findings, then stop.
```

