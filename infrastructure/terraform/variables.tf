# Project Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "neobotnet-v2"
}

variable "environment" {
  description = "Environment (dev, staging, production)"
  type        = string
  default     = "dev"
  # For production deployment, override with: -var="environment=production"
}

# AWS Configuration
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones_count" {
  description = "Number of availability zones"
  type        = number
  default     = 2
}

# ECS Configuration
# DEPRECATED: app_image variable no longer used
# Backend image now comes from aws_ecr_repository.backend.repository_url
# Kept for backwards compatibility but not referenced anywhere
variable "app_image" {
  description = "DEPRECATED - Backend image now uses ECR repository directly"
  type        = string
  default     = "DEPRECATED-use-ecr-repository"
}

variable "app_port" {
  description = "Port exposed by the docker image to redirect traffic to"
  type        = number
  default     = 8000
}

variable "app_count" {
  description = "Number of docker containers to run"
  type        = number
  default     = 1  # Reduced from 2 for development cost optimization
}

variable "health_check_path" {
  description = "Health check path"
  type        = string
  default     = "/health"
}

# Fargate Configuration
variable "fargate_cpu" {
  description = "Fargate instance CPU units to provision (1 vCPU = 1024 CPU units)"
  type        = number
  default     = 512
}

variable "fargate_memory" {
  description = "Fargate instance memory to provision (in MiB)"
  type        = number
  default     = 1024
}

# ================================================================
# SECRETS - Managed in AWS SSM Parameter Store
# ================================================================
# Secrets are NOT passed as Terraform variables.
# They are read from SSM Parameter Store via data sources in secrets.tf
# 
# Required SSM Parameters (create manually in AWS Console):
#   /${project_name}-${environment}/supabase-url
#   /${project_name}-${environment}/supabase-anon-key
#   /${project_name}-${environment}/supabase-service-role-key
#   /${project_name}-${environment}/jwt-secret-key
# ================================================================

variable "allowed_origins" {
  description = "List of allowed CORS origins for production"
  type        = list(string)
  default     = [
    "https://neobotnet.com",
    "https://www.neobotnet.com",
    "https://neobotnet-scan-mvp.vercel.app",
    "https://neobotnet-v2-git-dev-sams-projects-3ea6cef5.vercel.app"
  ]
  # Note: Backend also supports dynamic patterns for *.vercel.app and *.neobotnet.com
} 