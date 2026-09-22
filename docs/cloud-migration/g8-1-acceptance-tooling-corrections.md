# G8.1 — Acceptance-tooling and pre-G9 corrections (evidence)

Date: 2026-08-08. Commits: `be713f1` (Part A claims/rubric), `9aed864`
(Parts B–E tooling), `7c7ec2c` (Part F API image), `48c5786` (aggregate-
caught smoke fixes), plus this evidence commit. Accepted history through
`0ada898` unamended.

**The original G8 result is preserved as credible one-off evidence.** The
independent review confirmed the G8 chain, reran the suites, checked the
exact worker image, and found no harm to unrelated state. G8.1 makes future
reruns fail closed and removes claims broader than the evidence — it does
not falsify or discard the historical G8 measurements.

## Corrected claim boundaries (Part A)

- **Evaluation contract (one precise statement, everywhere):** G8 freezes
  3–5 rights-cleared evaluation **cases**. At G8, non-overlapping bounded
  windows from one verified rights-cleared source are permitted as the
  safe minimum. They freeze the harness, provenance and rubric, not corpus
  diversity. Multiple distinct rights-cleared source clips are a v0.2
  benchmark requirement and require owner/licence review before addition.
  Reconciled in ADR-0008 §4 (forward clarification), the implementation-
  plan G8 gate, `docs/evaluation-contract.md`, the manifest notes and the
  G8 evidence. The four windows are never presented as four clips.
- **Memory/sizing:** R2 and the G8 evidence now state exactly what was
  measured — ONE runtime-generated 299.084 s, ~22 MB Sintel-derived input
  (that codec/resolution/content pattern, local amd64 emulation), 6.56 GiB
  peak under 8 GiB, 18 % headroom, no OOM in that run; G0's 4 GiB OOM
  still proves 4 GiB insufficient; this does **not** prove all ≤5-minute
  inputs, codecs/resolutions, or the 250 MiB envelope fit in 8 GiB. R2
  likelihood restored to M; sizing provisional until native G11 plus
  representative/worst-case coverage.
- **Rubric:** the ambiguous single `score` is gone. Review records carry
  REQUIRED bounded integers `groundednessScore` and `usefulnessScore`
  (1–5). `validate_review_record` fails closed on missing fields,
  booleans, non-integers, out-of-range values, unknown error categories,
  empty rationale, and the old single-`score` shape (test-only samples;
  the manifest still contains no completed review rows).

## Defect → executing regression map

| Review finding | Correction | Executing proof |
|---|---|---|
| 1. "3–5 distinct clips" wording | one precise cases/windows contract | doc reconciliation (A1); manifest notes; `test_frozen_manifest_validates` |
| 2. memory over-generalization | narrowed R2/G8 wording, residual M | doc diff (A2); historical numbers unchanged |
| 3. stale tag accepted; no lock | source-digest labels + binding checks; host-global gate lock | `test_digest_*` (5 tests); live stale-tag failure demonstrated pre-rebuild; `test_gate_lock_contention_fails_second_acquirer` (two cwd paths), `test_gate_lock_is_per_gate` |
| 4. fail-open cleanup; delayed msgs unchecked; CPU unmeasured; constant accounting | checked label-scoped queries; 3-counter queues; HostConfig+cgroup CPU proof; queried DB/S3 accounting | `test_docker_query_failure_fails_closed`, residue trio, `test_delayed_message_counts_as_residue`; memtest cpu evidence; `test_reconcile_*` (4 tests) + live step 12 |
| 5. unproven log order | structured job_ready→message_success proof | `test_ready_before_ack_*` (4 tests incl. prose-substring rejection); live: `job_ready[2] -> message_success[3] (attempt 1)` |
| 6. ambiguous rubric score | two named 1–5 integer fields | `test_review_record_fails_closed` (10 cases) + missing-field/old-shape tests |
| 7. shell-interpolated size pipeline | argument-list + zlib stream, checked rc, ref validation | `test_compressed_size_streams_and_checks_return_code`, `test_docker_save_failure_cannot_produce_a_size`, `test_shell_metacharacters_rejected_before_execution` |
| 8. floating API base, no amd64 proof | digest-pinned, source-bound API image + live proof | `make g8-api-image-proof` PASSED (below) |

The gate-tooling suite adds 25 tests; the evaluation suite grew to 33.
Three defects in smoke-local itself were caught BY the new aggregate
(missed override wiring, surviving 2-tuple check, UUID/string accounting
mismatch — the last a fail-closed true negative) and fixed in `48c5786`.

## Source/image binding proof

Digest = SHA-256 over sorted (path, content-hash) pairs of the production
inputs (Dockerfile, locked deps, `.dockerignore`, shipped source, shared
contracts, copied API model/domain subset, pipeline files) — computed
without shell interpolation, passed at build, stored as OCI labels,
recomputed by every runtime gate before services start.

