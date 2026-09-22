# G9.3 readiness numeric validation evidence

**Date:** 2026-08-08
**Base:** accepted G9.2 commit `4282336f6ed1083c57efc51d84a1cbc2e34792a3`
**Boundary:** local shell validation and deterministic no-network mocks only
**Decision:** credentialed plan, apply, migration and deployment remain **NO-GO**

G9.3 resolves the sole remaining readiness-verifier P3 without rewriting history. The previous
validation accepted an unbounded digit string before comparing it with Bash arithmetic; an extreme
string could overflow. `verify-api-enablement.sh` now performs no arithmetic on either override.
Both must match the complete canonical decimal domain `1`–`60`: one or two digits, no sign,
whitespace, leading zero or zero, and no value above 60.

The deterministic harness adds negative regressions for 200-digit values, plus/minus signs,
whitespace, leading-zero forms, zero and 61 across both overrides, plus a clean boundary pass with
both values at 60. Every invalid value is rejected before mocked Terraform, AWS or curl is invoked.

## Local verification record

| Gate | Result |
|---|---|
| Bash syntax and full deterministic no-network harness | pass; 28 scenarios passed |
| Terraform recursive format/credential-free validate/16 mocked tests/graph | pass; 16 passed, 0 failed; graph exited 0 |
| root pytest | pass; 89 passed |
| diff and secret/account/state/media/handoff scans | pass; no findings in the G9.3 path set |

No AWS credential/profile/account was inspected; no AWS CLI/API, real Terraform plan/apply/state
action, migration, enablement, deployment, push or remote Git action occurred.
