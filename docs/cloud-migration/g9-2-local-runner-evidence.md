# G9.2 fail-closed runner correction evidence

> Historical G9.2 record. G9.3 removes Bash arithmetic from readiness override validation and
> restricts both values to canonical decimal `1`–`60`. See
> `g9-3-readiness-numeric-evidence.md`; credentialed execution remains NO-GO.

**Date:** 2026-08-08
**Base:** accepted G9.1 commit `a3dea2cd42259385e8c0dba19911fef1668f1116`
**Boundary:** local shell code, deterministic mocks and credential-free Terraform validation only
**Decision:** credentialed plan, apply, migration and deployment remain **NO-GO**

G9.2 removes the remaining manual-inspection gap without rewriting accepted commits. No AWS
credential/profile/account was inspected; no AWS CLI/API, real Terraform plan/apply/state action,
ECR push, migration, service enablement, deployment or remote Git action occurred.

## Mechanical migration gate

`infrastructure/terraform/portfolio/scripts/run-migration-task.sh` uses `set -euo pipefail` and:

- requires an explicit `EXPECTED_AWS_ACCOUNT_ID` of exactly 12 digits, calls STS only when later
  authorized, and stops before RunTask on mismatch;
- requires Terraform outputs API=0 and worker=0;
- converts the Terraform network output to the exact ECS JSON shape with `jq`;
- requires zero RunTask failures, exactly one task and one nonempty/non-`None` ARN;
- waits for stop, then requires zero DescribeTasks failures, exactly one stopped task, exactly one
  stopped `migration` container and a present numeric exit code exactly zero;
- relies on the registered `alembic upgrade head && alembic current --check-heads` chain, so exit
  zero mechanically proves both commands, then tails only the dedicated migration log group;
- ends after verification and contains no plan/apply/state/API-enable path.

## Post-enable verification gate

`verify-api-enablement.sh` is invoked only after a separately reviewed and authorized API-enable
apply. It requires API=1/worker=0 plus the expected account, waits for ECS `services-stable`, then
performs at most 12 HTTPS readiness attempts at 10-second intervals. A delayed success passes;
waiter failure or terminal timeout fails. It cannot apply, enable or alter state.

The database security-group description now accurately names API, worker and migration access.

## Local verification record

The final values below are recorded only after the complete gate passes:

| Gate | Result |
|---|---|
| `bash -n` for runners, harness and mock executables | passed |
| deterministic no-network script harness | **13 scenarios passed** |
| Terraform recursive format check and credential-free validate | passed |
| existing mocked `terraform test -no-color` | **16 passed, 0 failed** |
| `terraform graph -type=plan -draw-cycles` | passed; exit 0 |
| `uv run --with-requirements requirements-dev.txt pytest -q` | **89 passed** |
| diff and secret/account/state/media/handoff scans | passed; owner handoffs never staged |

Mock cases cover service-nonzero preflight, wrong account, RunTask command/response failures, empty
task list, `None` ARN, missing/nonzero exit, unexpected stopped state, clean migration success,
delayed readiness success, readiness timeout and ECS service-waiter failure. Every failure asserts
that the next operation is absent; all cases reject Terraform plan/apply and cross-boundary API
enablement.

G9.2 does not reduce D1/D2, R19, R20/D8, sensitive-input, separate-plan/apply or deployment approval
requirements recorded by G9.1.
