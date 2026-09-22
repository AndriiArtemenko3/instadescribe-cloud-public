# G8.2 final fail-closed corrections

**Date:** 2026-08-08
**Scope:** local acceptance tooling and evidence only; no product/API/pipeline/UI behavior, AWS,
Terraform, remote, release or deployment action.

> **Forward evidence note:** G8.2.1 subsequently tightened exact Docker absence/name handling,
> case-insensitive secret and cache context parity, snapshot-based database accounting, exact-image
> orchestration and API one-shot cleanup. Its fresh image IDs, counts and runtime measurements in
> [`g8-2-1-supervisory-fail-closed-corrections.md`](g8-2-1-supervisory-fail-closed-corrections.md)
> supersede the corresponding values below; this historical G8.2 record is retained unaltered apart
> from this pointer.

G8.1 remained credible. G8.2 closes the independently reproduced gaps that could otherwise let
future local acceptance runs authenticate incomplete source, hide cleanup/accounting failures or
overstate their evidence.

## Defect-to-executing-regression map

| Finding | Correction | Executing negative proof |
|---|---|---|
| copied trees were suffix-filtered | every copied entry binds relative path, type, POSIX mode and regular-file content; missing roots and symlink/special entries fail | worker + API add/change/remove `.yaml`, `.bin`, HTML and extensionless cases; executable-bit, missing-root, symlink and FIFO/special-file cases |
| private-key-like material lacked an explicit context boundary | `.dockerignore`, both Dockerfiles and both image proofs exclude/check `*.pem`, `*.key`, `*.p12`, `*.pfx` | context-policy regression plus both in-image forbidden-asset proofs |
| API proof cleanup was name-based and incomplete | host lock precedes exact lookup; stable owner + run labels; PostgreSQL uses an explicit named volume; containers/network removed by inspected IDs, volume by exact inspected name; every remove and absence query is checked | owned stale cleanup; unowned container/network/volume collision; query/remove failure and surviving residue cases |
| cleanup could replace a primary failure and print raw stderr | cleanup commands return typed safe categories; `preserve_primary_cleanup` keeps the active exception authoritative and reports only a sanitized secondary category | success+cleanup failure, primary+success, primary+`SystemExit`-like cleanup failure |
| memory Compose calls could fall back to default images | one `memory_compose` path always applies the G8 override; preflight/teardown do too; API is asserted after initial up and again after worker start, worker after start | injected call recorder and mismatched-running-API failure |
| an S3 current object could have zero version records; pagination markers could stall | current and version key sets must be exactly equal; expected version absence fails; object/version tokens must be usable and advance; marker pairs are rebuilt per page | zero-version, missing/non-advancing marker and same-key/multi-version pagination cases |
| database evidence checked totals incompletely | one shared helper validates exact project, `(job, project)`, `(job, artifact type, key)` and `(job, scene)` identities and is called by `smoke_local.py` | extra project/job/artifact/override plus wrong-count-equal artifact identity cases |
| local/remote digest and size prose was stale | local RepoDigests are distinguished from remote ECR manifest digests; current production image replaces the G0 probe as the G9 estimate input | documentation consistency review plus final image proof |

Focused G8.2, prior gate-tooling and evaluation-manifest tests: **102 passed**. The complete worker
suite, which also executes these tests under its integration environment: **178 passed**.

## Final source and image proof

| Artifact | Evidence |
|---|---|
| Worker | `linux/amd64`; ID `sha256:dd97955fca3121e8f0331213dfbcdcdce47d9f8fc095442e2236cb359d34373d`; source digest `454e4fc047b96a55709692c9c2648b041b3ea6bf4832cd228d99b73d95940559` |
| Worker pins | base `sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b`; Whisper `08e178d48790749d25932bbc082711ddcfdfbc4f` |
| Worker size | 3,468,780,081 B (3.47 GB) unpacked; 3,464,708,186 B (3.46 GB) checked shell-free local compressed-transfer measurement |
| API | `linux/amd64`; ID `sha256:49285186abf506d0a8ef266b8868c85c72407485cc209940b26a96d99b79458d`; source digest `26282a1e1e273b581682a6c7ad440a46f20111f9e529266b235ff0de172f7ab6`; 90,294,764 B unpacked |
| API proof | UID 10001, production uvicorn CMD, dependencies/imports/migration head, exact-image `upgrade head`, readiness 200 → sanitized 503 → 200, owned container/network/named-volume cleanup |

Both forbidden-asset proofs passed. A local Docker RepoDigest is not a remote registry fact. No
remote ECR/registry manifest digest exists yet; it can be recorded only after an authorized push.

## Final runtime evidence

`make smoke-local` passed from the corrected final source: **211.4 s** total, **140.6 s** from
worker start to `READY_FOR_REVIEW`. Exact worker/API image IDs were verified. PostgreSQL contained
exactly one project, one job, eight artifacts and one override with the expected identities. S3
contained exactly eight current keys and eight one-version records, with zero delete markers.
Structured logs proved `job_ready[2] → message_success[3]` for attempt 1. Restart persistence,
manifest fetch and the persistent scene edit passed. Container/network/volume residue: zero.

`make g8-memtest` passed from the same final source:

- input: 299.08431 s, 21,976,408 B, Sintel-derived runtime file;
- effective limits: 2 vCPU (`NanoCpus=2000000000`, `cpu.max=200000 100000`) and 8 GiB;
- worker start to Ready: **305.1 s**; database processing: **302.0 s**;
- `memory.peak`: **7,101,669,376 B = 6.61 GiB**; headroom **17.3%**;
- `oom=0`, `oom_kill=0`, `OOMKilled=false`, restarts 0;
- full eight-artifact set; work and DLQ visible/in-flight/delayed all `0/0/0`;
- container/network/volume residue: zero.

Claim boundary: **one 299.084-second, approximately 22 MB, Sintel-derived input passed locally
under 8 GiB; this does not prove every ≤5-minute input, codec/resolution or the 250 MiB upload
envelope.** Native Fargate behavior and representative/worst-case coverage remain G11/v0.2 work.

## Regression gates

- cloud API: **286 passed** (known Starlette/httpx deprecation warning only);
- database isolation proof: **OK**; Alembic drift: **none** at `0004_override_fields`;
- root Python: **89 passed**;
- Ruff check and format: clean;
- frontend: ESLint 0 errors (one existing hook warning), **189 tests**, forced TypeScript clean,
  production/cloud/demo builds green, preview and fixture HTTP 200;
- `git diff --check` and secret/media/generated/handoff/Terraform-state scans: clean.

## Remaining owner decisions and boundaries

- **D1:** AWS account/IAM and `eu-west-2` confirmation;
- **D2:** budget amount, recipient and test notification;
- **D7:** worker run mode, monthly ceiling and disable/teardown procedure. Always-on is not the
  default.

G9 still needs Terraform ignore rules before `terraform init`, a written pre-apply cost estimate,
and later authorized remote-image digest capture. G11 must verify real S3, native Fargate sizing,
pull/runtime behavior, `s3:GetObjectVersion` and noncurrent-version lifecycle. No AWS credential,
paid provider, Terraform, public origin or remote action occurred in G8.2.
