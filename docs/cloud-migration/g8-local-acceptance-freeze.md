# G8 — Local acceptance freeze (evidence)

Date: 2026-08-08. Commits: `34eb766` (Part A evidence reconciliation),
`c1a0fea` (Part B worker contracts), `ca5a7fb` (Parts C/E/F contract +
tooling), `2c64a03` (script poster fix), plus this evidence commit.
Accepted history through `e0eb003` unamended; branch `feat/aws-cloud-core`;
upstream `commercial/feat/aws-cloud-core`.

**Claim boundary:** everything here is local — PostgreSQL + LocalStack
S3/SQS, the fake vision provider, real FFmpeg/VAD/ASR from baked offline
weights. No real AWS, no real-provider quality, no full workflow parity,
no production readiness, no scale, no approval/review workflow, and no
completed export is claimed. Nothing was pushed, merged, tagged, released,
deployed, provisioned or paid.

## Part B — worker contract gaps closed

- **Exact scene IDs** (`services/worker/instascribe_worker/artifacts.py`):
  `re.fullmatch` replaces `.match` (whose `$` accepted one literal trailing
  newline). Regressions cover a REAL trailing LF (`"scene_1\n"`), CRLF, CR,
  leading/trailing spaces, suffixes, prefix garbage, case, zero and negative
  ordinals — plus an acceptance case for `scene_1/2/10/999`. The API/DB
  contract was already exact and is unchanged.
- **Revision bounds** (`services/worker/instascribe_worker/config.py`):
  `INSTASCRIBE_PIPELINE_REVISION` now mirrors the API validator and the
  `sa.String(120)` column — trimmed, non-empty, ≤ 120 characters
  (previously untrimmed ≤ 100). Boundary tests: `"  dev  "` → `dev`,
  lengths 1 and 120 accepted, empty-after-trim and 121 rejected.
  Non-retryable `pipeline_revision_mismatch` before any source/model work
  is unchanged (integration matrix still covers it). No migration.

## Part C — evaluation contract (frozen)

`tests/fixtures/evaluation/manifest.v1.json`
(schema `instascribe-eval-manifest/1`) + fail-closed
`tests/test_evaluation_manifest.py` (21 tests) + `docs/evaluation-contract.md`.

Four non-overlapping windows of the ONE committed rights-cleared fixture —
Sintel (© copyright Blender Foundation, durian.blender.org, CC BY 3.0,
`https://creativecommons.org/licenses/by/3.0/`), SHA-256
`75de21cc8ed60ece2d43e0127db8449e4eef0ae44ca47a586791945de0e5648b`,
8,940,006 bytes, 120.000 s measured: 0–30 s (opening/coverage), 30–60 s
(dialogue timing), 60–90 s (action density), 90–120 s (tail/assembly).
Each case carries source/title/owner/licence/hash/size/duration, a bounded
window, deterministic structural expectations (required artifact set,
fullmatch scene-ID rule, time bounds, strict-JSON validity, dialogue-gap and
assembly checks), the shared 1–5 groundedness/usefulness rubric protocol and
the closed error taxonomy. Validation fails closed on: unknown schema
version, missing source, hash/size/licence mismatch, duplicate case IDs,
overlapping/invalid windows, unresolved expectation keys, incomplete
rubric/disclosure. **Honest limitation (G8.1 precise contract):** the
four cases are non-overlapping windows of ONE rights-cleared source, not
four independent clips — the permitted G8 safe minimum freezing harness/
provenance/rubric, not corpus diversity; distinct clips are v0.2 and need
owner/licence review first. No new media, labels, study results or quality
claims.

## Part D — current production image (rebuilt from final G8 source)

`make g8-build` → tag `instascribe-worker:g8`, image ID
`sha256:8bc4ffb41ac30ec0669860c25871f5e97bcc3da9f6d53570a8f6047b4c5967b1`,
created 2026-08-07T22:43:15Z. Build wall time **3.5 s** — layer-cache warm
from the G5 build (base/deps/weights layers unchanged); only the changed
source layers re-ran. In-image greps confirm the rebuilt image carries the
Part B `fullmatch` and 1–120 revision code.

`make g8-image-proof` (G8 IMAGE PROOF PASSED):

