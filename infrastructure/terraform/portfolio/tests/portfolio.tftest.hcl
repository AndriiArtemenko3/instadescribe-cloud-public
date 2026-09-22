mock_provider "aws" {}

override_data {
  target = data.aws_ec2_managed_prefix_list.cloudfront_origin_facing
  values = { id = "pl-12345678" }
}

override_data {
  target = data.aws_iam_policy_document.ecs_tasks_assume
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.api_execution
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.worker_execution
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.migration_execution
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.api_task
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.worker_task
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.frontend_bucket
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

override_data {
  target = data.aws_iam_policy_document.media_bucket
  values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
}

variables {
  expected_aws_account_id       = "123456789012"
  resource_suffix               = "g9local"
  release_commit_sha            = "5fdd210b907d360f141f8c94e0878b8cb0b89f96"
  portfolio_token_sha256        = "0000000000000000000000000000000000000000000000000000000000000000"
  origin_verify_active_value    = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  origin_verify_accepted_values = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
  budget_alert_email            = "alerts@instascribe.test"
  api_desired_count             = 0
  worker_desired_count          = 0
  enable_g12_openai             = false
}

run "bootstrap_services_off" {
  command = plan

  assert {
    condition     = aws_ecs_service.api.desired_count == 0 && aws_ecs_service.worker.desired_count == 0
    error_message = "Bootstrap must leave both ECS services at zero."
  }

  assert {
    condition     = aws_ecs_task_definition.worker.cpu == "2048" && aws_ecs_task_definition.worker.memory == "8192"
    error_message = "The worker must retain the provisional 2-vCPU/8-GiB sizing."
  }

  assert {
    condition     = aws_ecs_task_definition.worker.ephemeral_storage[0].size_in_gib == 40
    error_message = "The worker requires an explicit provisional 40-GiB ephemeral-storage allocation."
  }

  assert {
    condition = (
      local.migration_container_definition.command == [
        "/bin/sh",
        "-c",
        "${local.database_url_shell} alembic -c /srv/alembic.ini upgrade head && exec alembic -c /srv/alembic.ini current --check-heads",
      ] &&
      local.migration_container_definition.essential &&
      strcontains(local.database_url_shell, "from sqlalchemy import URL") &&
      strcontains(local.database_url_shell, "render_as_string(hide_password=False)") &&
      length(local.migration_container_definition.environment) == 3 &&
      local.migration_container_definition.environment[0].name == "DATABASE_HOST" &&
      local.migration_container_definition.environment[1].name == "DATABASE_PORT" &&
      local.migration_container_definition.environment[2].name == "DATABASE_NAME" &&
      length(local.migration_container_definition.secrets) == 2 &&
      local.migration_container_definition.secrets[0].name == "DATABASE_USERNAME" &&
      local.migration_container_definition.secrets[1].name == "DATABASE_PASSWORD" &&
      local.migration_container_definition.logConfiguration.options.awslogs-stream-prefix == "migration" &&
      !contains(keys(local.migration_container_definition), "portMappings")
    )
    error_message = "Migration command, DB environment, RDS-managed secret injection or no-port contract drifted."
  }

  assert {
    condition     = local.container_environment[3].value == var.release_commit_sha
    error_message = "Application job provenance must use the single release commit SHA."
  }

  assert {
    condition = (
      local.api_image_tag == var.release_commit_sha &&
      local.worker_image_tag == var.release_commit_sha &&
      local.migration_image_tag == var.release_commit_sha
    )
    error_message = "API, worker and migration image tags must all derive from the single release commit SHA."
  }

  assert {
    condition     = aws_db_instance.postgres.multi_az == false && aws_db_instance.postgres.publicly_accessible == false
    error_message = "RDS must be single-AZ and private in v0.1."
  }

  assert {
    condition = (
      aws_sqs_queue.work.visibility_timeout_seconds == 1800 &&
      local.processing_job_max_attempts == 3
    )
    error_message = "The queue visibility and retry contracts must remain fixed."
  }

  assert {
    condition = (
      var.enable_g12_openai == false &&
      local.processing_provider == "fake" &&
      local.processing_max_duration_secs == 300 &&
      local.processing_job_max_attempts == 3 &&
      local.container_environment[4] == { name = "INSTASCRIBE_PROVIDER", value = "fake" } &&
      local.container_environment[5] == { name = "INSTASCRIBE_MAX_DURATION_SECS", value = "300" } &&
      local.container_environment[6] == { name = "INSTASCRIBE_MAX_ATTEMPTS", value = "3" } &&
      length(local.worker_openai_secrets) == 0 &&
      length(aws_iam_role_policy.worker_openai_secret) == 0 &&
      !contains([for secret in local.api_runtime_secrets : secret.name], "OPENAI_API_KEY") &&
      !contains([for secret in local.worker_runtime_secrets : secret.name], "OPENAI_API_KEY")
    )
    error_message = "The default fake-provider plan must retain 300 seconds/three attempts and contain no OpenAI injection or permission."
  }

  assert {
    condition     = aws_s3_bucket_versioning.media.versioning_configuration[0].status == "Enabled"
    error_message = "Exact-version source reads require media-bucket versioning."
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.dlq_visible.threshold == 0
    error_message = "The mandatory DLQ alarm must fire when visible messages exceed zero."
  }
}

run "api_enabled_after_migration" {
  command = plan

  variables {
    api_desired_count = 1
  }

  assert {
    condition     = aws_ecs_service.api.desired_count == 1 && aws_ecs_service.worker.desired_count == 0
    error_message = "The second apply may enable exactly one API while the worker remains off."
  }
}

run "g12_openai_worker_only" {
  command = plan

  variables {
    enable_g12_openai = true
  }

  assert {
    condition = (
      local.processing_provider == "openai" &&
      local.processing_max_duration_secs == 120 &&
      local.processing_job_max_attempts == 1 &&
      local.container_environment[4] == { name = "INSTASCRIBE_PROVIDER", value = "openai" } &&
      local.container_environment[5] == { name = "INSTASCRIBE_MAX_DURATION_SECS", value = "120" } &&
      local.container_environment[6] == { name = "INSTASCRIBE_MAX_ATTEMPTS", value = "1" }
    )
    error_message = "G12 must derive provider openai, a 120-second input bound and one paid attempt across the queue/job contract."
  }

  assert {
    condition = (
      length(local.worker_openai_secrets) == 1 &&
      local.worker_openai_secrets[0].name == "OPENAI_API_KEY" &&
      length(local.worker_runtime_secrets) == 3 &&
      !contains([for secret in local.api_runtime_secrets : secret.name], "OPENAI_API_KEY") &&
      contains([for secret in local.worker_runtime_secrets : secret.name], "OPENAI_API_KEY")
    )
    error_message = "G12 must inject the existing OpenAI secret into the worker only; the API must never receive it."
  }

  assert {
    condition = (
      length(aws_iam_role_policy.worker_openai_secret) == 1 &&
      local.worker_openai_secret_statement.Action == ["secretsmanager:GetSecretValue"] &&
      length(local.worker_openai_secret_statement.Resource) == 1
    )
    error_message = "G12 must grant only one worker execution policy with GetSecretValue scoped to one secret."
  }

  assert {
    condition     = aws_ecs_service.worker.desired_count == 0
    error_message = "Enabling the G12 configuration must not start the worker; the separately controlled desired count remains zero by default."
  }
}

run "origin_overlap_active_a" {
  command = plan

  variables {
    origin_verify_accepted_values = [
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]
  }

  assert {
    condition = (
      nonsensitive(var.origin_verify_active_value) == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" &&
      length(nonsensitive(var.origin_verify_accepted_values)) == 2 &&
      nonsensitive(var.origin_verify_accepted_values)[0] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" &&
      nonsensitive(var.origin_verify_accepted_values)[1] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    error_message = "The overlap step must keep CloudFront active A while ALB accepts exact A and B."
  }
}

run "origin_overlap_active_b" {
  command = plan

  variables {
    origin_verify_active_value = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    origin_verify_accepted_values = [
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]
  }

  assert {
    condition     = nonsensitive(var.origin_verify_active_value) == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    error_message = "The cutover step must make B active while ALB still accepts A and B."
  }
}

run "origin_final_b" {
  command = plan

  variables {
    origin_verify_active_value    = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    origin_verify_accepted_values = ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]
  }

  assert {
    condition = (
      length(nonsensitive(var.origin_verify_accepted_values)) == 1 &&
      nonsensitive(var.origin_verify_accepted_values)[0] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    error_message = "The final rotation step must drop A and accept only exact B."
  }
}

run "project_name_maximum" {
  command = plan

  variables {
    project_name = "abcdefghijklmnopqr"
  }

  assert {
    condition     = length(aws_lb.api.name) <= 32 && length(aws_lb_target_group.api.name) <= 32
    error_message = "The maximum accepted project name must keep ALB names within 32 characters."
  }
}

run "reject_api_two" {
  command         = plan
  expect_failures = [var.api_desired_count]

  variables { api_desired_count = 2 }
}

run "reject_worker_two" {
  command         = plan
  expect_failures = [var.worker_desired_count]

  variables { worker_desired_count = 2 }
}

run "reject_project_name_nineteen" {
  command         = plan
  expect_failures = [var.project_name]

  variables { project_name = "abcdefghijklmnopqrs" }
}

run "reject_malformed_expected_aws_account_id" {
  command         = plan
  expect_failures = [var.expected_aws_account_id]

  variables { expected_aws_account_id = "1234-not-an-account" }
}

run "reject_short_release_sha" {
  command         = plan
  expect_failures = [var.release_commit_sha]

  variables { release_commit_sha = "5fdd210" }
}

run "reject_uppercase_release_sha" {
  command         = plan
  expect_failures = [var.release_commit_sha]

  variables { release_commit_sha = "5FDD210B907D360F141F8C94E0878B8CB0B89F96" }
}

run "reject_origin_wildcard" {
  command         = plan
  expect_failures = [var.origin_verify_active_value]

  variables {
    origin_verify_active_value    = "*aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    origin_verify_accepted_values = ["*aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
  }
}

run "reject_origin_whitespace" {
  command         = plan
  expect_failures = [var.origin_verify_active_value]

  variables {
    origin_verify_active_value    = " aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    origin_verify_accepted_values = [" aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
  }
}

run "reject_origin_uppercase" {
  command         = plan
  expect_failures = [var.origin_verify_active_value]

  variables {
    origin_verify_active_value    = "Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    origin_verify_accepted_values = ["Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
  }
}

run "reject_origin_missing_active" {
  command         = plan
  expect_failures = [var.origin_verify_accepted_values]

  variables {
    origin_verify_accepted_values = ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]
  }
}

run "reject_origin_duplicates" {
  command         = plan
  expect_failures = [var.origin_verify_accepted_values]

  variables {
    origin_verify_accepted_values = [
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ]
  }
}

run "reject_three_origin_values" {
  command         = plan
  expect_failures = [var.origin_verify_accepted_values]

  variables {
    origin_verify_accepted_values = [
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    ]
  }
}
