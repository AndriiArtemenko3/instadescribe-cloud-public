# G5 + G5.1 — Production worker vertical slice (evidence)

Dates: G5 2026-08-07; G5.1 correction gate 2026-08-07. Scope: the bounded
production worker (strict SQS consumer → atomic claim → exact versioned
source download → ffprobe gate → unchanged subprocess pipeline →
attempt-scoped artifacts → idempotent persistence → bounded retry/DLQ), the
production `linux/amd64` image, and the full production-image fake-provider
smoke. Fake vision output — but real S3/SQS/PostgreSQL/ffmpeg/VAD/ASR/
pipeline orchestration throughout. No real AWS, no real provider calls, no
leases/heartbeats/crash-reclaim (v0.2), no G6 manifest/override routes, no
bit-reproducible-image claim, no remote-CI claim.

## Honest correction record (G5.1)

**The original G5 35-test matrix did NOT prove all claimed acceptance
areas.** Independent review reproduced ten correctness/secrecy failures the
green suites missed; each now has a forward fix and a regression test. The
earlier evidence's claims are REPLACED by this document.

| # | Reproduced failure | Fix (commit) | Regression proof |
|---|---|---|---|
| 1 | A forged message naming a `READY_FOR_REVIEW` job was deleted before its `messageId`/`requestedAt` were checked | identity validated before EVERY terminal policy (`0f1881c`) | `test_forged_identity_against_terminal_job_is_never_acknowledged` |
| 2 | A deterministic failure deleted the message even when the guarded `FAILED` write returned false | every guarded result honored; False = ownership loss, no delete (`0f1881c`) | `test_stolen_ownership_during_failure_never_deletes_or_claims_failure` |
| 3 | Every task incarnation fenced with the static label `worker-local-1` | per-claim UUID ownership token in `jobs.worker_id`; label is log-only (`0f1881c`) | `test_same_label_two_attempts_all_stale_operations_fenced` |
| 4 | A raising progress callback left `run_job.py` alive while the workspace was removed; timeout/SIGTERM hit only the parent | new session/process group + one idempotent `terminate_tree` on every executor exit, before workspace cleanup (`0f1881c`) | real child+grandchild PID tests: timeout, callback exception, SIGTERM, interruption |
| 5 | Invalid settings printed secret-bearing inputs in an uncaught Pydantic traceback | `hide_input_in_errors` + entrypoint category event, exit nonzero (`0f1881c`) | `test_invalid_config_exits_nonzero_without_secrets_or_traceback` |
| 6 | Pre-claim SQS/DB failures crashed with raw SDK/DB traceback text | sanitized boundaries (category + class name), bounded backoff in continuous mode, `--once` exits nonzero (`0f1881c`) | secret-injection tests over DSN/queue URL/endpoints |
| 7 | The "fake-only" provider allowlist was environment-overridable | code-constant `PROVIDER_ALLOWLIST`; hostile env proven inert (`0f1881c`) | `test_only_fake_provider_is_allowlisted_and_env_cannot_override` |
| 8 | Success commit + SQS delete failure was misreported as a processing failure/requeue | acknowledgement is a separate post-commit step: `success_ack_pending`, no failure transition (`0f1881c`) | `test_ack_failure_after_success_is_ack_pending_not_processing_failure` |
| 9 | The reusable upload POST could create a newer source at the same key (manifest would serve video B for video A's artifacts) | S3 versioning required + exact pinned `VersionId` end to end (`9f384c3`) | `test_persisted_version_survives_source_overwrite` + smoke step 7b |
| 10 | Tests never drove three real retries into the DLQ; poison logging was tested without the consumer; artifact/finalization failure paths untested | full D3 matrix added (commit 3) | see the matrix below |

## Consumer contract (after G5.1)

**Ownership**: each successful claim generates a fresh cryptographically
strong UUID token persisted in `jobs.worker_id`; every progress, duration,
retry, failure and success predicate uses that exact token. Labels never
fence (deployments overlap; task names recur).

**Identity before policy**: the complete persisted logical identity —
`jobId`, `enqueue_message_id`, original `enqueue_requested_at` (taskType and
schema enforced by the strict parser) — is validated before ANY terminal
acknowledgement or claim. `QueueMessage.from_body` accepts only the
canonical serializer grammar `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` (ISO
week/ordinal dates, space separators, comma fractions, minute-only stamps
and non-Z offsets rejected), plus the existing exact-key/duplicate-key/8 KiB
bounds.

**Terminal acknowledgement matrix** (canonical identity required first):

| Persisted state | Policy |
|---|---|
| READY_FOR_REVIEW / COMPLETED | acknowledged, no rerun |
| CANCELLED | acknowledged — documented policy: cancellation is a durable owner action; compute never runs; retention would only pollute the DLQ |
| FAILED with non-retryable code (`invalid_settings`, `invalid_media`, `source_identity_mismatch`, `pipeline_revision_mismatch`) | acknowledged |
| FAILED with `retry_exhausted` | left for DLQ transfer |
| FAILED with retryable or UNKNOWN code | left for DLQ/repair — never assumed safe |
| PROCESSING (another claim) | left unacknowledged (no v0.1 lease) |
| forged/mismatched identity (any state) | zero mutation, zero delete; redrive owns it |
| any terminal delete failure | sanitized `*_ack_pending`, state untouched, redelivery retries |

**Guarded results**: `guarded_update`/`guarded_transition` returning False is
ownership loss — no delete, no visibility change, no success/failure claim
(`stale_owner` outcome). The claim-lost exhaustion UPDATE is atomic over job
ID + complete message identity + claimable status + `attempt_count >=
max_attempts`, rowcount honored. Failure-path DB exceptions roll back
best-effort and never delete.

**Acknowledgement separation**: after the success (or durable FAILED)
commit, SQS deletion is its own step — `success_ack_pending` /
`failed_deterministic_ack_pending` on failure, and canonical redelivery
acknowledges without any pipeline/artifact rerun.

## Execution safety (after G5.1)

- `run_job.py` runs in its own session/process group; one idempotent
  `terminate_tree` (TERM group → bounded grace → KILL group → always reap)
  runs on timeout, SIGTERM/SIGINT, callback exceptions and every executor
  exit — proven with a REAL child spawning a REAL grandchild (recorded PIDs,
  both gone, child reaped, workspace removed after). No mocked `Popen`.
- Progress mirroring dedups unchanged observations and throttles
  progress-only churn; stage changes and ≥99 write immediately; a long
  unchanged status produces a bounded number of database writes.
- The provider set is code policy (`("fake",)`) — hostile environment
  variables are inert; the child env stays pinned to
  `INSTASCRIBE_BACKEND=fake` with no DSN/AWS credentials.
- `jobs.settings` passes the strict shared `StoredJobSettings` contract
  (exact keys, strict types, v0.1 allowlists/bounds) before download/model
  work — malformed persisted settings are deterministic `invalid_settings`.
- The worker requires `INSTASCRIBE_PIPELINE_REVISION` (dev locally); a
  claimed job persisted for a different revision fails as non-retryable
  `pipeline_revision_mismatch` before source/model work.
- Startup/cycle failures are category-only events; injected secrets
  (DSN passwords, queue hosts/ports, signed-URL-ish strings) proven absent
  from stdout/stderr along with tracebacks; continuous mode backs off
  boundedly; `--once` exits nonzero on an infrastructure failure.

## Source and media authority (after G5.1)

- S3 versioning enabled and machine-asserted (`Status=Enabled`) in
  bootstrap/verify and every test fixture. Upload completion REQUIRES a
  non-empty `VersionId` (missing evidence = sanitized 503; no slot, no
  enqueue). Publication retries compare VersionId EXACTLY — same-bytes
  overwrites (same ETag, new version) are refused — and checksum evidence
  symmetrically in presence and value.
- The worker downloads ONLY the pinned `VersionId` (no If-Match fallback);
  the `source_video` row records `{etag, version_id}` and provenance is
  refused without a pin. Proven: after processing, a new version at the same
  key leaves the pinned version serving the original bytes byte-for-byte
  (integration test + smoke step 7b).
- The S3 `StreamingBody` is closed in `finally` on every failure path; when
  a trustworthy checksum was persisted, checksum response mode is requested
  and an absent returned checksum is an identity failure.
- ffprobe's measured duration is authoritative: persisted via a
  claim-guarded update before model work; a false declaration cannot bypass
  the 300 s cap; an in-bounds wrong declaration is replaced by the
  measurement. Extension↔MIME pairing is enforced at the API AND the worker;
  the probed container must match the extension's family.

## Artifacts (after G5.1)

- Strict standards-compliant JSON (NaN/Infinity rejected); `scenes.json` is
  a non-empty list of objects with unique canonical `scene_[1-9][0-9]*` IDs
  and finite ordered bounds; `result.scene_count` must be an honest positive
  int (bool rejected) equal to the validated count; required JSONs keep
  their expected top-level types; posters degrade safely.
- Generated keys are ATTEMPT-SCOPED: `jobs/{job_id}/attempts/{attempt}/…`.
  A stale attempt can never change a winner's bytes; winning rows are
  selected atomically inside the success transaction; superseded attempt
  objects remain under the private prefix for lifecycle cleanup (G9 adds
  noncurrent-version + stale-attempt expiry; IAM adds `s3:GetObjectVersion`).

## Test evidence (after the final source edit)

| Suite | Result |
|---|---|
| Worker unit + integration (`make g5-test`) | **95 passed** (67 unit + 28 integration; was 35 at G5) |
| API cloud suite (serial; incl. 13 wire-grammar + versioning + pairing cases) | **170 passed** (was 147) |
| Isolation proof (DB sentinel + dev-queue sentinel + attributes) | ISOLATION PROOF OK |
| Alembic drift (no G5.1 migration was needed) | no new upgrade operations |
| Root suite (fresh light venv; incl. the fake-provider geometry regression) | 56 passed |
| Ruff check + format (repo) | clean |
| Frontend: ESLint / Vitest / `tsc -b` + production build / demo build / preview smoke | 0 errors (2 pre-existing warnings) / 16 passed / clean / built / `GET /` 200 + fixture 200 |
| Cold-start LocalStack bootstrap + verify | asserts `versioning=Enabled` + CORS/queues/redrive |

Previously missing matrix now proven (D3): every required artifact
missing/malformed/wrong-shape/non-standard JSON; the scene ID/bounds/count
matrix; poster presence+absence; idempotent per-type upsert with winner-key
replacement; S3 upload failure before finalization (retryable, no rows, no
delete); DB failure after uploads (no rows, no delete) and failure-handler
DB outage (`db_unavailable`, nothing acknowledged); full-flow stale finalize
(no winner overwrite, no delete); post-success delete failure + canonical
re-acknowledgement; **three REAL retryable failures → durable
`FAILED/retry_exhausted` → actual DLQ arrival of the retained canonical
message**; **hostile malformed AND oversized poison through the real
consumer → actual DLQ arrival, zero job mutation, zero hostile text in
logs**; the complete FAILED-duplicate code matrix incl. unknown codes;
forged identity against terminal states; two claim tokens under one label
with every stale operation fenced; the API-finalizer race still monotonic.

## Production image

Multi-target `services/worker/Dockerfile` (unchanged from G5, rebuilt from
final source): `base` pinned by digest
(`python:3.12-slim@sha256:646fb0bc…`), ffmpeg/ffprobe, non-root UID 10001,
`pip check` + exercised torchaudio resample, faster-whisper medium baked at
pinned snapshot `08e178d48790749d25932bbc082711ddcfdfbc4f` with offline
resolution asserted in-build, `HF_HUB_OFFLINE=1`; `g0smoke` retained;
`production` contains no fixture/smoke/tests/`.env`/media/credentials/
handoffs (build fails otherwise; runtime `find` re-proves it).
`torch==2.11.0+cpu` / `torchaudio==2.11.0+cpu` aligned; boto3/SQLAlchemy 2/
psycopg 3/pydantic-settings in the compiled x86_64 lock.

## Production-image smoke (`make g5-smoke`)

**PASSED — all 11 steps, 2026-08-07, total 222.4 s** (rebuilt image from the
final G5.1 source). Clean stack → protected create → browser-style presigned
POST of the Sintel fixture → verified upload-complete (VersionId REQUIRED
and pinned) → exactly one strict visible message → the PRODUCTION worker
(2 vCPU / 8 GiB / concurrency one / fake provider / offline models) →
`QUEUED → PROCESSING → READY_FOR_REVIEW`.

An earlier smoke run legitimately FAILED with `artifacts_invalid` ×3 →
`retry_exhausted`: the new strict scene validation caught the fake
provider's zero-length final scene per chunk (`end == start`) — real
providers never emit zero-length scenes (the committed fixture confirms),
so the placeholder geometry was corrected to conform to the schema rather
than weakening the validator. The retry → exhaustion → durable FAILED path
this exercised end-to-end in the production image matched the designed
behavior exactly.

| Measurement | Value |
|---|---|
| Status transitions observed | `QUEUED → PROCESSING → READY_FOR_REVIEW` |
| Wall time, worker start → READY_FOR_REVIEW | 145.3 s |
| `started_at → completed_at` (database) | 141.6 s |
| Container memory peak (cgroup `memory.peak`) | 7,121,543,168 B ≈ **6.63 GiB** (8 GiB sizing holds) |
| Ownership | `worker_id` is a per-claim UUID token (asserted) |
| Measured duration persisted | ~120 s (the fixture's actual length, not the declared hint) |
| Attempt count / progress / stage | 1 / 100 / `complete` |
| Artifact rows | 8 — 5 analysis JSONs + 2 posters (all **attempt-scoped**: `jobs/{id}/attempts/1/…`) + `source_video` |
| Checksums / sizes / SSE | every S3 object read back; SHA-256 + byte size equal the rows; `AES256`; `source_video` checksum equals the local fixture SHA-256 |
| Source version proof (step 7b) | overwrite at the same key: latest bytes differ, the pinned `VersionId` still serves the analyzed bytes byte-for-byte |
| Queue after success | 0 visible + 0 in-flight (deleted only after the commit) |
| API restart persistence | job + rows unchanged |
| Image | amd64/linux, 3,468,777,605 B (3.47 GB); fixture/smoke/tests/`.env`/media absent (runtime `find` proof) |
| Terminal idempotency | duplicate canonical message acknowledged; rows byte-identical; exactly ONE `job_claimed` in the logs |

Fake vision output — real S3/SQS/PostgreSQL/ffmpeg/VAD/ASR/pipeline
orchestration, under amd64 emulation on the development host.

## Honest v0.1 limitations and blockers to G6

- **No leases/heartbeats/crash reclaim** (v0.2): a worker that dies
  mid-PROCESSING leaves the row in PROCESSING; redelivery is refused by the
  claim conditional until operator repair — disclosed, unchanged by G5.1.
- **At-least-once, not exactly-once**: duplicates are handled by terminal
  policy + stable identity; `*_ack_pending` outcomes rely on canonical
  redelivery to complete acknowledgement.
- **Fake provider only** (code policy); real-provider quality unproven until
  the owner-approved G12 action.
- **LocalStack, not AWS**: S3/SQS semantics are LocalStack 4.14.0; LocalStack
  does not enforce presign `content-length-range` (real-S3 test at G11);
  native Fargate timing/memory re-measured at G11.
- **Emulated amd64 measurements** on Apple silicon; not production
  performance claims. Image digests pin inputs; the image is not claimed
  bit-reproducible.
- **G6 not started**: no manifest/override routes, no frontend changes. G6
  must resolve artifact ROWS (attempt-scoped keys) and serve the pinned
  source version — both prerequisites are now in place.

Sintel fixture: © copyright Blender Foundation | durian.blender.org — CC BY
3.0; attribution retained in `THIRD_PARTY_NOTICES.md` and the demo UI.
