# ================================================================
# COST-OPTIMIZED ECS CONFIGURATION
# ================================================================
# This configuration right-sizes containers for development workloads
# Target: Reduce monthly costs from $116 to $18-25
# ================================================================

# ================================================================
# ECR Repository for Main Backend Application
# ================================================================
# NOTE: This repository already exists (created outside Terraform)
# Using data source to reference it instead of creating new
data "aws_ecr_repository" "backend" {
  name = "neobotnet-backend"
}

# ECS Cluster (unchanged - this is fine)
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs.name
      }
    }
  }

  tags = local.common_tags
}

# CloudWatch Log Group (unchanged)
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/aws/ecs/${local.name_prefix}"
  retention_in_days = 7

  tags = local.common_tags

  lifecycle {
    ignore_changes = [name]
  }
}

# ECS Task Execution Role (unchanged)
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${local.name_prefix}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role (unchanged)
resource "aws_iam_role" "ecs_task_role" {
  name = "${local.name_prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# IAM policy for ECS task role to run tasks
resource "aws_iam_role_policy" "ecs_task_role_policy" {
  name = "${local.name_prefix}-ecs-task-role-policy"
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
          "ecs:TagResource"
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
          aws_iam_role.subfinder_task_role.arn
        ]
      }
    ]
  })
}

# ================================================================
# MAIN BACKEND APPLICATION - RIGHT-SIZED
# ================================================================
# BEFORE: 512 CPU (0.5 vCPU) + 1024 memory (1GB) = ~$18/month
# AFTER:  256 CPU (0.25 vCPU) + 512 memory (512MB) = ~$9/month
# SAVINGS: $9/month (50% reduction)
# Legacy task definition removed - using batch processing task definition instead

# Legacy ECS Service removed - using batch processing service instead

# ================================================================
# SUBFINDER SCANNER - RIGHT-SIZED FOR DNS ENUMERATION
# ================================================================
# BEFORE: 512 CPU + 1024 memory = ~$15/month if running continuously
# AFTER:  256 CPU + 512 memory = ~$7/month (per-task cost: $0.004/run)
# SAVINGS: $8/month + much lower per-execution cost

# ECR Repository for Subfinder Scanner
resource "aws_ecr_repository" "subfinder" {
  name                 = "${local.name_prefix}-subfinder"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-subfinder-ecr"
  })
}

# Subfinder ECS Task Definition - OPTIMIZED
resource "aws_ecs_task_definition" "subfinder" {
  family                   = "${local.name_prefix}-subfinder"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256   # OPTIMIZED: 0.25 vCPU (was 512)
  memory                   = 512   # OPTIMIZED: 512 MB (was 1024)
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

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
        }
      ]

      # Resource limits - OPTIMIZED (container memory < task memory for ECS overhead)
      memory = 480  # FIXED: Must be less than task memory (512 MB) 
      cpu    = 256  # REDUCED from 512

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "subfinder"
        }
      }

      # Optimized health check
      healthCheck = {
        command     = ["CMD-SHELL", "python3 -c \"import redis; r=redis.Redis(host='${aws_elasticache_cluster.redis.cache_nodes[0].address}', port=6379); r.ping()\" || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 30
      }

      # Security
      readonlyRootFilesystem = false
      user                  = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-subfinder-task"
  })
}

# ================================================================
# DNSX DNS RESOLVER - OPTIMIZED FOR DNS QUERIES
# ================================================================
# DNS resolution is I/O bound, minimal CPU required
# Optimized for batch processing of discovered subdomains
# Cost: ~$3/month (per-task cost: $0.003/run)

# ECR Repository for DNSX Scanner
resource "aws_ecr_repository" "dnsx" {
  name                 = "${local.name_prefix}-dnsx"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-dnsx-ecr"
  })
}

# DNSX ECS Task Definition - OPTIMIZED
resource "aws_ecs_task_definition" "dnsx" {
  family                   = "${local.name_prefix}-dnsx-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256   # I/O bound, minimal CPU
  memory                   = 512   # Minimal memory for DNS queries
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "dnsx-scanner"
      image     = "${aws_ecr_repository.dnsx.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MODULE_TYPE"
          value = "dnsx"
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
          name  = "HEALTH_CHECK_ENABLED"
          value = "true"
        },
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_cluster.redis.cache_nodes[0].address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_cluster.redis.cache_nodes[0].port)
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

      # Resource limits - OPTIMIZED (container memory < task memory)
      memory = 480  # Container memory < task memory (512 MB)
      cpu    = 256

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "dnsx"
        }
      }

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "/app/health-check.sh || exit 1"]
        interval    = 30
        timeout     = 15
        retries     = 3
        startPeriod = 10
      }

      # Security
      readonlyRootFilesystem = false
      user                  = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-dnsx-task"
  })
}

