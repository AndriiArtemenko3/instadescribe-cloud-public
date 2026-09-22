# G9 local Terraform implementation evidence

> Historical G9 record. G9.1 supersedes its one-API default, two-variable provenance,
> origin-header, viewer-TLS, worker-storage and S3 timing claims. See
> `g9-1-local-correction-evidence.md`; credentialed planning remains NO-GO.

**Date:** 2026-08-08
**Branch/base:** `feat/aws-cloud-core`, reconciled forward from accepted G8.2.1 commit `5fdd210`
**Implementation commit:** `df9508def08ea7fc6617255f281ad097182121af`
**Boundary:** local code, formatting, provider-schema validation and mocked contracts only

No AWS credential, profile, account identity, AWS CLI/API, Terraform plan/apply/destroy/import/state
operation, ECR login/push, deployment, migration against RDS, DNS change or paid-provider call was
used. No public origin or remote Git action occurred.

## Forward reconciliation from G8.2.1

- Region is now owner-selected as `eu-west-2`; D1 remains open only for the exact AWS account/IAM
  identity and authority used by a later credentialed plan.
- D7 is resolved for v0.1: ephemeral evidence environment, intended maximum 72 hours; worker
  `desired_count = 0` by default, explicitly bounded to one for controlled G11/G12 tests. No queue
  autoscaling is implemented or claimed; scale-to-zero automation remains v0.2.
- The planning AWS Budget threshold is USD 25. D2 remains open for the real recipient, subscription
  confirmation and test notification; no address was invented or committed.
- G8.2.1's 2-vCPU/8-GiB worker sizing and exact-version source contract are retained. Native
  Fargate, real S3, remote image digest/size and broader input-envelope proof remain G11 boundaries.

## Implemented Terraform surface

`infrastructure/terraform/portfolio/` is one explicit environment (no premature modules):

- Terraform/AWS provider constraints and signed multi-platform lockfile;
- VPC, two public subnets, two isolated database subnets, IGW/routes and no NAT;
- security groups: CloudFront prefix list to ALB, ALB to API:8000, no worker inbound, private RDS
  from API/worker only;
- ALB listener default 403 plus secret-header forwarding rule, target group and `/healthz` check;
- ECS cluster, x86 Fargate API (0.25 vCPU/0.5 GiB) and worker (2 vCPU/8 GiB) task definitions,
  services and public-IP egress; worker default 0/max 1;
- separate immutable/scanned ECR repositories;
- encrypted private single-AZ PostgreSQL 16 `db.t4g.micro` in isolated subnets with RDS-managed
  credentials;
- private encrypted frontend S3 and private encrypted/versioned media S3, 72-hour upload/job and
  noncurrent-version lifecycle, direct-upload/media CORS;
- CloudFront OAC/static origin, path-scoped SPA rewrite and uncached `/api/*` ALB behavior; no
  distribution-wide error rewrite and no DNS;
- encrypted SQS/DLQ, 30-minute visibility, redrive count 3 and mandatory DLQ-visible alarm routed
  to an SNS email subscription;
- separate least-privilege API/worker execution and task roles, including worker
  `s3:GetObjectVersion` and attempt-prefix writes;
- API/worker CloudWatch log groups; portfolio/origin secret versions, empty G12 OpenAI secret shell,
  RDS-managed secret injection; USD 25 AWS Budget; non-secret outputs.

## Local validation

The global machine had no Terraform CLI. An official Terraform `1.13.5` darwin/arm64 archive was
downloaded only to `/private/tmp/instascribe-g9-terraform`; SHA-256
`1bf942231235e7e1a4c38c6d7b820e54f526ac487f87d19f0c4a425c6ddb62cb` matched HashiCorp's
published checksum. No Homebrew/system install occurred.

| Command/gate | Result |
|---|---|
| ignore proof for `.terraform/`, state, plan, crash, override, auto/secret tfvars | passed before init |
| `terraform init -backend=false -input=false` | passed; installed HashiCorp-signed AWS provider v6.58.0; no backend/AWS call |
| `terraform providers lock -platform=darwin_arm64 -platform=linux_amd64` | passed; lockfile retained |
| `terraform fmt -check -recursive .` | passed |
| credential/profile-unset `terraform validate -no-color` with metadata disabled | passed |
| credential/profile-unset `terraform test -no-color` using `mock_provider "aws"` | **1 passed, 0 failed** |
| root `uv run --with-requirements requirements-dev.txt pytest -q` | **89 passed** |
| `git diff --check` and scoped secret/account/state/media/handoff scans | passed; user handoffs never staged |

The mocked test asserts the one-API/zero-worker defaults, worker sizing, private single-AZ RDS,
30-minute queue visibility, max attempts 3, media versioning and DLQ alarm threshold. It makes no
AWS plan or API call.

The first sandboxed `validate` could not execute the downloaded provider binary; the credential-free
command passed when the provider executable was permitted to start outside that filesystem sandbox.
The first mocked test exposed nondeterministic mock IAM-policy data; explicit safe mock values were
added and the final test passed. Bare `pytest` was not installed and the sandbox blocked the local
uv cache; the repository suite passed through the existing local uv tool/cache outside that sandbox.
The incidental untracked `uv.lock` produced by that command was removed before staging.

The final post-commit audit found that the first ignore set covered auto/secret tfvars but not the
conventional `terraform.tfvars` or arbitrary `*.tfvars` name. A forward-only G9 safety correction
now ignores every `*.tfvars` and `*.tfvars.json` file as well; the tracked
`terraform.tfvars.example` remains a placeholder-only template.

## Still awaiting owner action

- **D1:** exact AWS account and least-privilege IAM identity for an explicitly approved
  credentialed plan.
- **D2:** real Budget/SNS recipient, subscription confirmation and a test notification after apply.
- Plan inputs: stable bucket suffix, immutable commit/image tag, portfolio-token SHA-256 digest and
  high-entropy origin-verification header.
- Explicit authorization for the credentialed `terraform plan`; apply remains a later, separate
  authorization. The plan must confirm prefix-list/AZ/RDS availability, globally unique buckets,
  regional prices, IAM/task-definition behavior and exact resource count.
- With DNS changes excluded, the v0.1 CloudFront-to-ALB custom-origin leg is HTTP. Prefix-list and
  secret-header controls protect direct-origin bypass, but the unencrypted origin leg is a recorded
  R19 residual; if the owner does not accept it, public deployment is blocked pending an authorized
  HTTPS-origin design.

G10–G12 have not started.
