# ================================================================
# Batch Processing Integration for Existing ECS Infrastructure
# ================================================================
# This file extends the existing ecs-optimized.tf with batch support
# while maintaining full backward compatibility with individual scans

# ================================================================
# Enhanced IAM Permissions for Batch Orchestration
# ================================================================

# Enhanced ECS Task Role Policy for Batch Operations
resource "aws_iam_role_policy" "batch_orchestrator_policy" {
  name = "${local.name_prefix}-batch-orchestrator-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:DescribeTasks",
          "ecs:ListTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:TagResource",
          "ecs:DescribeServices",
          "ecs:ListServices"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeNetworkInterfaces"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution_role.arn,
          aws_iam_role.subfinder_task_role.arn,
          aws_iam_role.ecs_task_role.arn
        ]
      }
    ]
  })
}

# ================================================================
# Enhanced Main Backend App with Batch Support
# ================================================================

# Updated Main App Task Definition with Batch Environment Variables
resource "aws_ecs_task_definition" "app_batch" {
  family                   = "${local.name_prefix}-app-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512  # Increased for batch coordination
  memory                   = 1024 # Increased for batch coordination
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-app"
      image     = "${aws_ecr_repository.backend.repository_url}:latest"
      essential = true

      portMappings = [
        {
          protocol      = "tcp"
          containerPort = var.app_port
          hostPort      = var.app_port
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "DEBUG"
          value = var.environment == "dev" ? "true" : "false"
        },
        {
          name  = "API_V1_STR"
          value = "/api/v1"
        },
        {
          name  = "PROJECT_NAME"
          value = "neobotnet-v2"
        },
        {
          name  = "ALLOWED_ORIGINS"
          value = jsonencode(var.allowed_origins)
        },
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_cluster.redis.cache_nodes[0].address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_cluster.redis.port)
        },
        # ================================================================
        # NEW: Batch Processing Environment Variables
        # ================================================================
        {
          name  = "ECS_CLUSTER_NAME"
          value = aws_ecs_cluster.main.name
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "BATCH_PROCESSING_ENABLED"
          value = "true"
        },
        {
          name  = "SUBFINDER_TASK_DEFINITION"
          value = aws_ecs_task_definition.subfinder_batch.family
        },
        {
          name  = "ECS_SECURITY_GROUP"
          value = aws_security_group.ecs_tasks.id
        },
        {
          name  = "ECS_SUBNETS"
          value = jsonencode(aws_subnet.public[*].id)
        },
        # ================================================================
        # ECS IAM Role ARNs for Batch Container Orchestration
        # ================================================================
        {
          name  = "ECS_TASK_EXECUTION_ROLE_ARN"
          value = aws_iam_role.ecs_task_execution_role.arn
        },
        {
          name  = "ECS_TASK_ROLE_ARN"
          value = aws_iam_role.ecs_task_role.arn
        },
        {
          name  = "ECS_SUBFINDER_TASK_ROLE_ARN"
          value = aws_iam_role.subfinder_task_role.arn
        }
      ]

      secrets = [
        {
          name      = "SUPABASE_URL"
          valueFrom = data.aws_ssm_parameter.supabase_url.arn
        },
        {
          name      = "SUPABASE_ANON_KEY"
          valueFrom = data.aws_ssm_parameter.supabase_anon_key.arn
        },
        {
          name      = "SUPABASE_SERVICE_ROLE_KEY"
          valueFrom = data.aws_ssm_parameter.supabase_service_role_key.arn
        },
        {
          name      = "JWT_SECRET_KEY"
          valueFrom = data.aws_ssm_parameter.jwt_secret_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs-batch"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import requests; requests.get('http://localhost:${var.app_port}/health')\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-app-batch-task"
  })
}

# ================================================================
# Enhanced Subfinder Task Definition for Batch Processing
# ================================================================

resource "aws_ecs_task_definition" "subfinder_batch" {
  family                   = "${local.name_prefix}-subfinder-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256 # Dynamic - will be overridden by batch orchestrator
  memory                   = 512 # Dynamic - will be overridden by batch orchestrator
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.subfinder_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "subfinder"
      image     = "${aws_ecr_repository.subfinder.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_cluster.redis.cache_nodes[0].address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_cluster.redis.cache_nodes[0].port)
        },
        # ================================================================
        # NEW: Batch Processing Support
        # ================================================================
        {
          name  = "BATCH_MODE"
          value = "true"
        },
        {
          name  = "MODULE_TYPE"
          value = "subfinder"
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

      # Dynamic resource allocation - will be overridden at runtime
      memory = 480
      cpu    = 256

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "subfinder-batch"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "echo 'Batch container ready' || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 30
      }

      readonlyRootFilesystem = false
      user                   = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-subfinder-batch-task"
  })
}

# ================================================================
# Cloud SSL Analyzer removed - module no longer used
# ================================================================

# ================================================================
# Batch Processing Service (Updated from original)
# ================================================================

# Update the main ECS service to use the batch-enabled task definition
resource "aws_ecs_service" "main_batch" {
  name            = "${local.name_prefix}-service-batch"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app_batch.arn
  desired_count   = var.app_count
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = aws_subnet.public[*].id
    assign_public_ip = true # Still needed for outbound connections (Supabase, Redis)
  }

  # ============================================================
  # ALB Integration (NEW)
  # ============================================================
  # Registers ECS tasks with the ALB target group
  # ALB performs health checks and routes traffic to healthy tasks only

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "${local.name_prefix}-app" # Must match task definition
    container_port   = var.app_port
  }

  # Health check grace period
  # ECS waits this long after task start before performing health checks
  # Gives the application time to boot up and become ready
  health_check_grace_period_seconds = 60

  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution_role,
    aws_iam_role_policy.batch_orchestrator_policy,
    aws_lb_listener.http # Wait for ALB listener to be ready
  ]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-batch-service"
  })
}

# ================================================================
# Output Updates for Batch Processing
# ================================================================

output "batch_orchestrator_service_name" {
  description = "Name of the batch-enabled ECS service"
  value       = aws_ecs_service.main_batch.name
}

output "subfinder_batch_task_definition" {
  description = "ARN of the batch-enabled subfinder task definition"
  value       = aws_ecs_task_definition.subfinder_batch.arn
}

# Cloud SSL batch task definition output removed - module no longer used