| Proof | Value |
|---|---|
| Platform | linux/amd64 |
| Base image | `python:3.12-slim@sha256:646fb0bc…02d7b` (digest-pinned) |
| Whisper snapshot | `08e178d48790749d25932bbc082711ddcfdfbc4f`, baked; `refs/main` pinned; offline resolution proven with `HF_HUB_OFFLINE=1` |
| Dependency gate | `pip check` + exercised torchaudio resample — `torch 2.11.0+cpu / torchaudio 2.11.0+cpu` |
| Runtime user | uid 10001 (`worker`) |
| Forbidden assets | absent (fixture, g0_smoke, App/, tests, `.env*`, `*.mp4`, job data, `*HANDOFF*`) |
| API model/domain copy | imports inside the image (`app.models`, `app.domain.states`, worker + contracts) |
| Sizes | unpacked 3,468,778,728 B (3.47 GB); gzip-compressed 3,464,708,727 B (3.46 GB — recorded, not claimed byte-reproducible) |

## Part E — mandatory five-minute 8 GiB memory test (R2): **PASSED**

`make g8-memtest` on the run-owned Compose project `instascribe-g8-memtest`
(its `down -v` touches only that project's volume). Input generated at
runtime and never committed:
`ffmpeg -y -v error -stream_loop 2 -i App/public/videos/sintel-blender-cc.mp4 -t 299 -c copy …`
(ffmpeg 8.1.2) → 21,976,408 B, SHA-256 `108a772d…4c146e` (this run only —
no cross-ffmpeg-version byte reproducibility claimed), ffprobe-asserted
**299.084 s** (gate: > 295, ≤ 300).

| Measurement | Value |
|---|---|
| Image | `instascribe-worker:g8` (`sha256:8bc4ffb4…67b1`, verified on the running container) |
| Limits | 2 vCPU / 8 GiB (`memory.max` = 8,589,934,592 verified), concurrency one |
| Stages | fake provider, audio extraction ON, real FFmpeg/VAD/ASR, offline weights |
| Transitions | QUEUED → PROCESSING → READY_FOR_REVIEW |
| Wall (worker start → Ready) | **310.4 s**; DB started→completed 307.2 s (≤ 15 min — R7 posture unchanged) |
| cgroup `memory.peak` | **7,044,927,488 B = 6.56 GiB** |
| Headroom | **18.0 %** (narrow — recorded honestly) |
| `memory.events` | low 0, high 0, max 0, **oom 0, oom_kill 0**, oom_group_kill 0 |
| Docker | OOMKilled false, restarts 0 |
| Artifacts | full required set + optional posters |
| Queues | work 0/0, DLQ 0/0 |
| Teardown | project down, zero container/volume residue (asserted) |

The five-minute peak (6.56 GiB) matches the 120 s fixture's ~6.6 GiB peak
for THIS input family: whisper-medium weights dominated in the tested runs.
The owner decision branch (raise memory vs lower the advertised duration)
was **not** needed for this input. *G8.1 claim boundary:* the measurement
covers ONE ~22 MB Sintel-derived input at its codec/resolution/content
pattern under local amd64 emulation — it does not prove all ≤5-minute
inputs, all codecs/resolutions, or the 250 MiB upload envelope fit in
8 GiB; task sizing remains provisional until native G11 plus
representative/worst-case coverage. 2 vCPU is still not proven necessary.

## Part F — `make smoke-local` (one command): **PASSED**

Run-owned Compose project `instascribe-g8-smoke` (Make help warns its
`down -v` destroys that project's volume only; the script refuses to start
while the dev stack is running). Total 210.7 s. All 12 steps:

1. liveness + `/api/readyz` 200 at migration head;
2. protected create → distinct IDs (`b9ba7818…` ≠ `ce837f14…`);
3. browser-style presigned POST reached private S3;
4. upload-complete → exactly one visible strict-contract message;
5. QUEUED → PROCESSING → READY_FOR_REVIEW in 140.6 s (fresh image verified
   on the container);
6. required artifact rows/objects with matching SHA-256 checksums, JSON
   content types, `jobs/{id}/attempts/1/` prefix and pinned source
   VersionId (posters present as optional extras);
7. manifest signed the row-resolved version-pinned video + all five JSON
   artifacts; all six fetched 200 and the video bytes hash-matched the
   fixture;
8. exact generated scene ID `scene_3` PATCHed; override visible in the
   overrides map; `scenes.json` object checksum unchanged (generated data
   immutable);
9. API restart preserved job, artifact and override state;
10. fresh manifest + override fetch fully usable after the restart;
11. deletion ordering: `job_ready` (post-commit) logged before the ack,
    no `success_ack_pending`, exactly one `job_claimed`, work queue and
    DLQ drained;
12. accounting: 1 upload object, 7 generated objects, 1 job row, 8
    artifact rows, 1 override row — all inside the named project; teardown
    left zero containers/volumes (asserted).

## Final regression matrix (counts collected after the final source state)

| Gate | Result |
|---|---|
| Focused scene-ID + revision tests (in worker suite) | pass (within 109) |
| Evaluation-manifest validation | **21 passed** |
| `make g5-test` (worker unit+integration) | **109 passed** |
| Image inspection (`make g8-image-proof`) | PASSED |
| Five-minute memory (`make g8-memtest`) | PASSED (6.56 GiB/8 GiB) |
| `make smoke-local` | PASSED (12/12) |
| `make cloud-test` | **286 passed** (1 pre-existing warning) |
| `make isolation-proof` | ISOLATION PROOF OK (no consuming worker) |
| `make g2-verify` (Alembic drift) | No new upgrade operations detected |
| Root `pytest -q` | **77 passed** (56 + 21 new) |
| `ruff check .` / `ruff format --check .` | All checks passed / 162 files formatted |
| Frontend Vitest (full) | **189 passed** (19 files) |
| ESLint / `npx tsc -b --force` | 0 errors (1 pre-existing warning) / clean |
| Production, cloud, demo builds | green |
| Demo preview smoke | `/` 200 html; `/tutorials` 200; scenes.json 200 (8,655 B); video 200 (8,940,006 B) |
| `git diff --check` | clean |
| Secret / media / generated-file / handoff scans | clean; handoffs never staged; temp video never committed |

No UI code changed during G8 (the G7 live-browser evidence remains valid
and is reused per Part A; frontend gates were re-run for regression only —
`npm install` restored the declared dev dependencies locally, a
node_modules state change, not a source change).

## Phase 1 acceptance matrix (staged handoff §18)

| Acceptance item | Status |
|---|---|
| FastAPI health/readiness + core job endpoints | ✅ smoke-local step 1-4; cloud suite 286 |
| PostgreSQL/SQLAlchemy/Alembic jobs foundation | ✅ g2-verify drift-free; restart persistence proven |
| Direct S3-compatible upload + artifact manifest via LocalStack | ✅ steps 3, 7 |
| SQS/DLQ + one worker adapter path | ✅ steps 4-5, 11; DLQ empty |
| Existing pipeline in an isolated workspace with the fake provider | ✅ steps 5-6; memory test |
| Existing Vite frontend creates/polls/opens one processed job locally | ✅ G7 live-browser evidence (Part A) |
| At least one scene override persists in PostgreSQL | ✅ step 8-10 (persists across restart) |
| Legacy fixture demo remains green | ✅ demo build + preview smoke |

## Limitations and rollback

- Local/fake-provider only; every claim above stops at the local boundary.
- One 299.084-second, approximately 22 MB, Sintel-derived input passed locally
  under 8 GiB; this does not prove every ≤5-minute input, codec/resolution or
  the 250 MiB upload envelope. Native Fargate behavior remains a G11 boundary.
- Build wall time (3.5 s) reflects a warm layer cache; a cold rebuild costs
  what the G5 evidence recorded.
- The evaluation corpus has no diversity (one film); v1 freezes only the
  harness and rubric.
- Rollback: G8 is additive (docs, tests, scripts, two bounded worker
  fixes); revert per commit. The compose worker default tag is unchanged
  (`instascribe-worker:g5`) unless `INSTASCRIBE_WORKER_IMAGE` is set.

## Remaining pre-G9 blockers / owner decisions

- **D1** AWS account/IAM + region (blocked, owner);
- **D2** budget amount/recipient/test notification (blocked, owner);
- **D7** worker run mode + monthly ceiling before any AWS resource
  (ADR-0008 §5; always-on ≈ $97.82/mo worker task estimate);
- Production API image prerequisite completed in G8.1: digest-pinned base,
  explicit linux/amd64 build and live migration/readiness smoke (see
  `g8-1-acceptance-tooling-corrections.md`);
- deployed reader `s3:GetObjectVersion`; lifecycle protection for pinned
  noncurrent source versions;
- Terraform ignore rules before `terraform init`; pre-apply cost estimate
  at the G9 approval point.
