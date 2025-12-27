# ================================================================
# WAYMORE - HISTORICAL URL DISCOVERY
# ================================================================
# Waymore discovers historical URLs from:
# - Wayback Machine (archive.org)
# - Common Crawl
# - Alien Vault OTX
# - URLScan.io
# - VirusTotal
#
# Architecture:
# - Parallel producer with Subfinder (both take apex domains)
# - Outputs to Redis Stream for URL Resolver consumption
# - Stores to historical_urls table
#
# Resource Allocation:
# - 512 CPU (0.5 vCPU) - I/O bound (archive API calls)
# - 1024 MB memory - For Python/Go runtime and response buffering
# - Cost: ~$0.01/run (on-demand Fargate pricing)
#
# Author: Neobotnet Development Team
# Date: 2025-12-22
# ================================================================

# ================================================================
# ECR REPOSITORY
# ================================================================

resource "aws_ecr_repository" "waymore" {
  name                 = "${local.name_prefix}-waymore"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-waymore-ecr"
  })
}

# ================================================================
# ECS TASK DEFINITION
# ================================================================

resource "aws_ecs_task_definition" "waymore" {
  family                   = "${local.name_prefix}-waymore-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512   # Archive API calls + Python runtime
  memory                   = 1024  # Python + Go + response buffering
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "waymore-scanner"
      image     = "${aws_ecr_repository.waymore.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MODULE_TYPE"
          value = "waymore"
        },
        {
          name  = "BATCH_MODE"
          value = "true"
        },
        {
          name  = "STREAMING_MODE"
          value = "true"
        },
        {
          name  = "LOG_LEVEL"
          value = "info"
        },
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_cluster.redis.cache_nodes[0].address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_cluster.redis.cache_nodes[0].port)
        },
        # Waymore configuration
        {
          name  = "WAYMORE_LIMIT"
          value = "5000"
        },
        {
          name  = "WAYMORE_TIMEOUT"
          value = "600"
        },
        {
          name  = "WAYMORE_CONFIG"
          value = "/app/config.yml"
        }
      ]

      secrets = [
        {
          name      = "SUPABASE_URL"
          valueFrom = data.aws_ssm_parameter.supabase_url.arn
        },
        {
          name      = "SUPABASE_SERVICE_ROLE_KEY"
          valueFrom = data.aws_ssm_parameter.supabase_service_role_key.arn
        },
        # API keys for enhanced coverage (optional - will use empty string if not set)
        {
          name      = "URLSCAN_API_KEY"
          valueFrom = data.aws_ssm_parameter.urlscan_api_key.arn
        },
        {
          name      = "VIRUSTOTAL_API_KEY"
          valueFrom = data.aws_ssm_parameter.waymore_virustotal_api_key.arn
        },
        {
          name      = "ALIENVAULT_API_KEY"
          valueFrom = data.aws_ssm_parameter.alienvault_api_key.arn
        }
      ]

      # Resource limits (container memory < task memory)
      memory = 960
      cpu    = 512

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "waymore"
        }
      }

      # Health check - waymore is installed and accessible
      healthCheck = {
        command     = ["CMD-SHELL", "waymore --version || exit 1"]
        interval    = 30
        timeout     = 15
        retries     = 3
        startPeriod = 30
      }

      # Security
      readonlyRootFilesystem = false
      user                  = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-waymore-task"
  })
}

# ================================================================
# OUTPUTS
# ================================================================

output "waymore_ecr_repository_url" {
  description = "URL of the Waymore ECR repository"
  value       = aws_ecr_repository.waymore.repository_url
}

output "waymore_task_definition_arn" {
  description = "ARN of the Waymore ECS task definition"
  value       = aws_ecs_task_definition.waymore.arn
}

output "waymore_task_definition_family" {
  description = "Family name of the Waymore task definition"
  value       = aws_ecs_task_definition.waymore.family
}

