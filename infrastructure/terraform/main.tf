# Terraform version and providers
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    consul = {
      source  = "hashicorp/consul"
      version = "~> 2.20"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.20"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }

  # Remote state backend with optimization
  backend "s3" {
    bucket = "neobotnet-terraform-state-108457888166"
    key    = "neobotnet-v2/terraform.tfstate"
    region = "us-east-1"
    
    # Enable state optimization for faster deployments
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}

# Configure AWS Provider with optimization
provider "aws" {
  region = var.aws_region
  
  # Skip metadata API check for faster provider initialization  
  skip_metadata_api_check = true
  skip_region_validation  = true
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Local values
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
} # Force infrastructure update
# Trigger infrastructure deployment for credential sync