| | Worker | API |
|---|---|---|
| Image ID (final aggregate) | `sha256:933eef2a…a5bbb1` | `sha256:866db122…75cb4` |
| Source digest | `c90beb18…4b6c57` | `5e7bdcdc…71d581` |
| Base digest (label = Dockerfile pin) | `sha256:646fb0bc…02d7b` | `sha256:646fb0bc…02d7b` (amd64 validity proven via `buildx imagetools inspect`: index → amd64 manifest, 3.12.13-slim-trixie) |
| Model revision label | `08e178d4…dfbc4f` | — |
| Stale-tag behavior | fails before any DB/queue work (demonstrated live pre-rebuild) | same check (`g8_api_image_proof`) |

API image proof (PASSED): linux/amd64, 90.3 MB, UID 10001 `api`,
production uvicorn CMD, `pip check`, packaged head `0004_override_fields`,
contract imports, forbidden assets absent, **migration `upgrade head` run
from the exact image** against a run-owned PostgreSQL on a private network,
`/healthz` 200, `/api/readyz` 200 at head → sanitized 503
(`{"status":"unavailable","checks":["database"]}` — no DSN/host/traceback)
while PostgreSQL was stopped → recovered 200.

## Final aggregate (`make g8-acceptance`, once, final source state): PASSED

Strict sequence, no parallel prerequisites: worker build → worker proof →
API build → API proof → five-minute memory test → smoke-local; exit 0.

- **Memory test** (script identical to the fully captured run):
  299.084 s input, cgroup peak 6.65 GiB / 8 GiB (16.9 % headroom;
  run-to-run peaks 6.56–6.65 GiB across G8/G8.1), `memory.events` all
  zero, OOMKilled false, restarts 0, wall 306.4 s (≤ 15 min — a breach now
  FAILS the gate with the R7/owner consequence rather than recording a
  boolean), **CPU machine-verified**: `NanoCpus=2000000000`, cgroup
  `cpu.max` raw `"200000 100000"` → normalized 2.0 vCPUs (2 vCPU remains
  provisional, not proven necessary), queues (visible/in-flight/delayed)
  0/0/0 on work AND DLQ.
- **smoke-local** (205.5 s, all 12 steps): both bound images verified and
  asserted on the running containers; distinct IDs `226480e0…`≠`74266abb…`;
  READY in 137.6 s; manifest 6/6 signed fetches; `scene_3` PATCH with
  `scenes.json` checksum unchanged; restart-persistence; structured
  delete-order `job_ready[2] → message_success[3] (attempt 1)`, no
  `success_ack_pending`, one claim; accounting queried: DB
  projects/jobs/artifacts/overrides = 1/1/8/1 (identities asserted), S3 =
  8 objects, 8 single versions, 0 delete markers, 0 unknowns; teardown
  label-verified clean.

## Final regression counts (after the final source state)

| Gate | Result |
|---|---|
| Gate-tooling tests (new) | **25 passed** |
| Evaluation manifest + review-record | **33 passed** |
| `make g5-test` (worker suite incl. tooling) | **134 passed** |
| `make cloud-test` | **286 passed** (1 pre-existing warning) |
| `make isolation-proof` | ISOLATION PROOF OK |
| `make g2-verify` | No new upgrade operations detected |
| Root `pytest -q` | **89 passed** (56 legacy + 33 evaluation) |
| `ruff check .` / `ruff format --check .` | All checks passed / 168 files formatted |
| Frontend Vitest / ESLint / tsc | **189 passed** / 0 errors (1 pre-existing warning) / clean |
| Production, cloud, demo builds + preview smoke | green; `/` 200, scenes.json 200 (8,655 B) |
| `git diff --check` + secret/media/handoff/tfstate scans | clean; handoffs never staged |

No UI source changed (frontend gates were regression-only).

## Remaining owner blockers and pre-G9 limitations

- **D1** AWS account/IAM + region; **D2** budget amount/recipient/test
  notification; **D7** worker run mode + monthly ceiling — all owner
  decisions, all still open.
- Task sizing remains provisional until native G11 measurement plus
  representative/worst-case input coverage (R2, likelihood M).
- Evaluation corpus diversity is v0.2 (single-source windows at G8).
- The gzip-equivalent compressed size and any local Docker `RepoDigests` are
  local evidence only. No remote ECR/registry manifest digest exists until an
  authorized push; G9/G10 must record the digest of the eventually pushed
  artifact rather than treating a local RepoDigest as registry proof.
- Everything remains local/fake-provider; no real AWS, no ECR, no
  Terraform, no paid calls, no real-provider quality claims.
