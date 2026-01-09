"""
Core configuration settings for the application.
""" 
import json
from typing import List, Optional, Dict, Any, Union
from pydantic import Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anonymous key") 
    supabase_service_role_key: str = Field(..., description="Supabase service role key")
    
    # JWT Configuration
    jwt_secret_key: str = Field(..., description="Secret key for JWT tokens")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=90, description="Token expiration time - extended for better UX")
    
    # Cookie Security Configuration
    cookie_secure: bool = Field(default=False, description="Use secure cookies (HTTPS only) - auto-enabled in production")
    cookie_samesite: str = Field(default="lax", description="SameSite cookie policy")
    cookie_httponly: bool = Field(default=True, description="HttpOnly cookies for XSS protection")
    cookie_domain: Optional[str] = Field(default=None, description="Cookie domain for cross-subdomain auth")
    
    # FastAPI Configuration
    api_v1_str: str = Field(default="/api/v1", description="API v1 prefix")
    project_name: str = Field(default="neobotnet-v2", description="Project name")
    environment: str = Field(default="dev", description="Environment (dev, staging, production)")
    debug: bool = Field(default=False, description="Debug mode - set True only for local development")
    
    # CORS Configuration
    # Production origins - always included
    # Local development origins are added dynamically via get_cors_origins() property
    allowed_origins: List[str] = Field(
        default=[
            # Production Vercel deployments
            "https://neobotnet-scan-mvp.vercel.app",
            "https://neobotnet-v2-git-dev-sams-projects-3ea6cef5.vercel.app",
        ],
        description="Allowed CORS origins (production)"
    )
    
    # Additional CORS origin patterns (checked dynamically)
    cors_origin_patterns: List[str] = Field(
        default=[
            r"https://.*\.vercel\.app$",  # All Vercel preview deployments
            r"https://.*\.neobotnet\.com$",  # All neobotnet subdomains
            r"https://neobotnet\.com$",  # Bare domain (no subdomain)
            r"https://www\.neobotnet\.com$",  # www subdomain explicitly
        ],
        description="Regex patterns for allowed CORS origins"
    )
    
    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse ALLOWED_ORIGINS from string (JSON) or list."""
        if isinstance(v, str):
            try:
                # Try to parse as JSON array first (for Terraform/environment variables)
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                # If not JSON, split by comma as fallback
                return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # Environment-specific properties
    @property
    def is_production_environment(self) -> bool:
        """Check if running in production environment."""
        return self.environment in ["production", "prod"]
    
    @property
    def is_cloud_deployment(self) -> bool:
        """Check if running in cloud deployment (regardless of environment setting)."""
        # Detect cloud deployment by checking if we're using cloud domain origins
        cloud_indicators = [
            "neobotnet.com" in str(self.allowed_origins),
            "vercel.app" in str(self.allowed_origins),
            any("aldous-api" in origin for origin in self.allowed_origins),
        ]
        return any(cloud_indicators) or self.environment in ["production", "staging", "cloud-dev"]
    
    @property  
    def is_cross_origin_environment(self) -> bool:
        """Check if this is a cross-origin environment requiring special cookie handling."""
        return self.is_cloud_deployment or self.is_production_environment
    
    @property
    def effective_cors_origins(self) -> List[str]:
        """
        Get CORS origins based on environment.
        
        - Production: Only production origins (Vercel deployments, neobotnet.com)
        - Development: Adds localhost origins for local testing
        """
        origins = list(self.allowed_origins)  # Copy to avoid mutation
        
        # Add localhost origins only in development
        if not self.is_production_environment and self.debug:
            local_origins = [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://0.0.0.0:3000",
            ]
            for origin in local_origins:
                if origin not in origins:
                    origins.append(origin)
        
        return origins
    
    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis server host")
    redis_port: int = Field(default=6379, description="Redis server port")
    redis_auth_token: Optional[str] = Field(default=None, description="Redis AUTH token for ElastiCache")
    redis_ssl: bool = Field(default=False, description="Use SSL for Redis connection")
    redis_cluster_mode: bool = Field(default=False, description="Redis cluster mode for ElastiCache")
    
    @property
    def redis_url(self) -> str:
        """
        Environment-aware Redis URL construction.
        
        Automatically detects local vs cloud environment and constructs
        the appropriate Redis connection URL for WebSocket functionality.
        
        Local Environment:
        - Uses localhost Redis (host system or Docker)
        - Simple redis:// protocol without authentication
        - Perfect for development and local testing
        
        Cloud Environment:
        - Uses ElastiCache endpoint in VPC private subnet
        - Supports SSL and authentication when configured
        - Secure connection for production workloads
        """
        # Determine protocol based on environment and SSL settings
        if self.is_local_environment:
            # Local development - always use simple redis://
            protocol = "redis"
            auth_part = ""
            host = "localhost"  # Force localhost for local development
            port = 6379
        else:
            # Cloud environment - use configured settings
            protocol = "rediss" if self.redis_ssl else "redis"
            auth_part = f":{self.redis_auth_token}@" if self.redis_auth_token else ""
            host = self.redis_host
            port = self.redis_port
        
        return f"{protocol}://{auth_part}{host}:{port}/0"
    
    @property
    def is_local_environment(self) -> bool:
        """Check if running in local development environment."""
        return (
            self.environment in ["local", "local-dev", "dev"] and 
            self.redis_host == "localhost"
        ) or self.environment == "local-dev"
    
    @property
    def is_cloud_environment(self) -> bool:
        """Check if running in cloud environment (AWS ECS)."""
        return self.environment in ["production", "staging"] or self.redis_host != "localhost"
    
    @property
    def redis_connection_kwargs(self) -> Dict[str, Any]:
        """Get Redis connection parameters based on environment."""
        base_config = {
            "host": self.redis_host,
            "port": self.redis_port,
            "decode_responses": True,
            "socket_timeout": 10,
            "socket_connect_timeout": 10,
            # Note: retry_on_timeout removed as it's deprecated in Redis 6.x
        }
        
        # Cloud environment (ElastiCache) specific settings
        if self.is_cloud_environment:
            base_config.update({
                "health_check_interval": 30,
                "socket_keepalive": True,
                "socket_keepalive_options": {},
                # Modern Redis client parameters (removed deprecated connection_pool_kwargs)
                "max_connections": 10,
                # Note: retry_on_timeout removed as it's also deprecated in Redis 6.x
            })
            
            # Add AUTH token if provided (for ElastiCache AUTH)
            if self.redis_auth_token:
                base_config["password"] = self.redis_auth_token
                
            # SSL configuration for transit encryption
            if self.redis_ssl:
                base_config["ssl"] = True
                base_config["ssl_check_hostname"] = False
                
        return base_config
    
    # ECS Task Role Configuration (for batch processing - cloud deployment only)
    ecs_task_execution_role_arn: str = Field(default="", description="ECS task execution role ARN for container startup")
    ecs_task_role_arn: str = Field(default="", description="ECS task role ARN for main application containers")
    ecs_subfinder_task_role_arn: str = Field(default="", description="ECS task role ARN for subfinder batch containers")
    
    # Rate Limiting Configuration
    rate_limit_per_minute: int = Field(default=60, description="API requests per minute per user")
    rate_limit_burst: int = Field(default=10, description="Burst limit for API requests")
    
    model_config = ConfigDict(
        env_file=".env.dev",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings() 