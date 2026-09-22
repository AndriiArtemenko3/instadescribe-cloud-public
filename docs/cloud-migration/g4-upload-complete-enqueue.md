# G4 verified upload completion + durable SQS enqueue — evidence

> **Amended at the G5 Part A correction gate (2026-08-07).** The independent
> G4 review found seven gaps; all are now closed and the evidence below marked
> *(re-run)* was regenerated after those changes. Corrections: (1) the DSN
> guard now rejects ALL query parameters (the `?dbname=` effective-target
> bypass), requires loopback hosts, and each suite run owns a run-scoped
> `instascribe_<pid>_<token>_test` database — two concurrent full suites were
> run simultaneously and both passed (147 + 147) without touching each other;
> (2) `QueueMessage.from_body()` is now a strict canonical wire parser
> (exact key set, integer-1 schemaVersion, canonical lowercase UUIDs,
> string RFC3339 timestamps, duplicate-key and oversize rejection);
> (3) queue tests use run-owned namespaced queues — never the development
> queue — and the isolation proof now also plants a dev-queue sentinel
> message and asserts queue attributes survive *(re-run: OK)*; (4) the
> earlier "concurrent" claims were sequential/fault-injected — REAL
> barrier-based concurrency tests now exist for same-job and competing-job
> completions; (5) `prove_isolation.py` cleans its sentinels in `finally`;
> (6) S3 `BotoCoreError` transport failures, post-send DB outages (response
> identity pre-captured before send) and failure-metadata write outages are
> sanitized and tested; (7) optional VersionId/checksum retry comparison is
> symmetric, and the missing-object 403-vs-404 IAM nuance stays reserved for
> G11. Suite total after corrections: **147 passed** *(re-run)*.

**Date:** 2026-08-06 · **Gate:** G3 correction gate (Part A) + Phase 1 G4
**Runtime:** Python 3.12.13; boto3/botocore 1.43.66; LocalStack 4.14.0 (community); postgres:16.14
**Local/LocalStack semantics are stated as such throughout; anything reserved for real AWS is tagged G11.**

## Part A — the reproduced G3 defect and its prevention

**Root cause:** `make cloud-test` pointed `INSTASCRIBE_TEST_DATABASE_URL` at the live Compose application database; the session fixture ran `alembic downgrade base` around the suite, and `/readyz` (SELECT 1 only) kept reporting ready over an empty schema.

**Prevention, proven:**
- Dedicated disposable `instascribe_test` database (`make test-db`, idempotent, app volume untouched). Fail-closed guards run **before** any Alembic/cleanup operation: normalized `(host, port, database)` target comparison (regression test proves `localhost` vs `127.0.0.1` spellings of the same target are refused — raw string inequality is insufficient) plus an explicit `*_test` name opt-in; missing/ambiguous URLs refuse. The Alembic URL travels inside the test's Alembic config — the suite no longer redirects the process `DATABASE_URL`.
- **Sentinel proof (`make isolation-proof`), re-run at head `0003`:** app DB migrated to head, durable project/job planted, full `make cloud-test` executed, then: head unchanged (`0003_source_enqueue → 0003_source_enqueue`), tables intact, sentinel survived → `ISOLATION PROOF OK`.
- **Schema-aware readiness:** `/readyz` + `/api/readyz` now compare `alembic_version` against the head packaged next to the app code. Proven on the isolated DB: at head → 200; one migration behind → 503 `{"checks":["schema"]}` while `/healthz` stayed 200; schema absent → 503 schema; upgrade → 200. No revision IDs/DSN/SQL in any body. In-image proof: `docker compose run api python -c …` imports the checker and resolves packaged head `0003_source_enqueue` from `/srv/migrations`.
- G3 hardening (validate_default, control-character 422s, revision/numeric bounds, strict-404 auth duplicates, transport-test relabeling, ADR-0006 rotation wording) all present with tests; the Starlette `TestClient`/httpx deprecation warning remains **recorded as forward maintenance** (upstream expects an `httpx2` migration; not suppressed, tracked here).

## Part B — migration 0003 and the shared queue contract

`0003_source_enqueue` (revision IDs must fit `alembic_version` VARCHAR(32) — pitfall found and documented): `source_etag` (opaque validator, **not** a checksum), `source_version_id`, `source_checksum_sha256` (only when genuinely supplied — never derived from ETag), `upload_verified_at`, stable `enqueue_message_id`, `enqueue_requested_at`, non-negative `enqueue_attempt_count` (server default 0, check-constrained), `enqueued_at`. Proven: populated-0002 upgrade applies defaults to existing rows; constraint enforces; downgrade preserves 0002 data; re-upgrade; `alembic check` drift-free. The stored ETag/VersionId is the G5 handoff: the worker downloads with exact `VersionId` or `If-Match`, closing the presigned-POST reuse/overwrite TOCTOU window.

