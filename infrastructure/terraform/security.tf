# ================================================================
# Application Load Balancer Security Group
# ================================================================
# Allows traffic from internet to ALB on HTTP/HTTPS
# ALB then forwards to ECS tasks via private security group rules

resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  # Allow HTTP from anywhere (CloudFront sends HTTP to ALB)
  ingress {
    protocol    = "tcp"
    from_port   = 80
    to_port     = 80
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from internet (CloudFront)"
  }

  # Allow HTTPS (optional, for direct ALB access if needed)
  ingress {
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }

  # All outbound to VPC (ALB forwards to ECS tasks)
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = [var.vpc_cidr]
    description = "To ECS tasks in VPC"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# ================================================================
# ECS Tasks Security Group (Updated for ALB)
# ================================================================
# Restricts ECS tasks to only accept traffic from ALB
# This improves security by preventing direct internet access

resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${local.name_prefix}-ecs-tasks-"
  description = "Security group for ECS tasks (accepts traffic from ALB only)"
  vpc_id      = aws_vpc.main.id

  # CHANGED: Only allow traffic from ALB (not 0.0.0.0/0)
  # This prevents direct internet access to tasks
  ingress {
    protocol        = "tcp"
    from_port       = var.app_port
    to_port         = var.app_port
    security_groups = [aws_security_group.alb.id]
    description     = "HTTP from ALB only"
  }

  # All outbound traffic (for Supabase, Redis, external APIs)
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-tasks-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Consul
resource "aws_security_group" "consul" {
  name_prefix = "${local.name_prefix}-consul-"
  vpc_id      = aws_vpc.main.id

  # Consul HTTP API
  ingress {
    protocol    = "tcp"
    from_port   = 8500
    to_port     = 8500
    cidr_blocks = [var.vpc_cidr]
    description = "Consul HTTP API"
  }

  # Consul RPC
  ingress {
    protocol    = "tcp"
    from_port   = 8300
    to_port     = 8300
    cidr_blocks = [var.vpc_cidr]
    description = "Consul RPC"
  }

  # Consul Serf LAN
  ingress {
    protocol    = "tcp"
    from_port   = 8301
    to_port     = 8301
    cidr_blocks = [var.vpc_cidr]
    description = "Consul Serf LAN"
  }

  # All outbound traffic
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-consul-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Vault
resource "aws_security_group" "vault" {
  name_prefix = "${local.name_prefix}-vault-"
  vpc_id      = aws_vpc.main.id

  # Vault API
  ingress {
    protocol    = "tcp"
    from_port   = 8200
    to_port     = 8200
    cidr_blocks = [var.vpc_cidr]
    description = "Vault API"
  }

  # All outbound traffic
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vault-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
} 