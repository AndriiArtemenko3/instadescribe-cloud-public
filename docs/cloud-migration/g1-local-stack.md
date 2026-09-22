# G1 local-stack evidence

**Date:** 2026-08-06 · **Gate:** Phase 1 G1 — local-stack scaffolding (PostgreSQL + LocalStack S3/SQS + health-only FastAPI)
**Scope guard:** no `/readyz`, no database schema, no job routes, no auth, no presigned uploads, no worker service, no frontend changes.

## Topology (`docker-compose.yml`, project `instascribe-cloud-core`)

| Service | Image / build | Health | Ports | Notes |
|---|---|---|---|---|
| `postgres` | `postgres:16.14` (pinned) | `pg_isready` | 5432 | named volume `pgdata`; local-dev-only placeholder password |
| `localstack` | `localstack/localstack:4.14.0` (pinned; 4.x = community Apache-2.0 line — the CalVer `2026.x` images are the licensed distribution and exit(55) without an auth token, verified during bring-up) | `/_localstack/health` | 4566 | `SERVICES=s3,sqs`, region `eu-west-2`; bootstrap script mounted read-only into `/etc/localstack/init/ready.d/` |
| `api` | built from `services/api/Dockerfile` (python:3.12-slim, non-root uid 10001) | `GET /healthz` | 8000 | starts after postgres + localstack are healthy (`depends_on: service_healthy`) |

Split endpoint configuration carried on the `api` service (first consumed by G3 SDK code): `INSTASCRIBE_S3_ENDPOINT_INTERNAL=http://localstack:4566` (container SDK calls), `INSTASCRIBE_S3_ENDPOINT_PUBLIC=http://localhost:4566` (browser-visible presigning), `INSTASCRIBE_S3_FORCE_PATH_STYLE=1`, plus LocalStack's canonical `test`/`test` placeholder credentials (not real secrets).

## API service

- `services/api/`: FastAPI app with **two custom application routes** — `GET /healthz` (liveness, no dependency checks) and `GET /api/healthz` (exact alias for CloudFront-coherent health checks per implementation-plan §6) — plus FastAPI's built-in docs/OpenAPI routes (`/docs`, `/openapi.json`, …). **Docs-route policy:** enabled locally; configurable off, and disabled for the public portfolio environment before G9. `/readyz` deliberately absent (G2).
- Dependencies: `services/api/requirements.in` → compiled/pinned `requirements.txt` via `uv pip compile` (19 packages): **fastapi 0.141.1, uvicorn 0.52.1, pydantic 2.13.4, starlette 1.4.1**; dev extras (`pytest`, `httpx`) in `requirements-dev.in/txt`.
- Focused tests (`services/api/tests/test_health.py`, run via `make g1-test`): healthz 200 without dependencies; `/api/healthz` byte-identical alias; `/readyz` + `/api/readyz` return 404 (guards accidental early readiness).

## LocalStack bootstrap (`infrastructure/localstack/01-bootstrap.sh`)

Idempotent, version-controlled, runs on every container start (ready.d) and safely re-runnable by hand: probe-then-create for the private media bucket `instascribe-media` (region `eu-west-2`); last-write-wins `put-bucket-cors` (origin `http://localhost:5173`; methods `POST/GET/HEAD`; `AllowedHeaders: *` for presigned-POST form fields; `ExposeHeaders: ETag, Accept-Ranges, Content-Range, Content-Length` for browser `<video>` Range playback); DLQ `instascribe-work-dlq` created first, then work queue `instascribe-work` with `set-queue-attributes` applying `VisibilityTimeout=1800` and `RedrivePolicy{maxReceiveCount:3 → DLQ ARN}`.

## Make targets

`g1-up` (compose up --build --wait) · `g1-down` · `g1-check` (config + both health routes) · `g1-verify` (bootstrap re-run + exact CORS/redrive readback) · `g1-test` (focused health tests in a uv venv).

## Acceptance verification results

| # | Check | Result |
|---|---|---|
| 1 | `docker compose config` | pass |
| 2 | API image builds from its own manifest | pass — 52 MB dependency layer from the pinned manifest alone; app layer 16 kB |
| 3 | Cold `docker compose up --build` | pass (first attempt failed on the licensed `2026.07.2` LocalStack image — exit 55, no auth token; re-pinned to community `4.14.0` and cold start succeeded, `--wait` exit 0) |
| 4 | postgres + localstack healthy | pass — postgres, localstack, api all report healthy |
| 5 | `/healthz` + `/api/healthz` → 200 | pass — both 200 with identical body `{"status":"ok"}` |
| 6 | No `/readyz`, no DB schema | pass — `/readyz` and `/api/readyz` return 404 (also pinned by a focused test); `psql \dt` finds no relations |
| 7 | Bucket, work queue, DLQ, redrive exist | pass — bucket `instascribe-media`; queues `instascribe-work` + `instascribe-work-dlq`; RedrivePolicy `{deadLetterTargetArn: …:instascribe-work-dlq, maxReceiveCount: "3"}`; VisibilityTimeout 1800 |
| 8 | Bucket CORS exactly verified | pass — get-bucket-cors returns exactly: origin http://localhost:5173; methods POST/GET/HEAD; AllowedHeaders *; ExposeHeaders ETag, Accept-Ranges, Content-Range, Content-Length; MaxAgeSeconds 3000 |
| 9 | Second bootstrap run idempotent | pass — manual re-run of the ready.d script succeeds; resources unchanged, CORS/redrive re-applied last-write-wins |
| 10 | Teardown + fresh restart (G1-scoped resources) | pass — `docker compose down -v` removed only project-scoped containers, network, and the pgdata volume; fresh `up --build --wait` returned healthy with all resources re-bootstrapped |
| 11 | Existing pytest + Ruff | 56 passed; `ruff check` + `ruff format --check` clean (61 files) |
| 12 | Frontend lint/typecheck/Vitest/build/demo build/preview smoke | all green (0 errors, 2 pre-existing warnings) |
| 13 | `git diff --check` | clean |
| 14 | No credentials/.env/media/runtime data in images or commits | pass — API image env holds no secrets (base-image Python build key only), non-root `api` user; compose carries only documented placeholders (postgres `local-dev-only`, LocalStack canonical `test`/`test`); no `.env`, media, or runtime data staged |

## Notes

The focused API tests (3) run via `make g1-test` in a service-local uv venv and are deliberately outside the root pytest suite (root CI installs only `requirements-dev.txt`, which has no FastAPI). **Runtime correction (G2 review):** the original G1 run used an unpinned `uv venv` that selected the host's newest interpreter (Python 3.13/arm64) instead of the API contract's Python 3.12 — the target now pins `--python 3.12` and prints the interpreter version with each run. **API image target caveat:** the local image is built for the host architecture (arm64); a digest-pinned base and an explicit `linux/amd64` build + smoke remain mandatory before G9 — the local image proves nothing about the AWS target. The first cold start exposed that LocalStack CalVer images are license-gated — the pin comment in `docker-compose.yml` records this so the lesson is not re-learned. Root suites stay green: 56 pytest, ruff clean, all 8 frontend checks, fixture preview smoke.
