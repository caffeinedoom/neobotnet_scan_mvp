# ================================================================
# CloudFront Response Headers Policy to Fix Error Caching
# ================================================================
# This policy prevents CloudFront from caching 4xx/5xx error responses
# which was causing 401 authentication responses to be cached as errors

resource "aws_cloudfront_response_headers_policy" "api_policy" {
  name    = "${local.name_prefix}-api-policy"
  comment = "API policy that prevents error response caching"

  # Remove server headers that might cause caching issues
  remove_headers_config {
    items {
      header = "Server"
    }
  }

  # Custom headers to prevent error caching
  custom_headers_config {
    items {
      header   = "Cache-Control"
      value    = "no-cache, no-store, must-revalidate"
      override = false
    }
  }

  # Security headers for API
  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      override                   = true
    }
  }

  # CORS is handled by the backend (FastAPI CORSMiddleware)
  # This allows dynamic origin matching including Vercel preview deployments
  # DO NOT add cors_config here - it would override backend CORS headers
}

# CloudFront Distribution for aldous-api.neobotnet.com
# Provides HTTPS endpoint for development API testing

variable "api_domain_name" {
  description = "API subdomain for development"
  type        = string
  default     = "aldous-api.neobotnet.com"
}

# Route53 Hosted Zone for the API subdomain
resource "aws_route53_zone" "api_zone" {
  name = var.api_domain_name

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-api-zone"
  })
}

# SSL Certificate for CloudFront (must be in us-east-1)
resource "aws_acm_certificate" "api_cert" {
  provider          = aws.us_east_1
  domain_name       = var.api_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-api-cert"
  })
}

# Certificate validation DNS records in Route53
resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api_cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.api_zone.zone_id
}

# Wait for certificate validation
resource "aws_acm_certificate_validation" "api_cert" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.api_cert.arn
  validation_record_fqdns = [for record in aws_route53_record.api_cert_validation : record.fqdn]

  timeouts {
    create = "5m"
  }
}

# ================================================================
# CloudFront Origin: Application Load Balancer
# ================================================================
# CloudFront now points to ALB instead of direct ECS task IP
# Benefits:
# - Stable DNS (ALB DNS never changes)
# - No manual DNS updates needed
# - Health checks ensure traffic goes to healthy tasks only
# - Zero-downtime deployments

# CloudFront Distribution - Using ALB as origin
resource "aws_cloudfront_distribution" "api_distribution" {
  origin {
    domain_name = aws_lb.main.dns_name # ALB DNS (stable)
    origin_id   = "${local.name_prefix}-api-origin"

    custom_origin_config {
      http_port              = 80 # ALB listens on port 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]

      # Timeout configurations (ADDED)
      # These improve reliability for long-running requests
      origin_read_timeout      = 60 # Max allowed by CloudFront
      origin_keepalive_timeout = 60 # Keep connections alive
    }
  }

  enabled = true
  comment = "CloudFront for ${var.api_domain_name} - Production API"

  aliases = [var.api_domain_name]

  # ================================================================
  # Cache Behavior: Health Check Endpoint
  # ================================================================
  # Short cache for health checks to reduce origin load
  # Safe to cache as it's public and doesn't contain user data
  ordered_cache_behavior {
    path_pattern           = "/health"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "${local.name_prefix}-api-origin"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 10  # Cache for 10 seconds
    max_ttl     = 30  # Max 30 seconds

    response_headers_policy_id = aws_cloudfront_response_headers_policy.api_policy.id
  }

  # ================================================================
  # Default Behavior: API Endpoints (No Caching)
  # ================================================================
  # API responses contain user-specific data and must not be cached.
  # All headers/cookies forwarded to ensure authentication works.
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "${local.name_prefix}-api-origin"
    compress               = true  # Enable compression for API responses
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = true
      headers      = ["*"]  # Forward all headers for auth
      cookies {
        forward = "all"     # Forward all cookies for session
      }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0  # No caching - API returns user-specific data

    # Apply response headers policy to prevent error caching
    response_headers_policy_id = aws_cloudfront_response_headers_policy.api_policy.id
  }

  # Use cheapest price class for development
  price_class = "PriceClass_100"

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.api_cert.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-api-cloudfront"
  })

  depends_on = [
    aws_acm_certificate_validation.api_cert,
    aws_lb.main # Changed from aws_route53_record.ecs_direct
  ]
}

# DNS record pointing to CloudFront
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.api_zone.zone_id
  name    = var.api_domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.api_distribution.domain_name
    zone_id                = aws_cloudfront_distribution.api_distribution.hosted_zone_id
    evaluate_target_health = false
  }
} 