`packages/contracts/instascribe_contracts.queue.QueueMessage` — the one strict contract: `{schemaVersion:1, messageId, taskType:"ANALYZE", jobId, requestedAt}` RFC3339-Z; unknown fields forbidden; naive timestamps rejected; offsets normalized to UTC; identifiers only. Shipped in the API image (`/srv/instascribe_contracts`, `PYTHONPATH=/srv`) — in-image import proven. No API-local duplicate schema exists.

## Part C — upload-complete semantics (implemented and tested)

`POST /api/v1/jobs/{job_id}/upload-complete` (token-inherited, no request body): loads the job by exact ID, `HeadObject` on the persisted canonical key only, requires exact `ContentLength == input_size_bytes`, normalized `ContentType` equality, `AES256` SSE, and a present ETag (stored normalized; VersionId/SHA-256 only when supplied). Nothing client-supplied is trusted.

**Recoverable ordering (documented in the route docstring):** verify → one transaction `AWAITING_UPLOAD→UPLOAD_COMPLETE` persisting verification + stable `enqueue_message_id`/original `enqueue_requested_at` + attempt increment (the compute slot is acquired **here** by `uq_jobs_one_compute_active`; the specific violation is classified via `diag.constraint_name` — unrelated integrity errors are not misclassified, tested) → SQS send with the stable identity → conditional `UPLOAD_COMPLETE→QUEUED` clearing failure fields. Send failure: durable `UPLOAD_COMPLETE` + `enqueue_failed_at` + bounded classified `enqueue_error="sqs_send_failed"` → retryable 503. Send-success/final-update failure: rollback of nothing, 202 accepted, state recoverable (G5 claims both `UPLOAD_COMPLETE` and `QUEUED`). Duplicates possible (standard SQS — **no exactly-once claim**); harmless via stable identity + G5 claim.

Error surface (stable codes, no raw AWS text): `source_not_visible` 409 · `source_mismatch` 422 (+checks) · `capacity_conflict` 409 · `source_identity_changed` 409 · `enqueue_unavailable`/`storage_unavailable` 503 · `terminal_conflict` 409 · idempotent 200 for queued/processing/ready/completed.

## Test results

**112 cloud tests pass** (~17 s) against the isolated DB + LocalStack, including all 15 handoff-required areas: golden path with exact queue-message assertion; the G3 declared-5,000,000/uploaded-4,096 mismatch rejected with no send; missing object / wrong MIME / injected-missing SSE each leaving `AWAITING_UPLOAD`; ETag normalization + no-false-checksum; slot conflict (second job 409, only the holder's message on the queue); SQS failure → durable `UPLOAD_COMPLETE` → retry reusing the **same** messageId reaching `QUEUED` (attempts=2, failure fields cleared); send-success/finalize-failure → 202 + recoverable state → simulated worker `PROCESSING` → late call idempotent 200 with **no** regression and no resend; retry-after-object-overwrite → `source_identity_changed`, no message; idempotent/terminal matrix; slot-vs-unrelated integrity classification; sanitized responses/logs (injected `AKIA…`/endpoint text provably absent); queue/DLQ redrive+visibility asserted by the hermetic self-draining fixture (same shape in CI's LocalStack service). Failure injection is deterministic (monkeypatched S3/SQS/transition) — no timing sleeps.

**Live compose proof (clean `down -v` start):** migrate gate ran 0001→0003 before the API served; schema-aware readiness 200; create → browser-style upload → upload-complete 202 → `QUEUED` with exactly one valid contract message; **and a genuine live capacity conflict** was observed when a second completion ran while the first held the slot (the partial index working outside tests).

**Regressions:** root pytest 56; ruff check/format clean; frontend 8/8 + fixture preview 200 (one transient preview 404 traced to a not-yet-ready preview server; retry with identical artifacts fully green); `git diff --check` clean; API image builds from pinned manifests.

## Residual risks and G5 blockers

None blocking. G5 consumes: the tuple-claim (`UPLOAD_COMPLETE` + `QUEUED`), the stored ETag/VersionId for `If-Match`/`VersionId` downloads, the queue contract, and the 1800 s visibility (heartbeats are G5 work). Reserved for G11 (real AWS): presigned-POST size-policy enforcement, real SSE/head semantics, SQS behavior beyond LocalStack. Owner decisions D1–D7 unchanged.
