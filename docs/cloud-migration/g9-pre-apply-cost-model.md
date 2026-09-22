# G9 pre-apply cost model — eu-west-2 portfolio evidence environment

**Date:** 2026-08-08
**Status:** planning estimate only; no AWS account, plan, resource or bill was inspected
**Posture:** API and worker disabled for bootstrap; API one only after migration; intended maximum
environment lifetime 72 hours

This is a conservative low-traffic estimate for the exact G9 Terraform shape. It is not an AWS
quote and is not measured billing. The owner must re-check the regional prices and the credentialed
plan immediately before any apply. Free Tier and promotional credits are ignored so they cannot
hide the underlying cost.

## Planning inputs

| Meter | G9 assumption | Approximate planning rate |
|---|---:|---:|
| API Fargate | Linux/x86, 0.25 vCPU, 0.5 GiB, one task | $0.014/hour |
| Worker Fargate compute | Linux/x86, **2 vCPU, 8 GiB**, zero tasks by default | $0.136/task-hour |
| Worker ephemeral storage | 40 GiB provisioned; 20 GiB included, 20 GiB charged | ~$0.0024/task-hour |
| Application Load Balancer | one ALB, two AZs, very low LCU use | $0.029/hour allowance |
| RDS PostgreSQL | db.t4g.micro, single-AZ, 20 GiB gp3 | $0.023/hour including storage allowance |
| Public IPv4 | two ALB addresses plus API task; worker adds one while running | $0.005/address-hour |
| Secrets Manager | portfolio hash, active + accepted origin values, empty OpenAI shell, RDS-managed master secret | $0.003/hour aggregate |
| ECR/S3/CloudFront/SQS/CloudWatch | 3.46 GB local worker-image proxy, small API image, low requests/logs/media | $0.007/hour allowance |

The worker compute rate preserves the accepted G8/G8.2.1 planning figure (about $97.82 for 720
continuous hours). The additional-storage estimate uses a deliberately rounded $0.00012 per
GB-hour planning rate for the charged 20 GiB above Fargate's included 20 GiB; the owner must replace
it with the current `eu-west-2` rate at plan approval. Fargate billing starts while the image is
downloaded, is per second with a one-minute minimum, and therefore includes the large worker-image
pull. The local 3.46 GB compressed-transfer
measurement is only a proxy: ECR layer storage and transfer must be recorded from the eventual
authorized push, never inferred as a remote digest/size fact.

AWS pricing references used for the model: [Fargate](https://aws.amazon.com/fargate/pricing/),
[Application Load Balancing](https://aws.amazon.com/elasticloadbalancing/pricing/),
[RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/pricing/),
[public IPv4](https://aws.amazon.com/vpc/pricing/),
[Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/),
[ECR](https://aws.amazon.com/ecr/pricing/),
[S3](https://aws.amazon.com/s3/pricing/), and
[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/). Regional dynamic tables and taxes can
change; these links must be checked again at the approval point.

## Time-window estimate

The worker-off/API-on base is rounded to **$0.091/hour**. The bootstrap phase with API zero is lower,
but is not used to understate the window. Enabling one worker adds about **$0.1434/hour**: $0.136
compute, $0.005 public IPv4 and approximately $0.0024 for its charged 20 GiB of extra ephemeral
storage.

| Window | Worker off (selected default) | Worker continuously on (warning case) |
|---:|---:|---:|
| 24 hours | **$2.18** | **$5.63** |
| 72 hours | **$6.55** | **$16.88** |
| 7 days / 168 hours | **$15.29** | **$39.38** |

A controlled worker run is added at roughly $0.1434 per task-hour: a 15-minute pull-and-processing
window is about $0.04; one full hour is about $0.14. Of that, extra ephemeral storage is about
$0.0006 for 15 minutes or $0.0024 for one hour. Actual S3/CloudFront egress, log volume, ALB
LCUs, image-pull duration and retries can raise the total. The AWS Budget is fixed at **USD 25**,
but a Budget is delayed monitoring, not a hard spending cap. In the always-on warning case the
seven-day estimate already exceeds it.

## Exclusions and treatment

- Prices are USD estimates **before VAT, tax and currency conversion**. No GBP exchange rate is
  assumed.
- OpenAI/model usage is excluded. G12 requires a separate key, spend approval and measured record.
- The 40-GiB worker allocation is provisional. G11 must measure native Fargate peak usage and free
  space; insufficient storage requires a reviewed increase or narrower public input claim.
- Substantial media egress, abusive traffic, retry storms, manual snapshots, retained object
  versions, retained logs and resources outside Terraform are not included.
- No NAT Gateway, custom DNS, Multi-AZ RDS, autoscaling, dashboard or v0.2 service is included.

## Disable and teardown cost controls

1. Keep `worker_desired_count = 0`; set it to `1` only for an approved bounded G11/G12 window, then
   return it to `0` and confirm the service has zero running tasks.
2. End the environment target window within 72 hours. This is an operations target, not an S3
   deletion guarantee. Application rollback is not teardown: rolling back
   images/frontend leaves ALB, RDS and API meters running.
3. For teardown, follow `docs/runbooks/g9-portfolio-environment.md` and obtain a separate explicit
   destructive approval before `terraform destroy` or deleting bucket/image contents.
4. After destroy, inspect billing/residual resources until the account shows no unexpected ongoing
   meters. A successful command is not by itself zero-cost proof.

S3 lifecycle makes current media versions eligible after three lifecycle days, subject to UTC day
rounding and asynchronous processing. Current expiration in the versioned bucket creates a
delete-marker/noncurrent transition; the separate three-day noncurrent window follows. Teardown
therefore requires separately authorized manual emptying of all versions and delete markers.

Residual-billing checklist: manual/final RDS snapshots and retained automated backups; non-empty ECR
repositories/layers; all current and noncurrent S3 object versions and delete markers; CloudWatch log
groups/exports; Secrets Manager recovery-window secrets; ALB/ENIs/public IPv4 addresses; CloudFront
distribution; SNS subscription; and any future state-storage resources. Local Terraform state does
not incur AWS cost but remains sensitive and must be retained or disposed of securely.
