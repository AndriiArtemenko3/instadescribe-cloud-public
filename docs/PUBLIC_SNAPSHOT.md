# Public snapshot provenance and verification

Prepared on 22 September 2026 for engineering portfolio review.

## Source boundary

- Original project: InstaDescribe / historical InstaScribe naming.
- Exact source tag: `v0.1.0-cloud-core`.
- Exact source commit: `133992307deebdb339786bfbce3bca6714ebd808`.
- Exact source Git tree: `0b1daa6808678d9f19bb73106d5d579388a0ab00`.
- Fresh public history starts at publication; it does not recreate the original
  development chronology. Source attribution, MIT licence and media notices remain.
- No later hardening branch, Next.js spike or current private R&D is included.

Application behaviour, infrastructure and dependency manifests/locks are preserved.
Changes cover README/setup/provenance/release-status documentation and CI configuration.
A two-import reorder in Alembic and explicit Ruff package classification fix a
macOS/Linux import-order discrepancy; no migration logic changed. Historical planning documents
are context, not commitments or completed-feature claims.

## Verification

Fresh local checks on 22 September 2026:

- Root Python suite: 109 passed; Ruff lint and formatting passed.
- Frontend: 194 tests passed; normal and cloud builds passed. ESLint has one
  existing warning and no errors. Vite reports the existing large-bundle warning.
- Worker suite without external services: 189 passed, 29 skipped.
- API suite in GitHub CI with PostgreSQL/LocalStack: **290 passed**; migrations and
  schema drift check passed. This resolves the incomplete local run (140 passed,
  149 skipped and one missing-database failure without services).

The [CI run](https://github.com/AndriiArtemenko3/instadescribe-cloud-public/actions/workflows/ci.yml)
is the authoritative fresh service-backed check. Historical results in release
documents remain labelled historical and are not substituted for fresh checks.

## Public-release scan

Gitleaks scans of the publication tree and fresh history found three documented
local/example placeholders, reviewed as non-secrets; no verified live credentials
were found. No private source history, `.env` file, key file or Terraform state was
included. This is a bounded publication check, not a security certification.

## Deployment status

No infrastructure was deployed or restored for publication. The historical AWS
frontend returned HTTP 200 and readiness returned HTTP 503 on 22 September 2026.
Use the local fixture for review; no current end-to-end cloud availability is claimed.
