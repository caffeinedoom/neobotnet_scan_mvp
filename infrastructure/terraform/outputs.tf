# Networking outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnets" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnets" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

# ALB security group output removed - using ultra-minimal architecture

output "security_group_ecs_tasks" {
  description = "ID of the security group for ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}

# Load balancer outputs removed - using ultra-minimal architecture with direct ECS access
# Note: API is now accessible via ECS task public IP (changes on task restart)
# Use: aws ecs describe-tasks to get current task public IP

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service (batch processing service)"
  value       = aws_ecs_service.main_batch.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.ecs.name
}

# CloudFront Domain Outputs
output "api_domain_name" {
  description = "API domain name (HTTPS endpoint)"
  value       = var.api_domain_name
}

output "api_zone_nameservers" {
  description = "Route53 nameservers for the API subdomain (configure these in Namecheap)"
  value       = aws_route53_zone.api_zone.name_servers
}

output "api_zone_id" {
  description = "Route53 hosted zone ID for the API domain"
  value       = aws_route53_zone.api_zone.zone_id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.api_distribution.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.api_distribution.domain_name
}

output "ssl_certificate_arn" {
  description = "SSL certificate ARN"
  value       = aws_acm_certificate.api_cert.arn
}

# Direct ECS access information
output "ecs_task_public_ip" {
  description = "Current ECS task public IP (managed by deployment scripts)"
  value       = "Use: ./scripts/get-current-ip.sh to get current IP"
}

# CloudFront + ECS Architecture (Smart Hostname Workaround):
# - HTTPS API: https://aldous-api.neobotnet.com (via CloudFront)
# - Direct API: http://34.200.242.142:8000 (for development/testing)
# - Internal hostname: ecs-direct.aldous-api.neobotnet.com → 34.200.242.142
# - Health check: https://aldous-api.neobotnet.com/health
# - API endpoints: https://aldous-api.neobotnet.com/api/v1/
#
# Architecture Flow:
# Internet → CloudFront → ecs-direct.aldous-api.neobotnet.com (DNS A record) → ECS Task IP
#
# When ECS IP changes:
# 1. Update local.ecs_task_ip in cloudfront.tf
# 2. Run terraform apply (updates DNS record automatically)

# Redis Connection Information
output "redis_endpoint" {
  description = "Redis ElastiCache endpoint for application connection"
  value       = aws_elasticache_cluster.redis.configuration_endpoint != null ? aws_elasticache_cluster.redis.configuration_endpoint : aws_elasticache_cluster.redis.cache_nodes[0].address
  sensitive   = false
}

output "redis_port" {
  description = "Redis port number"
  value       = aws_elasticache_cluster.redis.port
}

# ================================================================
# Backend Application Outputs
# ================================================================

output "backend_ecr_repository_url" {
  description = "ECR repository URL for backend application"
  value       = aws_ecr_repository.backend.repository_url
}

# ================================================================
# Subfinder Container Outputs
# ================================================================

output "subfinder_ecr_repository_url" {
  description = "ECR repository URL for subfinder container"
  value       = aws_ecr_repository.subfinder.repository_url
}

output "subfinder_task_definition_arn" {
  description = "ARN of the subfinder ECS task definition"
  value       = aws_ecs_task_definition.subfinder.arn
}

output "subfinder_task_definition_family" {
  description = "Family name of the subfinder ECS task definition"
  value       = aws_ecs_task_definition.subfinder.family
}

# ================================================================
# DNSX Container Outputs
# ================================================================

output "dnsx_ecr_repository_url" {
  description = "ECR repository URL for DNSX container"
  value       = aws_ecr_repository.dnsx.repository_url
}

output "dnsx_task_definition_arn" {
  description = "ARN of the DNSX ECS task definition"
  value       = aws_ecs_task_definition.dnsx.arn
}

output "httpx_ecr_repository_url" {
  description = "URL of the HTTPx ECR repository"
  value       = aws_ecr_repository.httpx.repository_url
}

output "httpx_task_definition_arn" {
  description = "ARN of the HTTPx ECS task definition"
  value       = aws_ecs_task_definition.httpx.arn
}

output "dnsx_task_definition_family" {
  description = "Family name of the DNSX ECS task definition"
  value       = aws_ecs_task_definition.dnsx.family
}

output "httpx_task_definition_family" {
  description = "Family name of the HTTPx ECS task definition"
  value       = aws_ecs_task_definition.httpx.family
}

# ================================================================
# Katana Web Crawler Outputs
# ================================================================

output "katana_ecr_repository_url" {
  description = "ECR repository URL for Katana container"
  value       = aws_ecr_repository.katana.repository_url
}

output "katana_task_definition_arn" {
  description = "ARN of the Katana ECS task definition"
  value       = aws_ecs_task_definition.katana.arn
}

output "katana_task_definition_family" {
  description = "Family name of the Katana ECS task definition"
  value       = aws_ecs_task_definition.katana.family
} 