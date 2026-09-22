# G9.1 local Terraform correction evidence

> Historical G9.1 record. G9.2 replaces its manual ECS inspection commands with committed
> fail-closed migration and API-enablement verification runners. See
> `g9-2-local-runner-evidence.md`; credentialed execution remains NO-GO.

**Date:** 2026-08-08
**Branch/base:** `feat/aws-cloud-core`, forward-only from accepted G9 commits
**Boundary:** local code, formatting, provider-schema validation, static graph and mocked contracts
**Decision:** credentialed planning remains **NO-GO**

G9.1 responds to the independent G9 review without rewriting accepted history. It uses the existing
checksum-verified Terraform 1.13.5 binary and already initialized HashiCorp-signed AWS provider
6.58.0 in `/private/tmp/instascribe-g9-terraform`. It performs no credential/profile/account
inspection, AWS CLI/API call, real plan, apply/destroy/import/state operation, ECR login/push,
migration, deploy, DNS/ACM action, provider spend or remote Git action.

## Corrections implemented

- Fail-closed bootstrap: API and worker desired counts both default to zero; each is validated as
  0/1. The API may be one only after a successful migration and a second reviewed plan/apply.
- A concrete one-shot Fargate migration task uses the immutable API image, DB host/port/name,
  RDS-managed username/password injection, URI-safe SQLAlchemy URL construction,
  `alembic upgrade head`, Alembic 1.19's locally verified `current --check-heads`, dedicated logs,
  least-privilege execution role, empty task role, dedicated no-ingress SG and no port/service.
- One `release_commit_sha` — exactly 40 lowercase hex — drives API image, worker image, migration
  image, `INSTASCRIBE_PIPELINE_REVISION` and worker identity. Divergent tag/revision inputs no longer
  exist.
- Origin protection requires one active 64-lowercase-hex value and one/two distinct exact accepted
  values containing active. Secrets Manager records active and accepted JSON separately. The ALB
  rule consumes only the exact accepted list; CloudFront consumes only active. The tested rotation is
  `[A]` → active A/[A,B] → active B/[A,B] → `[B]`. Wildcards, whitespace, uppercase, duplicates,
  third values and missing-active lists fail closed. State/plans remain sensitive.
- The invalid `TLSv1.2_2021` claim was removed from the AWS default CloudFront certificate. R20 is an
  explicit owner decision: accept AWS default-certificate viewer behavior for the bounded
  environment or later authorize DNS plus `us-east-1` ACM. G9.1 creates neither. R19 HTTP origin-leg
  risk remains separate.
- Worker ephemeral storage is explicitly 40 GiB. The cost model includes the charged 20 GiB above
  the included allocation. Sizing remains provisional pending native G11 peak/free-space evidence;
  insufficient space requires more reviewed capacity or a narrower public input claim.
- S3 wording now distinguishes the 72-hour environment target from three-day lifecycle eligibility,
  subsequent noncurrent eligibility, UTC rounding, asynchronous processing and manually bounded
  bucket emptying at teardown.
- `project_name` maximum is 18 characters so current ALB suffixes stay within AWS's 32-character
  naming limit; tests accept 18 and reject 19.

## Required local validation record

The final record is populated only after all commands pass:

| Gate | Required result |
|---|---|
| `terraform fmt -check -recursive .` | passed |
| credentials/profile unset + metadata disabled `terraform validate -no-color` | passed |
| mocked `terraform test -no-color` including bootstrap, migration, API-enable, rotation and negative cases | **16 passed, 0 failed** |
| Alembic compatibility: existing API venv `alembic 1.19.0`; `alembic current --help` | passed; supported flag is `--check-heads` |
| `terraform graph -type=plan -draw-cycles` | passed; exit 0 |
| `uv run --with-requirements requirements-dev.txt pytest -q` | **89 passed** |
| `git diff --check`; scoped secret/account/state/media/handoff scans | passed; owner handoffs never staged |

Mock-provider tests are credential-free and do not prove AWS availability, IAM effectiveness,
service readiness, migration against RDS, CloudFront propagation or billing.

## Owner gates and residual inputs

- **D1:** exact AWS account, intended least-privilege identity and plan authority.
- **D2:** Budget/SNS recipient, subscription confirmation and post-apply test notification.
- Stable bucket suffix, one real 40-hex release SHA, portfolio-token digest, active/accepted 64-hex
  origin values and access-restricted local state handling.
- Separate authorization for the bootstrap plan; later bootstrap apply remains distinct. Image push,
  migration run, API-enable plan, API-enable apply and readiness/smoke are further separate actions.
- **R19:** owner acceptance or redesign for the HTTP CloudFront-to-ALB origin leg.
- **R20/D8:** owner acceptance of AWS default viewer-certificate behavior or later authorization for
  DNS plus `us-east-1` ACM. No TLS 1.2 floor is claimed now.
- Credentialed plan review must still confirm regional availability/prices, unique bucket names,
  resource count, task/IAM/network behavior, zero service bootstrap and no unexpected replacement.

G10 and all AWS actions remain blocked until these gates are explicitly satisfied.
