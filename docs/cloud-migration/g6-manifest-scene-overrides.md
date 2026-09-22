# G6 + G6.1 + G6.2 — Version-pinned manifests and persistent scene overrides (evidence)

Date: G6 2026-08-07; G6.1 correction gate 2026-08-07. Scope: FABLE5 Phase 1
G6 — migration `0004_override_fields`, the exact version-pinned artifact
manifest, atomic persistent scene overrides — plus the G6.1 fail-closed and
evidence corrections. **G6.1 corrections applied:** generated-artifact keys
are validated by EXACT equality (`winning_prefix + suffix`), closing
nested/substring/duplicate-basename/traversal acceptance, with proof the
signer is never called for an inconsistent manifest; the source row must
also match the job's `input_content_type`/`input_size_bytes`; huge JSON
integers can no longer raise an uncaught OverflowError; speed rejects more
than two decimal places (NUMERIC(4,2) — 2.499 is refused, never silently
stored as 2.50); scene ids use `fullmatch` (a URL-encoded trailing newline
is 422) and PostgreSQL's ARE `$` was PROVEN to already reject
`'scene_1'||chr(10)` at the constraint (`f`), so no forward migration was
needed; every presigned GetObject carries
`ResponseCacheControl="private, no-store"` and GET overrides returns the
same header; final manifest serialization sits inside the sanitized 503
boundary; the live smoke fetches ALL required artifacts and exits nonzero
unless machine-verified cleanup succeeds. **Claim boundary:** this is a backend capability for a
**persistent human edit** — not a completed human-review workflow, not
frontend-integrated (G7), not real-S3 behavior (G11), not SaaS/customer
isolation, no exactly-once claim. Semantics are honest per-field
**last-write-wins**, not optimistic locking. Signed URLs pin the **exact
source version**, they are not immutable upload URLs.

## Gate 1 — migration `0004_override_fields`

Head after G6: `0004_override_fields` (fits the VARCHAR(32) revision column).
Adds `locked BOOLEAN NOT NULL DEFAULT false` and database-level checks:
`version >= 1`; `speed IS NULL OR (speed >= 0.50 AND speed <= 2.50)`;
`scene_id ~ '^scene_[1-9][0-9]*$'`. Retained: job FK with ON DELETE CASCADE,
unique `(job_id, scene_id)`, `text` backing wire field `ad`, `active`
default true, `version` default 1, timezone-aware server `updated_at`.
Migrations 0001–0003 unamended.

Proof (9 focused tests, `test_g6_migration.py`): populated 0003 → 0004 keeps
every pre-existing override value and applies `locked=false` to existing
rows; downgrade to 0003 preserves all values and drops the column;
re-upgrade succeeds; `alembic check` reports no drift (`make g2-verify`
after live upgrade: "No new upgrade operations detected"); PostgreSQL — not
only Pydantic — rejects `scene_01`/`shot_1`/`scene_0`/empty ids, speeds
0.49/2.51 and version 0; boundary rows (0.50, 2.50, NULL) are accepted.

## Gate 2 — `GET /api/v1/jobs/{job_id}/manifest`

The path identifier is a processing **job** ID. Policy: only
`READY_FOR_REVIEW` serves a manifest in bounded G6; malformed UUID, absent
job, or a project ID supplied as the job ID → generic 404 `not_found`;
other states → 409 `artifacts_not_ready`; database/signing/consistency
failures → sanitized 503 `manifest_unavailable` with a stable category
logged (`category=database|signer|<consistency>`); responses carry
`Cache-Control: private, no-store`.

Resolution: persisted artifact ROWS only (never reconstructed keys):
`source_video→video`, `scenes_json→scenes`, `entities_json→entities`,
`audio_events_json→audioEvents`, `ad_placement_gaps_json→placementGaps`,
`transcript_json→transcript`, optional `poster_jpg→posterJpg`,
`poster_avif→posterAvif` (explicit null when absent); unknown artifact
types ignored; ANY missing/inconsistent required row refuses the whole
manifest. Generated rows must live under the winning
`jobs/{job_id}/attempts/{attempt_count}/` prefix with the expected suffix,
exact content type, positive size and lowercase 64-hex SHA-256. The source
row must equal `job.input_object_key` and carry
`{etag, version_id}` == the job's pinned identity; the signed GetObject URL
pins the exact `VersionId` (opaque query parameter — no raw VersionId field
on the wire). Presigning uses the browser-visible endpoint: locally URLs
contain `localhost:4566`, never `localstack:4566`. New typed config
`INSTASCRIBE_DOWNLOAD_PRESIGN_EXPIRY_SECS` (60..900, default 300); one
manifest request uses ONE common expiry instant; URLs are never persisted
or logged.

