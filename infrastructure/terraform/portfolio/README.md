# InstaScribe v0.1 portfolio Terraform

This directory defines one explicit, short-lived `eu-west-2` evidence environment. It intentionally
uses no modules, no remote backend, no NAT Gateway and no DNS. The API and worker use public-subnet
Fargate tasks with public IPs but security groups permit no direct task ingress. RDS is private,
encrypted, single-AZ and isolated from the internet. Both ECS services default to a desired count of
zero; the API may become one only after the migration task succeeds, and the worker may never exceed
one task in v0.1.

## Safe local validation (no AWS account)

Use a trusted Terraform binary. G9 was validated with checksum-verified Terraform `1.13.5` and the
HashiCorp-signed AWS provider locked in `.terraform.lock.hcl`.

```bash
terraform fmt -check -recursive .
terraform init -backend=false -input=false
AWS_EC2_METADATA_DISABLED=true terraform validate
AWS_EC2_METADATA_DISABLED=true terraform test
bash -n scripts/*.sh tests/portfolio_scripts_test.sh tests/fixtures/bin/*
tests/portfolio_scripts_test.sh
```

Initialization downloads the provider from the Terraform registry only. `validate` and the mocked
contract test require no AWS credentials and must not be replaced by a credentialed plan during the
G9-local gate.

## Inputs for the later owner-approved plan

Copy `terraform.tfvars.example` to the gitignored `portfolio.auto.tfvars`, replace every placeholder,
and make the file readable only by the owner. Required values are:

- the exact owner-approved 12-digit AWS account ID, used only by the provider's fail-closed
  `allowed_account_ids` guard;
- a stable non-secret bucket suffix (not an account ID);
- one full lowercase 40-hex commit SHA used for both image tags and job provenance;
- the SHA-256 digest of the portfolio token (never the plaintext token);
- an active 64-lowercase-hex origin value plus an accepted list containing one or two distinct
  values including the active value;
- the owner-approved Budget/SNS email recipient.

Terraform state is sensitive: it contains the token digest and both origin-header inputs, and after
apply it will reference RDS-managed credentials. State and plans are gitignored, but v0.1 has no
remote-state backend. Keep local state access-restricted and backed up securely; remote encrypted
state/locking is the accepted v0.2 hardening step.

After explicit authorization and only with the intended AWS identity:

```bash
terraform plan -out=portfolio.tfplan
terraform show -no-color portfolio.tfplan
```

The owner must review the exact account/role, region (`eu-west-2`), resource count, budget recipient,
secret inputs and estimated cost before separately authorizing any apply. A plan is not apply
authorization. Never commit the saved plan: it can contain sensitive values.

The provider must fail before planning if the live caller account differs from
`expected_aws_account_id`. Never disable account-ID discovery or remove `allowed_account_ids` to
bypass that stop.

## Fail-closed deployment sequencing boundary

The first reviewed plan and separately authorized apply keep both services at zero. After the exact
commit-SHA images are built and pushed, run the declared one-shot migration task with its dedicated
no-ingress security group and public IP, inspect its stopped-task exit code and migration logs, and
verify the database is at Alembic head. Only then may a second reviewed plan and separately authorized
apply set `api_desired_count = 1`. Verify `/api/readyz` before any smoke test. The exact commands,
failure path and rollback boundary are in `docs/runbooks/g9-portfolio-environment.md`. Until that
sequence passes, the ALB has no API target and the application must not be described as routable.

Origin-header rotation is also staged: `[A]` with active `A` → accepted `[A,B]` while active remains
`A` → active `B` while accepting `[A,B]` → accepted `[B]`. Every value is exact 64-character
lowercase hex; `*`, `?`, whitespace and control characters fail validation, so the ALB condition has
no wildcard semantics. Each transition requires its own reviewed plan/apply and CloudFront
propagation/verification before advancing.

The distribution uses the AWS CloudFront default certificate and intentionally does not claim a
configurable TLS 1.2 minimum. The owner must either accept AWS default-certificate viewer behavior
for this bounded evidence environment or later authorize DNS plus a `us-east-1` ACM certificate.
No DNS or ACM resource is created here.

The committed `run-migration-task.sh` and `verify-api-enablement.sh` scripts are later authorized,
account-pinned verification tools. The first launches and mechanically verifies only the one-shot
migration; the second verifies an already-applied API enablement using ECS stability plus bounded
readiness retries. Neither invokes Terraform plan/apply, changes service counts or mutates state.

The reserved OpenAI secret has no Terraform-managed value. With the default
`enable_g12_openai = false`, neither task receives an OpenAI key reference and the worker execution
role has no permission to read it. The explicit G12 mode derives one shared processing contract for
the API and worker: provider `openai`, a 120-second source limit and one paid attempt (rather than
the fake baseline's provider `fake`, 300-second limit and three attempts). It injects the existing
secret into the worker only and conditionally grants that worker execution role
`secretsmanager:GetSecretValue` for exactly that secret. The API receives provider/limit
configuration but never the key. Add the secret value out-of-band so it never enters Terraform
configuration, plans or state; enabling G12 and running a paid job remain separately reviewable
operations. The worker desired count still defaults to zero and may never exceed one.
