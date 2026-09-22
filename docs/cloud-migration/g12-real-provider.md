# G12 real-provider validation — passed

**Run window:** 2026-08-09–2026-08-10 UTC

**Region:** `eu-west-2`

**Validated release:** `2b10135b212ded8fef61ae6a5f6dcb5ad0cbc86c`

**Model:** `gpt-4.1`

**Source:** rights-cleared 60.083-second Sintel-derived clip

## Verdict

G12 passed. One explicitly authorized, single-attempt OpenAI job reached
`READY_FOR_REVIEW`, loaded in the deployed cloud editor and produced durable,
version-pinned artifacts. The worker was then disabled and both task definitions
were restored to the deterministic `fake` provider contract.

This closes the real-provider gate for the bounded v0.1 Cloud Core claim. It does
not establish general model quality, high availability, automatic scaling, broad
input-envelope coverage or full authoring/export parity.

## Execution history

Two earlier bounded runs remain part of the audit history:

1. The first stopped during faster-whisper word alignment before a paid model
   request. Commit `249caff` added a narrow recovery path for that known alignment
   edge.
2. The next run completed provider-backed child processing but failed closed at
   artifact validation. The rejected workspace was deliberately removed and the
   exact rejected predicate was not retained. A later correction dropped only
   finite zero-duration tail scenes, retained strict rejection for malformed or
   negative-duration scenes and added fixed failure-code logging. That correction
   was evidence-supported, but the earlier cloud failure cannot be attributed to
   one predicate conclusively.

The successful run used commit `2b10135`, which contains both corrections. No paid
retry or resubmission occurred for this job.

## Successful bounded journey

The authorized source was accepted through the deployed API and uploaded directly
to private S3. One durable queue message was created. A reviewed Terraform change
temporarily moved the worker from desired count zero to one; the server-side G12
contract limited source duration to 120 seconds and processing attempts to one.

Observed states included:

```text
QUEUED
  -> PROCESSING / transcribing_audio / 16%
  -> PROCESSING / analyzing_frames / 25%
  -> READY_FOR_REVIEW / complete / 100%
```

The final contract recorded:

- five canonical, contiguous scenes with finite increasing time bounds;
- OpenAI provider provenance with model `gpt-4.1`;
- 10,943 input tokens, 1,568 output tokens and 12,511 total tokens;
- no terminal error;
- the exact deployed pipeline revision `2b10135…`.

The generated descriptions were rendered in the live editor alongside the pinned
source video. This verifies generation and delivery, not the subjective quality of
the descriptions.

## Artifact evidence

Nine non-null manifest artifacts were fetched and checked:

- version-pinned source video;
- scenes;
- entities;
- audio events;
- placement gaps;
- transcript;
- system information;
- JPEG poster;
- AVIF poster.

Every object matched the manifest's positive byte size, content type and SHA-256
checksum. Manifest and artifact responses carried `private, no-store`. A signed,
version-pinned video byte-range request returned HTTP 206 with the expected
`Content-Range`.

The system-information artifact was re-read after restoration through a protected
manifest and revalidated as `provider=openai`, `model=gpt-4.1`, status completed and
12,511 total tokens. No signed URL, token, secret, object key or durable identifier
is retained in this document.

## Timing and cost evidence

The complete submission-to-validation interval was approximately **410.2 seconds**
(6 minutes 50 seconds). The first observed `PROCESSING` state to the terminal state
was approximately **90.6 seconds**. The earlier interval includes the deliberately
manual worker-enablement and Fargate startup sequence; it is not normal autoscaling
or queue-latency evidence and neither figure is a model-only latency claim.

At the standard GPT-4.1 rates checked on 2026-08-10—$2 per million input tokens and
$8 per million output tokens—the measured token counts imply an estimated model
charge of **$0.03443** if all input was billed uncached. This is a calculation from
published rates, not an invoice or the total cost of earlier attempts. See the
[official GPT-4.1 pricing](https://developers.openai.com/api/docs/models/gpt-4.1).

AWS planning used an approximate 2-vCPU/8-GiB worker rate of $0.1434 per task-hour.
The bounded worker interval and the wider environment have not been reconciled to an
AWS invoice, so no exact AWS cost is claimed.

## Safe restoration

Immediately after successful validation, a separately reviewed plan restored the
safe portfolio posture:

- API desired/running count one and ready;
- worker desired/running count zero;
- API and worker provider `fake`;
- 300-second source-duration limit and three-attempt retry contract;
- no OpenAI secret reference in either task definition;
- no conditional worker permission to read the OpenAI secret;
- work queue and DLQ empty.

The OpenAI value remains stored outside Terraform configuration and state. It is not
referenced by, or accessible to, the deployed fake-mode tasks. No secret, portfolio
token, account identifier, email address, ARN or signed URL is included in committed
evidence.

## Claims supported

- The core multimodal audio-description workflow is deployed on AWS.
- A browser upload can proceed through private S3, SQS, a bounded ECS worker,
  PostgreSQL state and manifest-driven editor delivery.
- One single-attempt GPT-4.1 job on a 60-second rights-cleared clip reached
  `READY_FOR_REVIEW` and produced five reviewable scenes.
- Private artifacts were identity-, checksum-, content-type- and Range-verified.
- Heavy processing can be returned to worker count zero outside controlled runs.

## Claims not supported

- model-output quality or a completed human evaluation of this G12 output;
- production-grade, highly available, scalable or autoscaling operation;
- complete SaaS, authentication, tenant isolation or customer use;
- full feature parity, including cloud Smart Fill, TTS preview and final export;
- automated CI/CD deployment;
- leases, heartbeats, cancellation or comprehensive crash recovery;
- exact AWS bill, exact total OpenAI spend or broad five-minute/250-MiB coverage;
- Next.js or Azure experience.

## Release consequence

The historical validation is preserved by source tag `v0.1.0-cloud-core`, which
was subsequently created at `133992307deebdb339786bfbce3bca6714ebd808`.
The recorded runtime/images remain commit `2b10135`; the later evidence-only commit
must not be described as deployed. The public snapshot adds presentation/setup
clarifications without claiming current AWS availability.