**G6.1 corrections in this gate:** generated rows are validated by EXACT
key equality (`winning_prefix + expected relative suffix`) — the earlier
prefix/basename/substring combination accepted nested, substring and
duplicate-basename forms; equality is validation only and the persisted row
key is still what gets signed. The source row additionally requires
`content_type == job.input_content_type` and
`size_bytes == job.input_size_bytes`. Every presigned GetObject sets
`ResponseCacheControl="private, no-store"`, and final contract
validation/serialization sits inside the sanitized 503 boundary
(`category=contract`).

Proof (45 focused tests, `test_g6_manifest.py` — final G6.2 collection):
contract shape/headers/
expiry; live signed fetches of the video PLUS all five required JSON
references — each 200, exact seeded bytes, actual response Content-Type,
SHA-256 equal to the manifest checksum, browser-visible host only, and
`Cache-Control: private, no-store` on every SIGNED response;
`Range: bytes=4-15` → 206 with `Content-Range: bytes 4-15/{size}`;
after overwriting the reusable source key, BOTH the previously issued URL
and a freshly requested manifest still serve the originally processed
bytes; posters absent (null) and present (fetchable); unknown row ignored;
each required row missing in turn → 503; SIX adversarial malformed keys
(`xanalysis`, nested `evil/analysis`, duplicate-basename tails, a
traversal-like `../` form, losing attempt) → 503 with the signer PROVEN
never called; wrong content type, zero size, non-lowercase checksum → 503;
source key/version/etag/unpinned/content-type/size mismatches → 503;
injected signer, database AND final-serialization failures → sanitized 503
with no key/bucket/hostname/DSN/signed-URL/traceback in body or logs;
token required; unprefixed route strict 404.

## Gate 3 — atomic scene overrides

Routes: `PATCH /api/v1/jobs/{job_id}/scenes/{scene_id}` and
`GET /api/v1/jobs/{job_id}/overrides`, both `READY_FOR_REVIEW`-only with
the manifest's 404 identity policy; other states → 409 `job_not_editable`;
database failures roll back → sanitized 503 `persistence_unavailable`.

PATCH accepts a non-empty STRICT subset of
`{ad ≤8000 chars, active, locked, voice ∈ onyx|nova|alloy|shimmer|echo|fable,
speed ∈ [0.5, 2.5]}`: unknown fields and client `version` forbidden;
explicit null invalid (omitted ≠ null); booleans must be JSON booleans;
speed must be a finite JSON number (bool/string/NaN/Infinity rejected — a
non-finite constant yields a CLEAN 422 via a JSON-safe validation-error
handler added after finding the default handler crashed serializing NaN
input); `ad` may be empty and keeps tabs/newlines but rejects NUL/unsafe C0;
nothing is clamped or silently ignored. Scene ids validated for canonical
shape (≤120 chars, `^scene_[1-9][0-9]*$`). **G6.1:** huge JSON integers
(hundreds of digits) are a normal 422, not an uncaught OverflowError; the
PRECISION CONTRACT rejects more than two decimal places (`NUMERIC(4,2)` —
`2.499` is refused rather than silently stored as `2.50`; boundaries
0.5/0.55/1.25/2/2.5 accepted unchanged); scene ids use `fullmatch`, so a
URL-encoded trailing newline (`scene_1%0A`) is 422 with no row; PostgreSQL
was PROVEN to already reject `'scene_1'||chr(10)` at the existing 0004
constraint (`SELECT ('scene_1'||chr(10)) ~ '^scene_[1-9][0-9]*$'` → `f`,
INSERT raises), so no forward migration was needed. **G6.2 precision
honesty:** the two-decimal contract applies to PARSED numeric values — no
parsed value is silently rounded by PostgreSQL; lexically over-precise JSON
such as `2.5000000000000001` or `1.2300000000000000000001` resolves to the
IEEE-754 values 2.5/1.23 in standard request parsing BEFORE validation and
is therefore accepted as those parsed values (recorded by raw-body tests).
Lexical decimal preservation is not claimed. Checksum validation is also
exact (`fullmatch` — G6.2): a 64-hex checksum with a trailing newline on
either a generated or the source row refuses the manifest with the signer
proven uncalled.

