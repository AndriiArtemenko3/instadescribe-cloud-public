# G11 AWS cloud smoke — fake provider and persistence

**Date:** 2026-08-09  
**Region:** `eu-west-2`  
**Deployed API/worker release:** `64263e48d49fc3c476274903912405a4069c730c`  
**Provider:** `fake` only — no paid or external model calls

## Verdict

The v0.1 AWS vertical slice passed its functional cloud-smoke gate. Real AWS
S3, SQS, ECS Fargate, RDS PostgreSQL, CloudFront and the FastAPI application
completed the upload-to-editor path; the worker was returned to desired and
running count zero after the bounded test window.

This does **not** establish real-provider output quality. It also does not
close the full input-envelope or resource-sizing claim: sampled ECS metrics
are not cgroup peaks, peak ephemeral-filesystem use was unavailable, and the
real-S3 greater-than-250-MiB POST rejection remains unmeasured.

## Executed journeys

### Existing browser upload

- The previously uploaded source was durably verified and present as one SQS
  message while the worker was disabled.
- A saved Terraform plan changed only `aws_ecs_service.worker.desired_count`
  from zero to one: zero creates, zero deletes, zero replacements and no
  warnings.
- The worker became running after approximately 86 seconds, claimed the job,
  advanced it from `QUEUED` through real pipeline stages, and committed
  `READY_FOR_REVIEW` at 100% with no job error.
- The queue drained and the DLQ remained empty.
- The inverse reviewed plan returned the worker to zero immediately after the
  run.

### Rights-cleared Sintel fixture

- The committed Sintel fixture was uploaded directly to private S3 through
  the production presigned POST contract and completed through the protected
  API.
- The exact canonical SQS message was parsed through
  `QueueMessage.from_body()` and one byte-equivalent duplicate was published.
- The worker processed the media once. The duplicate was acknowledged after
  the terminal state without a second pipeline run; both queue messages
  drained and the DLQ stayed empty.
- The job reached `READY_FOR_REVIEW` at 100% with no error. Worker startup was
  approximately 85 seconds; terminal job state was observed at approximately
  193 seconds and the duplicate queue was fully drained by approximately 214
  seconds.

### Artifact and editor evidence

- The manifest returned eight non-null references: the pinned source video,
  five required JSON artifacts and two posters.
- Every fetched object matched its manifest byte size, content type and
  SHA-256 checksum.
- Manifest and object responses carried `private, no-store` cache policy.
- A real signed video byte-range request returned HTTP 206 with the expected
  `Content-Range`.
- One canonical scene edit persisted in PostgreSQL.
- Exactly one running API task was deliberately stopped. The replacement was
  healthy after approximately 137 seconds; the job, edit, fresh manifest and
  signed Range request all remained usable afterward.

### Failure boundary

- A harmless committed audio fixture was deliberately uploaded under the
  `.mp4`/`video/mp4` contract.
- Worker-side `ffprobe` validation rejected it before model work.
- The job reached `FAILED` with `error_code=invalid_media` in approximately
  ten seconds; the message was acknowledged and the DLQ remained empty.

## Operational evidence

| Evidence | Observed result |
|---|---:|
| Worker tasks | 2 bounded Fargate tasks |
| Worker reservation | 2 vCPU / 8 GiB / 40 GiB ephemeral storage |
| Image-pull interval | 66.6–68.2 seconds |
| Task runtime interval | 151.9–623.4 seconds |
| Sampled ECS CPU maximum | 87.97% |
| Sampled ECS memory maximum | 56.04% |
| Worker structured-log events | 20 |
| Job-claim markers | 3, including invalid-media validation |
| Duplicate markers | 2 |
| Invalid-media markers | 2 |
| Work queue after cleanup | 0 visible / 0 in flight |
| DLQ after cleanup | 0 |
| API after cleanup | desired 1, healthy and ready |
| Worker after cleanup | desired 0, running 0 |

The CPU and memory figures are one-minute ECS service samples, not process or
cgroup peaks. They must not be used to claim a 44% memory headroom. Peak
filesystem consumption/free-space floor was not observable because Container
Insights and ECS Exec are disabled and the deployed worker does not emit that
telemetry.

## Security and cost posture

- The OpenAI secret remained an empty shell and neither task received an
  OpenAI credential.
- The API, persisted jobs, worker policy and child process remained pinned to
  `fake`.
- A bounded scan of the API and worker log windows found no portfolio-token,
  credential, traceback, presigned-URL or `OPENAI_API_KEY` leakage indicators.
- All signed responses and identifiers captured during the operation remain
  only in ignored, mode-600 local evidence files.
- The worker is disabled after the test; the 8-GiB task is not incurring
  ongoing compute cost.

## Honest residuals

1. The canonical plan names `make smoke-cloud`, but no committed target or
   tested orchestration runner exists yet; this run used fail-closed manual
   commands and saved Terraform plans.
2. Peak filesystem consumption and the free-space floor remain unmeasured.
3. Real-S3 ordinary POST, version-pinned GET and Range semantics passed, but a
   greater-than-250-MiB POST-policy rejection was not exercised.
4. A single API task caused a bounded readiness interruption during the
   deliberate replacement. High availability is not claimed.
5. Generated descriptions are deterministic fake-provider placeholders. G12
   is the separate, paid, real-provider evidence gate.

These residuals do not block the bounded G12 test, but they remain explicit
limitations for the v0.1 release packet.
