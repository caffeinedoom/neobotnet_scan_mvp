# ================================================================
# Application Load Balancer (ALB) Infrastructure
# ================================================================
# This file creates an internet-facing ALB to sit in front of ECS tasks.
# Benefits:
# - Stable DNS (no changes on deployment)
# - Health checks before routing traffic
# - Zero-downtime deployments
# - Automatic failover between tasks
# - Industry standard architecture
# ================================================================

# ================================================================
# Application Load Balancer
# ================================================================

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false # Internet-facing
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection       = true # Production: prevent accidental deletion
  enable_http2                     = true
  enable_cross_zone_load_balancing = true

  # Drop invalid header fields (security best practice)
  drop_invalid_header_fields = true

  tags = merge(local.common_tags, {
    Name        = "${local.name_prefix}-alb"
    Description = "Application Load Balancer for ${var.project_name} ${var.environment}"
  })
}

# ================================================================
# Target Group for ECS Tasks
# ================================================================
# Target type is "ip" because Fargate uses awsvpc network mode

resource "aws_lb_target_group" "app" {
  name        = "${local.name_prefix}-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # Required for Fargate tasks

  # Health check configuration
  health_check {
    enabled             = true
    healthy_threshold   = 2  # 2 successful checks = healthy
    unhealthy_threshold = 3  # 3 failed checks = unhealthy
    timeout             = 5  # Wait 5s for response
    interval            = 30 # Check every 30s
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200" # Expect 200 OK
  }

  # Deregistration delay (connection draining)
  # ECS waits this long before removing a task from the target group
  # Allows in-flight requests to complete gracefully
  deregistration_delay = 30 # 30 seconds

  # Stickiness disabled (API doesn't need session affinity)
  stickiness {
    enabled = false
    type    = "lb_cookie"
  }

  tags = merge(local.common_tags, {
    Name        = "${local.name_prefix}-target-group"
    Description = "Target group for ECS tasks"
  })

  # Allow target group to be destroyed and recreated if needed
  lifecycle {
    create_before_destroy = true
  }

  # Dependency ensures VPC is fully created before target group
  depends_on = [aws_lb.main]
}

# ================================================================
# HTTP Listener (Port 80)
# ================================================================
# Forwards all HTTP traffic to the target group
# CloudFront sends HTTP to ALB (HTTPS termination happens at CloudFront)

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-http-listener"
  })
}

# ================================================================
# Outputs
# ================================================================
# These outputs are used by other resources (CloudFront, monitoring)

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer (use this for CloudFront origin)"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Canonical hosted zone ID of the ALB (for Route53 alias records)"
  value       = aws_lb.main.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "target_group_arn" {
  description = "ARN of the target group (used by ECS service)"
  value       = aws_lb_target_group.app.arn
}

output "target_group_name" {
  description = "Name of the target group"
  value       = aws_lb_target_group.app.name
}