Persistence is ONE `INSERT ... ON CONFLICT (job_id, scene_id) DO UPDATE`:
insert starts at version 1; a conflict update touches ONLY the fields
present in the request, never resets omitted fields, and explicitly sets
`updated_at = now()` and `version = version + 1` (ORM onupdate not relied
upon). GET returns the exact raw legacy map ordered scene-numerically
(`scene_2` before `scene_10`), `{}` when empty, with no version/timestamps/
IDs/wrapper metadata inside the map. The generated `scenes_json` artifact
is immutable — edits live only in `scene_overrides` (proven: zero artifact
rows written by PATCH).

Proof (43 focused tests, `test_g6_overrides.py` — final G6.2 collection):
insert/update round trip
with response versions 1→2 and `updatedAt` ending in Z; empty map; tabs/
newlines/empty ad; 17 invalid payload shapes fail WITHOUT any row mutation;
NaN/±Infinity → clean 422, no row; 7 non-canonical scene ids → 422
`invalid_scene_id`; identity policy (project-id-as-job-id/absent/malformed
→ 404, no row) and five non-ready states → 409; sanitized DB-failure 503.
Concurrency (deterministic barriers, independent clients/sessions — no
timing sleeps): six parallel PATCHes to different scenes all persist; two
concurrent DISJOINT patches to the same initially absent scene both
survive with response versions {1,2} and final version 2 (next write → 3);
two concurrent same-field patches leave one submitted value with the
version incremented twice (honest last-write-wins — not an error).
G6.1 additions: huge positive/negative JSON-integer regressions (clean 422,
no traceback, no row); precision-contract boundaries and rejections;
encoded-newline scene id; the direct PostgreSQL newline proof; the
GET-overrides database-failure injection (rollback + sanitized 503, no
DSN/SQL leak); and `Cache-Control: private, no-store` on GET overrides.

## Gate 4 — identity, authorization, CORS

Both new routers mount ONLY under the central `/api/v1` token dependency.
The structural auth inventory now walks EVERY leaf router (jobs, manifest,
scenes) and every actual HTTP method: each guarded path returns the same
generic 401 for missing/wrong tokens, and every equivalent unprefixed path
is a strict 404. CORS adds PATCH without broadening origins: an
approved-origin preflight with `Content-Type` + `X-Portfolio-Token`
succeeds; an unapproved origin is denied. The portfolio token is never
forwarded to S3 (signed URLs carry no token/header material). Manifest and
PATCH responses echo both distinct IDs (`projectId`, `jobId`) for G7.
One portfolio-wide token — not customer isolation, not SaaS auth.

## Live proof (`services/api/scripts/g6_smoke.py`) — PASSED, all 6 steps (G6.1 flow)

Rebuilt API image from G6.1 source (`docker compose up --build`), migrated
to head, in-image route inventory listing exactly the seven `/api/v1`
routes incl. the three G6 routes; seeded a RUN-OWNED ready job (recorded
every created S3 VersionId); live manifest → the video AND all five
required JSON references fetched with exact bytes, actual content types,
manifest-equal checksums and `Cache-Control: private, no-store`
(`fetched_required_artifacts` records all six); `Range` 206 with correct
`Content-Range`; overwrote the source key → both the old URL and a fresh
manifest still served the originally processed bytes; live PATCHes
(versions 1→2) and the private cache header on GET overrides;
`docker compose restart api` → the override map shows EXACT SEMANTIC MAP
EQUALITY (the smoke compares parsed JSON maps, not raw response bytes) and the
manifest REMAINS USABLE (two independently generated manifests are NOT
byte-identical — fresh signatures/expiry are expected; instead the newly
signed pinned video is fetched again and its bytes, checksum and private
cache header re-verified). **Fail-closed cleanup (G6.1, hardened G6.2):**
every DB deletion and exact-VersionId S3 deletion is attempted regardless
of earlier failures; absence is then MACHINE-VERIFIED — a version counts as
absent ONLY on a genuine 404 response with an exact not-found code
(`NoSuchVersion`/`NoSuchKey`/`NotFound`/`404`); AccessDenied, throttling,
service 500s and transport failures are recorded as VERIFICATION FAILURES
(deterministic injected regressions prove each class); the script exits
nonzero on any residue and prints `G6 SMOKE PASSED` only after that
verification. Latest run: `cleanup_failures: []`, `cleanup_residue: []`,
final live LocalStack observation: `s3_not_found_observed: [NoSuchVersion]`
(the exact 404-shape code LocalStack 4.14.0 produced for every deleted
version — the durable authoritative record). Shared dev
data untouched.

