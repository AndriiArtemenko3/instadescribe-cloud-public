output "application_url" {
  description = "CloudFront URL for the Vite app and same-origin /api/* calls."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "api_health_url" {
  description = "Public health alias routed through CloudFront to the protected ALB origin."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}/api/healthz"
}

output "api_ready_url" {
  description = "Public readiness alias; verifies configuration and the database."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}/api/readyz"
}

output "api_ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "worker_ecr_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "media_bucket" {
  value = aws_s3_bucket.media.bucket
}

output "work_queue_url" {
  value = aws_sqs_queue.work.url
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "rds_master_secret_arn" {
  value     = aws_db_instance.postgres.master_user_secret[0].secret_arn
  sensitive = true
}

output "portfolio_token_secret_arn" {
  value = aws_secretsmanager_secret.portfolio_token_hash.arn
}

output "openai_api_key_secret_arn" {
  description = "OpenAI secret shell; any value/version is managed out-of-band and never by Terraform."
  value       = aws_secretsmanager_secret.openai_api_key.arn
}

output "release_commit_sha" {
  description = "Single immutable provenance value used for API and worker image tags and job revision stamping."
  value       = var.release_commit_sha
}

output "ecs_cluster_name" {
  description = "Cluster used by the separately authorized one-shot migration run."
  value       = aws_ecs_cluster.this.name
}

output "migration_task_definition_arn" {
  description = "Immutable API-image Alembic task definition; run it before enabling the API service."
  value       = aws_ecs_task_definition.migration.arn
}

output "migration_log_group" {
  value = aws_cloudwatch_log_group.migration.name
}

output "migration_network_configuration" {
  description = "Inputs for ecs run-task; the migration has no inbound rule and needs a public IP for ECR/log/secret access."
  value = {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.migration.id]
    assign_public_ip = "ENABLED"
  }
}

output "api_desired_count" {
  description = "Zero during bootstrap/migration; one only after a successful migration and a separately reviewed apply."
  value       = aws_ecs_service.api.desired_count
}

output "api_service_name" {
  description = "ECS service verified after the separately authorized API enablement apply."
  value       = aws_ecs_service.api.name
}

output "worker_desired_count" {
  description = "Should remain zero except during a controlled G11/G12 test."
  value       = aws_ecs_service.worker.desired_count
}

output "processing_contract" {
  description = "Non-secret server-authoritative provider, source-duration limit and paid-attempt bound derived from the G12 switch."
  value = {
    provider          = local.processing_provider
    max_duration_secs = local.processing_max_duration_secs
    max_attempts      = local.processing_job_max_attempts
  }
}
