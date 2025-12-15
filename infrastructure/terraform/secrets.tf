# ================================================================
# AWS SSM Parameter Store - Read Existing Secrets
# ================================================================
# Secrets are managed manually in AWS Console (one-time setup)
# Terraform reads them via data sources - no secrets in code/GitHub
# ================================================================

# ================================================================
# DATA SOURCES - Read existing SSM parameters
# ================================================================

data "aws_ssm_parameter" "supabase_url" {
  name = "/${local.name_prefix}/supabase-url"
}

data "aws_ssm_parameter" "supabase_anon_key" {
  name            = "/${local.name_prefix}/supabase-anon-key"
  with_decryption = true
}

data "aws_ssm_parameter" "supabase_service_role_key" {
  name            = "/${local.name_prefix}/supabase-service-role-key"
  with_decryption = true
}

data "aws_ssm_parameter" "jwt_secret_key" {
  name            = "/${local.name_prefix}/jwt-secret-key"
  with_decryption = true
}

# ================================================================
# LOCAL VALUES - Reference secrets throughout Terraform
# ================================================================

locals {
  secrets = {
    supabase_url              = data.aws_ssm_parameter.supabase_url.value
    supabase_anon_key         = data.aws_ssm_parameter.supabase_anon_key.value
    supabase_service_role_key = data.aws_ssm_parameter.supabase_service_role_key.value
    jwt_secret_key            = data.aws_ssm_parameter.jwt_secret_key.value
  }
}

# ================================================================
# IAM Policy for ECS tasks to read SSM parameters
# ================================================================

resource "aws_iam_policy" "ecs_ssm_policy" {
  name        = "${local.name_prefix}-ecs-ssm-policy"
  description = "Policy for ECS tasks to read SSM parameters"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameters",
          "ssm:GetParameter",
          "ssm:GetParametersByPath"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${local.name_prefix}/*"
        ]
      }
    ]
  })

  tags = local.common_tags

  lifecycle {
    ignore_changes = [name, description]
  }
}

# Attach SSM policy to ECS task execution role
resource "aws_iam_role_policy_attachment" "ecs_ssm_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = aws_iam_policy.ecs_ssm_policy.arn
}

# ================================================================
# OUTPUTS - For reference (values are sensitive)
# ================================================================

output "ssm_parameter_prefix" {
  description = "SSM parameter path prefix for this environment"
  value       = "/${local.name_prefix}/"
}
