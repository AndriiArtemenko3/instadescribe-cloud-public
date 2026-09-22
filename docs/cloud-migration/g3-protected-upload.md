# G3 protected creation + presigned upload — evidence

**Date:** 2026-08-06 · **Gate:** Phase 1 G3 (with the G2.5 project/provenance migration beneath it)
**Runtime:** Python 3.12.13 · boto3 1.43.66 / botocore 1.43.66 added to the pinned runtime set (recompiled via `uv pip compile`)
**Scope guard:** no upload-complete, SQS send, worker, manifest, override writes, frontend changes, Terraform, or AWS resources. `PATCH/DELETE /api/v1/jobs/{id}` → 405; `…/upload-complete` → 404 (tested).

## Auth design (central boundary)

One `/api/v1` router carries `verify_portfolio_token` mounted once; every present and future route beneath it inherits the dependency (structurally asserted on the router **and** proven behaviorally: every discovered route × method returns 401 without a token; no unguarded duplicate exists outside the prefix). Header `X-Portfolio-Token` via an OpenAPI `APIKeyHeader` scheme; configuration stores only a SHA-256 hex digest; comparison is `hmac.compare_digest` over the hashed supplied token. Missing and wrong tokens return byte-identical generic 401s; missing/malformed server digest returns safe 503 (protection never silently disabled). The token/header/digest are never logged. Local dev digest = SHA-256 of the documented placeholder `local-dev-token` (compose comment); production digests arrive from Secrets Manager later. Health/readiness and their `/api/` aliases remain public.

## Typed settings and CORS

New settings: token digest, media bucket, region, split internal/browser S3 endpoints, path-style flag, presign expiry (900 s), max upload 250 MiB, max declared duration 300 s, allowed origins, server-selected provider (`fake`, the only allowlisted value), model/fps/frame-quality/chunk-size/preset-style/content-type/extension allowlists, and the server-supplied `pipeline_revision` (`dev` in compose, `test` in tests). CORS: the configured Vite origin only, GET/POST/OPTIONS, `Content-Type` + `X-Portfolio-Token`, credentials disabled — allowed preflight echoes the origin; an unlisted origin receives no CORS grant (both tested). Readiness now also requires the token digest shape, pipeline revision, bucket, positive limits, and an allowlisted provider; failures log the stable event `readiness_unavailable categories=…` with **no** DSN/credentials/SQL/headers/tracebacks (caplog-asserted; the Alembic `fileConfig` logger-nuking pitfall was found and fixed with `disable_existing_loggers=False`).

## Validation allowlists (server-authoritative spend bounds)

name 1–200 trimmed · filename basename-only, NUL/traversal/separator-rejecting, extension ∈ {.mp4,.mov,.webm}, sanitized to `[A-Za-z0-9._-]` · content type ∈ {video/mp4, video/quicktime, video/webm} · size 1–250 MiB · declared duration ≤ 300 s (untrusted hint; G5 ffprobe remains authoritative) · model ∈ {gpt-4.1} · fps ∈ {0.5, 1.0} (**8 FPS rejected**) · frame quality ∈ {low} · chunk ∈ {60, 120} · detail 1–5 · preset ∈ the five pipeline styles · language short BCP-47-ish tag · custom prompt ≤ 2000 chars · unknown fields forbidden at both levels, so client-supplied `provider`/`pipelineRevision` fail as 422 (tested). Persisted settings are the normalized snake_case worker contract (`server.py:77–91` shape); `jobs.provider`/`pipeline_revision` come only from server configuration.

## Exact presigned-POST policy

Key `uploads/{job_id}/source/{sanitized_filename}`; SigV4; path-style; signed against the **browser-visible** endpoint (URLs contain `localhost:4566`, never `localstack:4566` — asserted). Conditions, decoded from the returned policy in tests: exact `{bucket}`, `["eq","$key",…]`, `["eq","$Content-Type",…]`, `["eq","$x-amz-server-side-encryption","AES256"]`, `["content-length-range",1,250 MiB]`, expiry 900 s. PostgreSQL stores object keys and metadata only — never signed URLs/fields. **Oversize enforcement note:** with a test-configured 1 KiB limit, this LocalStack version accepted an oversize POST (recorded limitation) — the policy-decode proof stands and a real-S3 enforcement test is **mandatory at G11**; no unobserved rejection is claimed.

## Creation semantics

One transaction creates the durable project + the initial `AWAITING_UPLOAD` processing job (distinct UUIDs), generates the presigned POST inside the transaction boundary, and commits only when both rows and signing succeed — a monkeypatched signing failure returns safe 503 and leaves **zero** rows (tested). Creation does **not** reserve the compute slot (ADR-0008 §2); multiple `AWAITING_UPLOAD` reservations coexist (tested). List/get join `projects`, newest-first, bounded limit ≤ 100, safe 404s (bad UUID included), and return the documented strangler adapter: compatibility `id` = processing `jobId`, explicit `projectId`, `project_name`/`starred` from the project, legacy lower-case status. Listings are global among token holders — portfolio access control, not multi-tenant auth.

## Migration/runtime packaging

The API image now ships `alembic.ini` (+`%(here)s` script location) and the migration tree; compose gained a one-shot `migrate` service (`alembic upgrade head`) that must complete before the API starts (`service_completed_successfully`). **Clean-volume proof:** `down -v` → `up --build --wait` rc 0 with `migrate` logging `→ 0001 → 0002` and exiting 0 before the API went healthy; readiness 200 through the stack; live token gate 401/200; live end-to-end create → browser-style POST to LocalStack → list showing `status=queued`, `pipeline_revision=dev`, sanitized key `uploads/{jobId}/source/live_clip.mp4`, distinct IDs. LocalStack bootstrap/verification now also enforce+assert **block-public-access (all four flags) and AES256 default encryption**.

## Test and CI surface

**79 cloud tests pass** (auth 6, CORS 2, validation 33, state machine 8, readiness 6, DB integration 13, G2.5 populated round-trip 1, G3 integration 6, health/docs 4) under Python 3.12.13 against compose PostgreSQL + LocalStack (`make cloud-test`, now setting `INSTASCRIBE_TEST_S3=1`). CI's `cloud-api` job gained a LocalStack service container and the S3 test env; an idempotent bucket fixture lets CI run without the compose bootstrap. No remote CI result is claimed before a push. Regressions: root pytest 56, ruff clean, frontend 8/8 + fixture preview 200, `git diff --check` clean, `alembic check` drift-free.

## Residuals for G4+

Upload-complete + HeadObject verification + SQS publication (G4, catching the compute-slot unique violation); source ETag/checksum evidence at G4; worker claim/execution (G5); real-S3 oversize enforcement test (G11); production image digest pinning (pre-G9); owner decisions D1–D7 unchanged.
