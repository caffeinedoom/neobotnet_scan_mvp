# ================================================================
# URL-RESOLVER - HTTP PROBING & URL ENRICHMENT
# ================================================================
# URL-Resolver probes discovered URLs and enriches them with:
# - HTTP status codes
# - Content types
# - Response sizes
# - Title extraction
# - Technology detection
#
# Modes:
# - STREAMING_MODE: Consumes from Redis streams (pipeline mode)
# - BACKFILL_MODE: Processes unresolved historical_urls from DB
#
# Resource Allocation:
# - 512 CPU (0.5 vCPU) - HTTP concurrent probing
# - 1024 MB memory - For Go runtime and HTTP response buffering
# - Cost: ~$0.01/run (on-demand Fargate pricing)
#
# Author: Neobotnet Development Team
# Date: 2025-12-28
# ================================================================

# ================================================================
# ECR REPOSITORY
# ================================================================

resource "aws_ecr_repository" "url_resolver" {
  name                 = "${local.name_prefix}-url-resolver"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-url-resolver-ecr"
  })
}

# ================================================================
# ECS TASK DEFINITION
# ================================================================

resource "aws_ecs_task_definition" "url_resolver" {
  family                   = "${local.name_prefix}-url-resolver-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 2048  # HTTP probing needs more CPU (2 vCPU)
  memory                   = 4096  # Go runtime + response buffering for concurrent probes (4GB)
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "url-resolver-scanner"
      image     = "${aws_ecr_repository.url_resolver.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MODULE_TYPE"
          value = "url-resolver"
        },
        {
          name  = "BATCH_MODE"
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
        # URL Resolver configuration
        {
          name  = "CONCURRENCY"
          value = "20"
        },
        {
          name  = "BATCH_SIZE"
          value = "50"
        },
        {
          name  = "TIMEOUT"
          value = "30"
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
        }
      ]

      # Resource limits - let task-level allocation apply (orchestrator overrides these)
      # Removed hardcoded memory/cpu to allow dynamic allocation from scan_module_profiles

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "url-resolver"
        }
      }

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "echo 'URL Resolver ready' || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 30
      }

      # Security
      readonlyRootFilesystem = false
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-url-resolver-task"
  })
}

# ================================================================
# OUTPUTS
# ================================================================

output "url_resolver_ecr_repository_url" {
  description = "URL of the URL-Resolver ECR repository"
  value       = aws_ecr_repository.url_resolver.repository_url
}

output "url_resolver_task_definition_arn" {
  description = "ARN of the URL-Resolver ECS task definition"
  value       = aws_ecs_task_definition.url_resolver.arn
}

output "url_resolver_task_definition_family" {
  description = "Family name of the URL-Resolver task definition"
  value       = aws_ecs_task_definition.url_resolver.family
}

