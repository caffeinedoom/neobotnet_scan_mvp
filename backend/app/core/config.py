"""
Core configuration settings for the application.

LEAN Refactor (2026-01): Simplified configuration without billing dependencies.
"""
import json
import os
from typing import List, Optional, Dict, Any, Union
from pydantic import Field, field_validator
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
    access_token_expire_minutes: int = Field(default=90, description="Token expiration time")
    
    # Cookie Security Configuration
    cookie_secure: bool = Field(default=False, description="Use secure cookies (HTTPS only)")
    cookie_samesite: str = Field(default="lax", description="SameSite cookie policy")
    cookie_httponly: bool = Field(default=True, description="HttpOnly cookies for XSS protection")
    cookie_domain: Optional[str] = Field(default=None, description="Cookie domain")
    
    # FastAPI Configuration
    api_v1_str: str = Field(default="/api/v1", description="API v1 prefix")
    project_name: str = Field(default="neobotnet-v2", description="Project name")
    environment: str = Field(default="dev", description="Environment")
    debug: bool = Field(default=True, description="Debug mode")
    
    # CORS Configuration - Production domains
    allowed_origins: List[str] = Field(
        default=[
            # Local development
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://172.236.127.72:3000",
            "http://0.0.0.0:3000",
            # Production domains
            "https://neobotnet.com",
            "https://www.neobotnet.com",          # Frontend
            "https://aldous-api.neobotnet.com",   # Backend API
            "https://huxley.neobotnet.com",       # Supabase Auth
            # Vercel deployments
            "https://neobotnet-scan-mvp.vercel.app",
        ],
        description="Allowed CORS origins"
    )
    
    # Dynamic CORS patterns
    cors_origin_patterns: List[str] = Field(
        default=[
            r"https://.*\.vercel\.app$",
            r"https://.*\.neobotnet\.com$",
        ],
        description="Regex patterns for allowed CORS origins"
    )
    
    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse ALLOWED_ORIGINS from string (JSON) or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # Environment properties
    @property
    def is_production_environment(self) -> bool:
        """Check if running in production environment."""
        return self.environment in ["production", "prod"]
    
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
    
    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis server host")
    redis_port: int = Field(default=6379, description="Redis server port")
    redis_auth_token: Optional[str] = Field(default=None, description="Redis AUTH token")
    redis_ssl: bool = Field(default=False, description="Use SSL for Redis connection")
    redis_cluster_mode: bool = Field(default=False, description="Redis cluster mode")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL based on environment."""
        if self.is_local_environment:
            return f"redis://localhost:6379/0"
        else:
            protocol = "rediss" if self.redis_ssl else "redis"
            auth_part = f":{self.redis_auth_token}@" if self.redis_auth_token else ""
            return f"{protocol}://{auth_part}{self.redis_host}:{self.redis_port}/0"
    
    @property
    def redis_connection_kwargs(self) -> Dict[str, Any]:
        """Get Redis connection kwargs."""
        kwargs = {
            "host": "localhost" if self.is_local_environment else self.redis_host,
            "port": 6379 if self.is_local_environment else self.redis_port,
            "db": 0,
            "decode_responses": True,
        }
        
        if not self.is_local_environment:
            if self.redis_auth_token:
                kwargs["password"] = self.redis_auth_token
            if self.redis_ssl:
                kwargs["ssl"] = True
                kwargs["ssl_cert_reqs"] = None
        
        return kwargs
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore extra env vars
    }


# Create settings instance
settings = Settings()
