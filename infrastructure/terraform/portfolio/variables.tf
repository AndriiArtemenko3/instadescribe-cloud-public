variable "aws_region" {
  description = "Fixed v0.1 portfolio region."
  type        = string
  default     = "eu-west-2"

  validation {
    condition     = var.aws_region == "eu-west-2"
    error_message = "The accepted v0.1 plan fixes the portfolio environment in eu-west-2."
  }
}

variable "expected_aws_account_id" {
  description = "Owner-approved AWS account ID used by the provider's fail-closed account allowlist."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_aws_account_id))
    error_message = "expected_aws_account_id must be exactly 12 decimal digits."
  }
}

variable "availability_zones" {
  description = "Two eu-west-2 AZs used for public ECS/ALB and isolated RDS subnets."
  type        = list(string)
  default     = ["eu-west-2a", "eu-west-2b"]

  validation {
    condition = (
      length(var.availability_zones) == 2 &&
      length(distinct(var.availability_zones)) == 2 &&
      alltrue([for az in var.availability_zones : startswith(az, "eu-west-2")])
    )
    error_message = "Provide exactly two distinct eu-west-2 availability zones."
  }
}

variable "project_name" {
  description = "Short resource-name prefix."
  type        = string
  default     = "instascribe"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,17}$", var.project_name))
    error_message = "project_name must be 3-18 lowercase letters, digits or hyphens so generated AWS names remain valid."
  }
}

variable "resource_suffix" {
  description = "Owner-selected stable lowercase suffix used to make S3 bucket names globally unique."
  type        = string

  validation {
    condition = (
      can(regex("^[a-z0-9]{6,12}$", var.resource_suffix)) &&
      !can(regex("(?i)(example|replace|change)", var.resource_suffix))
    )
    error_message = "Use a stable 6-12 character lowercase alphanumeric suffix, not a placeholder."
  }
}

variable "environment" {
  description = "The one explicit v0.1 environment."
  type        = string
  default     = "portfolio"

  validation {
    condition     = var.environment == "portfolio"
    error_message = "G9 defines only the single portfolio environment."
  }
}

variable "vpc_cidr" {
  description = "Portfolio VPC CIDR."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Two public subnet CIDRs for the ALB and public-IP ECS tasks."
  type        = list(string)
  default     = ["10.42.0.0/24", "10.42.1.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDRs are required."
  }
}

variable "database_subnet_cidrs" {
  description = "Two isolated subnet CIDRs for the single-AZ RDS subnet group."
  type        = list(string)
  default     = ["10.42.10.0/24", "10.42.11.0/24"]

  validation {
    condition     = length(var.database_subnet_cidrs) == 2
    error_message = "Exactly two isolated database subnet CIDRs are required."
  }
}

variable "release_commit_sha" {
  description = "One full lowercase Git commit SHA used for both image tags and application provenance."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.release_commit_sha))
    error_message = "release_commit_sha must be exactly one full 40-character lowercase hexadecimal Git SHA."
  }
}

variable "portfolio_token_sha256" {
  description = "SHA-256 hex digest of the owner-supplied portfolio token; never the plaintext token."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9a-fA-F]{64}$", var.portfolio_token_sha256))
    error_message = "portfolio_token_sha256 must be exactly 64 hexadecimal characters."
  }
}

variable "origin_verify_active_value" {
  description = "Active CloudFront-to-ALB origin-verification value: exactly 64 lowercase hex characters."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.origin_verify_active_value))
    error_message = "origin_verify_active_value must be exactly 64 lowercase hexadecimal characters; whitespace, control characters and ALB wildcards are rejected."
  }
}

variable "origin_verify_accepted_values" {
  description = "One or two distinct ALB-accepted origin values; must contain the active CloudFront value during rotation."
  type        = list(string)
  sensitive   = true

  validation {
    condition = (
      contains([1, 2], length(var.origin_verify_accepted_values)) &&
      length(distinct(var.origin_verify_accepted_values)) == length(var.origin_verify_accepted_values) &&
      alltrue([for value in var.origin_verify_accepted_values : can(regex("^[0-9a-f]{64}$", value))]) &&
      contains(var.origin_verify_accepted_values, var.origin_verify_active_value)
    )
    error_message = "origin_verify_accepted_values must contain one or two distinct 64-character lowercase hex values and include origin_verify_active_value."
  }
}

variable "budget_alert_email" {
  description = "Required owner-approved recipient for the USD 25 AWS Budget alert."
  type        = string

  validation {
    condition = (
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.budget_alert_email)) &&
      !can(regex("(?i)(example\\.|invalid|replace|placeholder)", var.budget_alert_email))
    )
    error_message = "Provide the real approved alert recipient; placeholders are rejected."
  }
}

variable "budget_limit_usd" {
  description = "Owner-selected planning budget threshold in USD."
  type        = number
  default     = 25

  validation {
    condition     = var.budget_limit_usd == 25
    error_message = "The selected G9 planning threshold is USD 25."
  }
}

variable "api_desired_count" {
  description = "API is off for bootstrap/migration; set to one only in the separately reviewed enablement apply."
  type        = number
  default     = 0

  validation {
    condition     = contains([0, 1], var.api_desired_count)
    error_message = "api_desired_count must be 0 or 1; bootstrap defaults to zero and v0.1 never exceeds one API task."
  }
}

variable "worker_desired_count" {
  description = "Worker is off by default; set to 1 only for controlled G11/G12 tests."
  type        = number
  default     = 0

  validation {
    condition     = contains([0, 1], var.worker_desired_count)
    error_message = "worker_desired_count must be 0 or 1; v0.1 never exceeds one worker."
  }
}

variable "enable_g12_openai" {
  description = "Explicit owner-controlled G12 switch: configure both application services for OpenAI while keeping the API key worker-only."
  type        = bool
  default     = false
}

variable "database_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "instascribe"
}

variable "database_username" {
  description = "RDS master username; RDS generates and manages its password."
  type        = string
  default     = "instascribe_admin"
}

variable "media_lifecycle_days" {
  description = "S3 current-version expiration eligibility and subsequent noncurrent-version window; not a deletion guarantee."
  type        = number
  default     = 3

  validation {
    condition     = var.media_lifecycle_days == 3
    error_message = "The selected evidence environment uses a 3-day S3 lifecycle eligibility interval."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the ephemeral evidence environment."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Additional non-secret tags."
  type        = map(string)
  default     = {}
}