## Regression gate (after the final source edit)

| Check | Result |
|---|---|
| Populated 0003→0004→0003→0004 + drift | pass (`test_g6_migration.py`; `alembic check` clean) |
| `make g1-up` stack + migrate + `make g2-verify` | up; head `0004_override_fields`; "No new upgrade operations detected" |
| Focused G6/G6.1/G6.2/G6.3 tests (final `--collect-only` after the G6.3 reconciliation) | 45 manifest + 43 overrides + 11 smoke-helpers = **99** three-file total; + 9 migration + 6 auth = **114** five-file evidence total. (At the `c075e11` checkpoint the read-only collection was 45/43/10 = 98 and 113; G6.3's hostile-`Error.Code` regression adds one helper case.) |
| `make cloud-test` | **278 passed** (277 at G6.2; 259 at G6.1; 244 at G6) |
| `make isolation-proof` | ISOLATION PROOF OK |
| `make g5-test` (shared models) | 95 passed at G6 — G6.1 changed no ORM/migration metadata, so per the correction gate it was not rerun |
| API image build/import + route inventory | rebuilt; 7 routes verified in-image |
| Live signed-GET / Range / source-overwrite / PATCH / restart | G6 smoke passed (above) |
| Root `pytest -q` | 56 passed |
| `ruff check .` / `ruff format --check .` | clean / 151 files formatted |
| Frontend lint/tsc/Vitest/build/demo + preview smoke | 0 errors (2 pre-existing warnings) / 16 passed / builds clean / `GET /` 200 + fixture 200 |
| `git diff --check` + secret/media/handoff scan | clean; no handoff staged |

## Boundaries, limitations and forward notes

- **LocalStack, not AWS**: signed URL/Range/versioning behavior is
  LocalStack 4.14.0; real S3 (incl. presign policy enforcement) remains G11.
- **Canonical-but-nonexistent scene ids** create orphan override rows —
  explicit v0.1 limitation; G6 does not fetch `scenes.json` per PATCH.
- **Last-write-wins** per field; no optimistic locking or review-state
  machine in v0.1 (the `version` column is ready for a v0.2 409 contract).
- The worker's production image embeds a copy of `app/models` from G5.1;
  G6's model change (locked + checks) is API-only surface — the worker
  never reads `scene_overrides` — so the 3.47 GB image was not rebuilt and
  the G5 smoke was not rerun (no worker code/packaging/image file changed);
  the image will naturally re-bake at its next required rebuild.
- Forward (pre-G9, recorded not implemented): deployed reader role needs
  narrowly scoped `s3:GetObjectVersion`; lifecycle must not expire a pinned
  noncurrent source version while a durable job references it; align the
  worker's 100-char `pipeline_revision` bound with the API/DB 120-char limit.
- **v0.2 pre-export prerequisite (recorded, not implemented):** once
  transitions out of `READY_FOR_REVIEW` exist (export flows), editability
  must be fenced ATOMICALLY against those transitions — no such transition
  is part of G7/v0.1, so no post-review state machinery was added here.
- **G8 forward note (recorded, not implemented — G6.2):** at G8's mandatory
  worker rebuild/memory test, change
  `services/worker/instascribe_worker/artifacts.py` scene-ID validation
  from `.match()` to `.fullmatch()` and add a worker regression for
  `scene_1\n`. The pipeline constructs scene IDs internally, so this does
  not block G7; changing the worker now would force an unnecessary 3.47 GB
  rebuild that already belongs to G8.
