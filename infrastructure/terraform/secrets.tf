# SSM Parameter for Supabase URL
resource "aws_ssm_parameter" "supabase_url" {
  name      = "/${local.name_prefix}/supabase-url"
  type      = "SecureString"
  value     = var.supabase_url
  overwrite = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-supabase-url"
  })
}

# SSM Parameter for Supabase Anonymous Key
resource "aws_ssm_parameter" "supabase_anon_key" {
  name      = "/${local.name_prefix}/supabase-anon-key"
  type      = "SecureString"
  value     = var.supabase_anon_key
  overwrite = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-supabase-anon-key"
  })
}

# SSM Parameter for Supabase Service Role Key
resource "aws_ssm_parameter" "supabase_service_role_key" {
  name      = "/${local.name_prefix}/supabase-service-role-key"
  type      = "SecureString"
  value     = var.supabase_service_role_key
  overwrite = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-supabase-service-role-key"
  })
}

# SSM Parameter for JWT Secret Key
resource "aws_ssm_parameter" "jwt_secret_key" {
  name      = "/${local.name_prefix}/jwt-secret-key"
  type      = "SecureString"
  value     = var.jwt_secret_key
  overwrite = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-jwt-secret-key"
  })
}

# IAM Policy for ECS tasks to read SSM parameters
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
          aws_ssm_parameter.supabase_url.arn,
          aws_ssm_parameter.supabase_anon_key.arn,
          aws_ssm_parameter.supabase_service_role_key.arn,
          aws_ssm_parameter.jwt_secret_key.arn
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