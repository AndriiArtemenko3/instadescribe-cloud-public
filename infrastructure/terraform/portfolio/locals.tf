locals {
  name = "${var.project_name}-${var.environment}"

  # One opt-in switch derives the complete server-authoritative processing
  # contract. The G12 real-provider run is intentionally shorter and has no
  # automatic paid retry; the fake evidence path retains its accepted limits.
  processing_provider          = var.enable_g12_openai ? "openai" : "fake"
  processing_max_duration_secs = var.enable_g12_openai ? 120 : 300
  processing_job_max_attempts  = var.enable_g12_openai ? 1 : 3

  # All deployment tags derive from this one fail-closed provenance input.
  api_image_tag       = var.release_commit_sha
  worker_image_tag    = var.release_commit_sha
  migration_image_tag = var.release_commit_sha

  common_tags = merge(
    {
      Project     = "InstaScribe"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Release     = "v0.1-cloud-core"
      CostPosture = "ephemeral-72h-worker-off"
    },
    var.tags,
  )

  container_environment = [
    { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    { name = "INSTASCRIBE_MEDIA_BUCKET", value = aws_s3_bucket.media.bucket },
    { name = "INSTASCRIBE_WORK_QUEUE_URL", value = aws_sqs_queue.work.url },
    { name = "INSTASCRIBE_PIPELINE_REVISION", value = var.release_commit_sha },
    { name = "INSTASCRIBE_PROVIDER", value = local.processing_provider },
    { name = "INSTASCRIBE_MAX_DURATION_SECS", value = tostring(local.processing_max_duration_secs) },
    { name = "INSTASCRIBE_MAX_ATTEMPTS", value = tostring(local.processing_job_max_attempts) },
    { name = "DATABASE_HOST", value = aws_db_instance.postgres.address },
    { name = "DATABASE_PORT", value = tostring(aws_db_instance.postgres.port) },
    { name = "DATABASE_NAME", value = var.database_name },
  ]

  database_secrets = [
    {
      name      = "DATABASE_USERNAME"
      valueFrom = "${aws_db_instance.postgres.master_user_secret[0].secret_arn}:username::"
    },
    {
      name      = "DATABASE_PASSWORD"
      valueFrom = "${aws_db_instance.postgres.master_user_secret[0].secret_arn}:password::"
    },
  ]

  # The OpenAI value is deliberately absent from Terraform and its state. G12
  # adds a value out-of-band to the pre-existing secret shell. Only the worker
  # task receives that secret reference; the API receives processing config,
  # never provider credentials.
  worker_openai_secrets = var.enable_g12_openai ? [
    {
      name      = "OPENAI_API_KEY"
      valueFrom = aws_secretsmanager_secret.openai_api_key.arn
    },
  ] : []

  api_runtime_secrets = concat(local.database_secrets, [
    {
      name      = "PORTFOLIO_TOKEN_SHA256"
      valueFrom = aws_secretsmanager_secret.portfolio_token_hash.arn
    },
  ])
  worker_runtime_secrets = concat(local.database_secrets, local.worker_openai_secrets)

  worker_openai_secret_statement = {
    Sid      = "ReadOpenAIKeyForWorkerOnly"
    Effect   = "Allow"
    Action   = ["secretsmanager:GetSecretValue"]
    Resource = [aws_secretsmanager_secret.openai_api_key.arn]
  }
  worker_openai_secret_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [local.worker_openai_secret_statement]
  })

  # Build the SQLAlchemy URL without ever placing a raw generated password in
  # a URI template. RDS-managed passwords may contain reserved URI characters;
  # URL.create performs the required escaping and the shell quotes the result.
  database_url_shell = "export DATABASE_URL=\"$(python -c 'import os; from sqlalchemy import URL; print(URL.create(\"postgresql+psycopg\", username=os.environ[\"DATABASE_USERNAME\"], password=os.environ[\"DATABASE_PASSWORD\"], host=os.environ[\"DATABASE_HOST\"], port=int(os.environ[\"DATABASE_PORT\"]), database=os.environ[\"DATABASE_NAME\"]).render_as_string(hide_password=False))')\";"

  migration_environment = [
    { name = "DATABASE_HOST", value = aws_db_instance.postgres.address },
    { name = "DATABASE_PORT", value = tostring(aws_db_instance.postgres.port) },
    { name = "DATABASE_NAME", value = var.database_name },
  ]

  migration_container_definition = {
    name      = "migration"
    image     = "${aws_ecr_repository.api.repository_url}:${local.migration_image_tag}"
    essential = true
    command = [
      "/bin/sh",
      "-c",
      "${local.database_url_shell} alembic -c /srv/alembic.ini upgrade head && exec alembic -c /srv/alembic.ini current --check-heads",
    ]
    environment = local.migration_environment
    secrets     = local.database_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.migration.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "migration"
      }
    }
    readonlyRootFilesystem = false
    user                   = "10001"
  }
}
