"""
NeoBot-Net CLI Configuration

Handles environment variables and configuration for AWS and Supabase access.
Configuration is loaded from environment variables or a .env file.
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

# Load environment from .env file if present
try:
    from dotenv import load_dotenv
    env_file = Path.home() / ".neobotnet" / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()  # Try current directory
except ImportError:
    pass  # dotenv not installed, use system env vars


@dataclass
class AWSConfig:
    """AWS configuration for ECS task management."""
    region: str
    ecs_cluster: str
    orchestrator_task_family: str
    subnets: List[str]
    security_group: str
    
    @classmethod
    def from_env(cls) -> "AWSConfig":
        """Load AWS config from environment variables."""
        subnets_str = os.environ.get("ECS_SUBNETS", "")
        subnets = [s.strip() for s in subnets_str.split(",") if s.strip()]
        
        return cls(
            region=os.environ.get("AWS_REGION", "us-east-1"),
            ecs_cluster=os.environ.get("ECS_CLUSTER", "neobotnet-v2-dev-cluster"),
            orchestrator_task_family=os.environ.get(
                "ECS_ORCHESTRATOR_TASK", 
                "neobotnet-v2-dev-orchestrator"
            ),
            subnets=subnets,
            security_group=os.environ.get("ECS_SECURITY_GROUP", "")
        )


@dataclass
class SupabaseConfig:
    """Supabase configuration for database access."""
    url: str
    service_role_key: str
    
    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        """Load Supabase config from environment variables."""
        return cls(
            url=os.environ.get("SUPABASE_URL", ""),
            service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        )


@dataclass
class Config:
    """Main CLI configuration."""
    aws: AWSConfig
    supabase: SupabaseConfig
    
    @classmethod
    def load(cls) -> "Config":
        """Load all configuration from environment."""
        return cls(
            aws=AWSConfig.from_env(),
            supabase=SupabaseConfig.from_env()
        )
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of missing fields.
        
        Returns:
            List of missing/invalid configuration items
        """
        missing = []
        
        # AWS validation
        if not self.aws.subnets:
            missing.append("ECS_SUBNETS (comma-separated subnet IDs)")
        if not self.aws.security_group:
            missing.append("ECS_SECURITY_GROUP")
        
        # Supabase validation
        if not self.supabase.url:
            missing.append("SUPABASE_URL")
        if not self.supabase.service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        
        return missing


# Singleton config instance
_config: Optional[Config] = None

def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def get_supabase_client():
    """Create a Supabase client with service role key."""
    from supabase import create_client
    config = get_config()
    return create_client(config.supabase.url, config.supabase.service_role_key)

