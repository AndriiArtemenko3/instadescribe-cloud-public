provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.expected_aws_account_id]

  default_tags {
    tags = local.common_tags
  }
}

# The CloudFront origin-facing prefix list is intentionally resolved by AWS
# during the later credentialed plan. `terraform validate` does not call AWS.
data "aws_ec2_managed_prefix_list" "cloudfront_origin_facing" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}
