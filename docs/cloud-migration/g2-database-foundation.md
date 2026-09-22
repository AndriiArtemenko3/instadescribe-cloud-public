# G2 database-foundation evidence

**Date:** 2026-08-06 · **Gate:** Phase 1 G2 — PostgreSQL/SQLAlchemy/Alembic foundation, job state machine, DB-backed readiness
**Runtime:** Python 3.12.13 (uv-managed venv, printed on every `make cloud-venv`/`g1-test` run) · postgres:16.14 (compose)
**Scope guard:** no `/api/v1` routes, token, presigning, SQS publication, worker integration, or frontend changes — `GET /api/v1/jobs` → 404 verified.

## Dependencies (compiled, fully pinned via `uv pip compile`, 27 packages)

`sqlalchemy==2.0.51` (synchronous engine, `pool_pre_ping`, `connect_timeout=2`), `alembic==1.19.0` (runtime set — migrations run as a one-off task using the API image), `psycopg==3.3.4` + `psycopg-binary`, `pydantic-settings==2.14.2`, on the G1 base (fastapi 0.141.1 / uvicorn 0.52.1 / pydantic 2.13.4). `DATABASE_URL` is Compose-supplied; the DSN is never committed (placeholder `local-dev-only` credential only), never logged, and never present in any response body.

## Schema (migration `0001_core_tables`, reversible; Alembic is the only schema path)

- **`jobs`** — UUID PK; `name` v200; checked `status` text (10 persisted states, `ck_jobs_status_valid`); `stage` v80; `progress` smallint 0–100 (`ck_jobs_progress_range`, server default 0); `settings` JSONB NOT NULL; input object key/content-type/size/duration; provider/model; attempt_count (sd 0)/max_attempts (sd 3); enqueue_failed_at/enqueue_error; lease_expires_at/worker_id; version (sd 1); starred (sd false); safe `error_code`/`error_message`; timestamptz created/updated (sd `now()`)/started/completed. Indexes: `ix_jobs_status_created_at`, `ix_jobs_updated_at`, and the **partial unique index `uq_jobs_one_compute_active` on `(true)` WHERE `status IN ('PROCESSING','QUEUED','UPLOAD_COMPLETE')`** — one compute-active portfolio job globally, enforced in the database; `AWAITING_UPLOAD` deliberately excluded so an abandoned reservation cannot block uploads; export states can extend it in a later migration.
- **`artifacts`** — UUID PK; `job_id` FK `ON DELETE CASCADE`; type v60/object_key/content_type NOT NULL; size/checksum; JSONB `metadata` (sd `{}`); created_at; `uq_artifacts_job_id_artifact_type`; `ix_artifacts_job_id`.
- **`scene_overrides`** — UUID PK; `job_id` FK CASCADE; scene_id v120; text/voice/speed(4,2); active (sd true); version (sd 1, **stale-409 enforcement deferred to v0.2** per ADR-0002); updated_at; `uq_scene_overrides_job_id_scene_id`; `ix_scene_overrides_job_id`.
- Deterministic naming conventions on the declarative base; no `pipeline_runs`/`pipeline_stage_runs`/outbox/extensions. **Drift lesson:** explicit `ck_jobs_*` names in the migration got double-prefixed by the `ck_%(table_name)s_%(constraint_name)s` convention (`ck_jobs_ck_jobs_…`) — caught by `alembic check`, fixed by passing base names; `alembic check` now reports **"No new upgrade operations detected"**, including a clean comparison of the expression-based partial index.

## State machine (`app/domain/states.py`, ADR-0007 as amended)

10 persisted states; `RETRYING` is **not** persisted (retry = one durable `PROCESSING → QUEUED`); publication-recovery edge `UPLOAD_COMPLETE → PROCESSING`; terminal `COMPLETED`/`FAILED`/`CANCELLED` with no outgoing edges; same-state is never a legal transition. Exhaustive legacy mapping (awaiting/upload-complete/queued→`queued`; processing + export-queued/exporting→`processing`; ready-for-review/completed→`ready`; failed/cancelled→`failed`). Transition primitive `repositories/jobs.transition_job`: validates the edge (typed `IllegalTransitionError` before any SQL), then one conditional `UPDATE … WHERE id AND status IN (expected) RETURNING`; lost races return `None`; tuple-expected form covers the G5 claim.

## Readiness

`/healthz` + `/api/healthz` unchanged (dependency-free liveness). New `/readyz` + `/api/readyz` exact aliases: essential-config check + `SELECT 1`; 200 `{"status":"ready"}` only when ready; 503 `{"status":"unavailable","checks":[…]}` otherwise — stable body, no DSN/SQL/exception text (tested for leakage). **Live proof:** PG up → both 200; `docker compose stop postgres` → liveness 200/200 while readiness 503 `checks:["database"]`; `start postgres` → readiness 200 again.

## Test & command integration

`make migrate` / `make g2-verify` (alembic check) / `make cloud-test` (full suite, `LOCAL_DATABASE_URL` injected) / `make cloud-venv` (3.12, `--clear`). CI gains a **`cloud-api` job** (Python 3.12 + postgres:16.14 service, `ci-only` placeholder credential): install from the runtime-derived dev lock → `alembic upgrade head` → `alembic check` → `pytest services/api/tests` — runs when the branch is pushed; no remote CI result is claimed before a push.

## Acceptance results

| # | Check | Result |
|---|---|---|
| 1 | Compose config valid; all published ports loopback-bound | pass (127.0.0.1:5432/4566/8000) |
| 2 | Locks recompile; tests report Python 3.12 | pass — 3.12.13 |
| 3 | Cold up healthy + machine-asserting LocalStack verification | pass (`--wait` rc 0; `g1-verify` ASSERTED OK) |
| 4 | `alembic upgrade head` on empty DB → exactly `jobs`, `artifacts`, `scene_overrides` (+`alembic_version`) | pass (also test-asserted) |
| 5 | ORM/migration drift-free | pass — `alembic check`: no new operations |
| 6 | Downgrade → base removes schema; re-upgrade succeeds | pass (also test-asserted) |
| 7 | State tests: every legal edge, all illegal pairs incl. same-state, terminal, exhaustive mapping | pass (8 tests) |
| 8 | PG integration: conditional transitions, tuple claim, cascades, uniqueness/checks, partial index behavior | pass (11 tests) |
| 9 | Readiness 200 identical on both aliases with PG up | pass |
| 10 | PG stopped: liveness 200, readiness safe 503; recovery → 200 | pass (live compose proof above) |
| 11 | No `/api/v1/jobs` or other G3 behavior | pass (404) |
| 12 | Root pytest/Ruff + frontend suite + preview smoke | 56 passed; ruff clean (81 files); frontend all green; preview 200 |
| 13 | API image builds from its runtime lock; `git diff --check` clean | pass |
| 14 | No secrets/.env/DB state/media in commits or images | pass (placeholders only; pgdata volume never staged) |

**Cloud API suite: 27 passed** (4 health/docs-policy, 8 state machine, 4 readiness, 11 DB integration) in ~4 s.

## Known residuals

Stale-version 409 enforcement (v0.2, ADR-0002); export states outside the partial index until a later migration; the CI `cloud-api` job is unexercised until a push is authorized; production image digest/amd64 requirements tracked for G9.