# ================================================================
# HTTPx - HTTP PROBING FOR DISCOVERED SUBDOMAINS
# ================================================================
# HTTPx is optimized for HTTP probing workloads:
# - 512 CPU (0.5 vCPU) for HTTP request handling
# - 1024 MB memory for response buffering and tech detection
# - Consumes from Redis Stream (subfinder output)
# - Produces to http_probes table

resource "aws_ecr_repository" "httpx" {
  name                 = "${local.name_prefix}-httpx"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-httpx-ecr"
  })
}

# HTTPx ECS Task Definition - OPTIMIZED
resource "aws_ecs_task_definition" "httpx" {
  family                   = "${local.name_prefix}-httpx-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512   # HTTP probing with tech detection
  memory                   = 1024  # Response buffering + tech detection
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "httpx-scanner"
      image     = "${aws_ecr_repository.httpx.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MODULE_TYPE"
          value = "httpx"
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
          name  = "HEALTH_CHECK_ENABLED"
          value = "true"
        },
        {
          name  = "REDIS_HOST"
          value = aws_elasticache_cluster.redis.cache_nodes[0].address
        },
        {
          name  = "REDIS_PORT"
          value = tostring(aws_elasticache_cluster.redis.cache_nodes[0].port)
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

      # Resource limits - OPTIMIZED (container memory < task memory)
      memory = 960  # Container memory < task memory (1024 MB)
      cpu    = 512

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "httpx"
        }
      }

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "/app/health-check.sh || exit 1"]
        interval    = 30
        timeout     = 15
        retries     = 3
        startPeriod = 10
      }

      # Security
      readonlyRootFilesystem = false
      user                  = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-httpx-task"
  })
}

# ================================================================
# KATANA WEB CRAWLER - CRAWLS DISCOVERED ENDPOINTS
# ================================================================
# Katana crawls web pages discovered by HTTPx:
# - 512 CPU (0.5 vCPU) for web crawling and parsing
# - 1024 MB memory for page content and JS rendering
# - Reads from http_probes table
# - Writes to crawled_endpoints table
# Cost: ~$0.01/run (on-demand Fargate pricing)

resource "aws_ecr_repository" "katana" {
  name                 = "${local.name_prefix}-katana"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-katana-ecr"
  })
}

# Katana ECS Task Definition
resource "aws_ecs_task_definition" "katana" {
  family                   = "${local.name_prefix}-katana-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512   # Web crawling with JS parsing
  memory                   = 1024  # Page content buffering
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "katana-scanner"
      image     = "${aws_ecr_repository.katana.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MODULE_TYPE"
          value = "katana"
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

      # Resource limits (container memory < task memory)
      memory = 960
      cpu    = 512

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "katana"
        }
      }

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "echo 'Katana ready' || exit 1"]
        interval    = 30
        timeout     = 15
        retries     = 3
        startPeriod = 10
      }

      # Security
      readonlyRootFilesystem = false
      user                  = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-katana-task"
  })
}

# IAM Role for Subfinder Tasks (unchanged)
resource "aws_iam_role" "subfinder_task_role" {
  name = "${local.name_prefix}-subfinder-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# ================================================================
# COST MONITORING AND ALERTS - NEW!
# ================================================================

# Note: Cost monitoring resources removed due to AWS provider version compatibility
# TODO: Re-add cost monitoring when upgrading to AWS provider >= 5.30
# For now, monitor costs through AWS Console Cost Explorer

# ================================================================
# ORCHESTRATOR - CLI-TRIGGERED SCAN PIPELINE
# ================================================================
# The orchestrator runs inside the VPC and coordinates the scan pipeline:
# - Receives program/domains from CLI via ECS task override
# - Orchestrates Subfinder -> DNSx + HTTPx (parallel) -> Katana
# - Has Redis access for streaming coordination
# - Uses existing scan_pipeline.py code
#
# Resource allocation:
# - 512 CPU (0.5 vCPU) for orchestration logic
# - 1024 MB memory for pipeline coordination
# - Cost: ~$0.01 per scan execution

resource "aws_ecr_repository" "orchestrator" {
  name                 = "${local.name_prefix}-orchestrator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-orchestrator-ecr"
  })
}

