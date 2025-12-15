# Additional providers for CloudFront functionality
# This file extends the providers defined in main.tf

# AWS Provider for us-east-1 (required for CloudFront SSL certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
} 