resource "aws_ecs_task_definition" "orchestrator" {
  family                   = "${local.name_prefix}-orchestrator"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512   # Orchestration logic
  memory                   = 1024  # Pipeline coordination
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "orchestrator"
      image     = "${aws_ecr_repository.orchestrator.repository_url}:latest"
      essential = true

      environment = [
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
        {
          name  = "ECS_CLUSTER"
          value = aws_ecs_cluster.main.name
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        # Scan module task ARNs for orchestration
        {
          name  = "SUBFINDER_TASK_DEFINITION"
          value = aws_ecs_task_definition.subfinder.arn
        },
        {
          name  = "DNSX_TASK_DEFINITION"
          value = aws_ecs_task_definition.dnsx.arn
        },
        {
          name  = "HTTPX_TASK_DEFINITION"
          value = aws_ecs_task_definition.httpx.arn
        },
        {
          name  = "KATANA_TASK_DEFINITION"
          value = aws_ecs_task_definition.katana.arn
        },
        {
          name  = "TYVT_TASK_DEFINITION"
          value = aws_ecs_task_definition.tyvt.arn
        },
        {
          name  = "WAYMORE_TASK_DEFINITION"
          value = aws_ecs_task_definition.waymore.arn
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

      # Resource limits
      memory = 960  # Container memory < task memory
      cpu    = 512

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "orchestrator"
        }
      }

      # No health check - this is a one-shot task, not a service
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-orchestrator-task"
  })
}

# ================================================================
# TYVT - VIRUSTOTAL DOMAIN SCANNER
# ================================================================
# TYVT queries VirusTotal for each subdomain to discover historical URLs.
# - Consumes from HTTPx Redis Stream (resolved hosts)
# - Runs in parallel with Katana
# - Rate limited: 4 req/min per key, 500/day, 15,500/month
# - Supports API key rotation
# Cost: ~$0.004/run (minimal CPU, I/O bound)

resource "aws_ecr_repository" "tyvt" {
  name                 = "${local.name_prefix}-tyvt"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-tyvt-ecr"
  })
}

# TYVT ECS Task Definition
resource "aws_ecs_task_definition" "tyvt" {
  family                   = "${local.name_prefix}-tyvt-batch"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256   # I/O bound (VT API calls)
  memory                   = 512   # Minimal memory needed
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "tyvt-scanner"
      image     = "${aws_ecr_repository.tyvt.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "MODULE_TYPE"
          value = "tyvt"
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
        # Rate limiting configuration (preserve original throttle)
        {
          name  = "VT_ROTATION_INTERVAL"
          value = "15s"
        },
        {
          name  = "VT_RATE_LIMIT_DELAY"
          value = "15s"
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
        {
          name      = "VT_API_KEYS"
          valueFrom = data.aws_ssm_parameter.virustotal_api_keys.arn
        }
      ]

      # Resource limits (container memory < task memory)
      memory = 480
      cpu    = 256

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "tyvt"
        }
      }

      # Health check
      healthCheck = {
        command     = ["CMD-SHELL", "echo 'TYVT ready' || exit 1"]
        interval    = 30
        timeout     = 15
        retries     = 3
        startPeriod = 10
      }

      # Security
      readonlyRootFilesystem = false
      user                  = "1001:1001"
    }
  ])

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-tyvt-task"
  })
}

# ================================================================
# COST OPTIMIZATION SUMMARY
# ================================================================
# 
# MONTHLY COST COMPARISON:
# 
# BEFORE (Original Configuration):
# - Main App: 512 CPU + 1024 MB = ~$18/month
# - Subfinder: 512 CPU + 1024 MB = ~$15/month (if running continuously)  
# - SSL Analyzer: 2048 CPU + 8192 MB = ~$75/month (if running continuously)
# - Redis: cache.t3.micro = ~$8/month
# - Other: Route53, ECR, etc. = ~$3/month
# - TOTAL: ~$119/month
# 
# AFTER (Optimized Configuration):
# - Main App: 256 CPU + 512 MB = ~$9/month (50% reduction)
# - Subfinder: 256 CPU + 512 MB = ~$7/month + $0.004/run (53% reduction)
# - SSL Analyzer: 512 CPU + 1024 MB = ~$15/month + $0.01/run (80% reduction!)
# - Redis: cache.t3.micro = ~$8/month (unchanged)
# - Other: Route53, ECR, etc. = ~$3/month (unchanged)
# - TOTAL: ~$25/month (79% reduction!)
#
# SAVINGS: $94/month (79% cost reduction)
#
# ================================================================
