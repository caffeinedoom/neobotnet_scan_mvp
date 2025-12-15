"""
Environment Detection and Configuration System
Automatically determines optimal execution environment for different operations.
"""

import os
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class EnvironmentType(str, Enum):
    """Environment types for operation routing."""
    LOCAL_DEV = "local-dev"
    LOCAL_DOCKER = "local-docker" 
    CLOUD_DEV = "cloud-dev"
    CLOUD_STAGING = "staging"
    CLOUD_PRODUCTION = "production"


class OperationType(str, Enum):
    """Types of operations that can be routed."""
    ASSET_MANAGEMENT = "asset_management"  # Local preferred
    AUTHENTICATION = "authentication"     # Any environment
    SCAN_OPERATION = "scan_operation"      # Cloud preferred
    DATA_RETRIEVAL = "data_retrieval"     # Any environment


@dataclass
class EnvironmentCapabilities:
    """Capabilities available in each environment."""
    has_ecs: bool = False
    has_local_containers: bool = False
    has_redis: bool = False
    has_database: bool = False
    can_scan: bool = False
    preferred_for_scans: bool = False


class EnvironmentDetector:
    """Detects current environment and available capabilities."""
    
    def __init__(self):
        self._capabilities_cache: Optional[EnvironmentCapabilities] = None
        self._environment_cache: Optional[EnvironmentType] = None
    
    def detect_environment(self) -> EnvironmentType:
        """Detect the current execution environment."""
        if self._environment_cache:
            return self._environment_cache
            
        # Check environment variable first
        env_var = os.getenv('ENVIRONMENT', '').lower()
        
        if env_var in ['production', 'prod']:
            self._environment_cache = EnvironmentType.CLOUD_PRODUCTION
        elif env_var in ['staging', 'stage']:
            self._environment_cache = EnvironmentType.CLOUD_STAGING
        elif env_var in ['cloud-dev', 'dev'] and self._is_cloud_environment():
            self._environment_cache = EnvironmentType.CLOUD_DEV
        elif env_var in ['local-dev', 'development']:
            self._environment_cache = EnvironmentType.LOCAL_DEV
        elif self._is_docker_environment():
            self._environment_cache = EnvironmentType.LOCAL_DOCKER
        else:
            # Default to local development
            self._environment_cache = EnvironmentType.LOCAL_DEV
            
        return self._environment_cache
    
    def _is_cloud_environment(self) -> bool:
        """Check if running in cloud environment (AWS ECS)."""
        # Check for ECS metadata endpoint
        if os.path.exists('/opt/aws/amazon-ecs-agent'):
            return True
            
        # Check for ECS task metadata environment variables
        ecs_indicators = [
            'ECS_CONTAINER_METADATA_URI',
            'ECS_CONTAINER_METADATA_URI_V4',
            'AWS_EXECUTION_ENV'
        ]
        
        if any(os.getenv(indicator) for indicator in ecs_indicators):
            return True
            
        # Check if Redis host is an ElastiCache endpoint
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        if redis_host != 'localhost' and '.cache.amazonaws.com' in redis_host:
            return True
            
        return False
    
    def _is_docker_environment(self) -> bool:
        """Check if running in Docker container."""
        # Check for Docker-specific indicators
        if os.path.exists('/.dockerenv'):
            return True
            
        # Check cgroup for docker
        try:
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read()
        except:
            return False
    
    async def get_capabilities(self) -> EnvironmentCapabilities:
        """Get capabilities available in current environment."""
        if self._capabilities_cache:
            return self._capabilities_cache
            
        environment = self.detect_environment()
        capabilities = EnvironmentCapabilities()
        
        # Test ECS availability
        capabilities.has_ecs = await self._test_ecs_access()
        
        # Test local container availability  
        capabilities.has_local_containers = await self._test_local_containers()
        
        # Test Redis connectivity
        capabilities.has_redis = await self._test_redis_connectivity()
        
        # Test database connectivity
        capabilities.has_database = await self._test_database_connectivity()
        
        # Determine scan capabilities
        capabilities.can_scan = capabilities.has_ecs or capabilities.has_local_containers
        
        # Determine scan preference based on environment
        if environment in [EnvironmentType.CLOUD_DEV, EnvironmentType.CLOUD_STAGING, EnvironmentType.CLOUD_PRODUCTION]:
            capabilities.preferred_for_scans = capabilities.has_ecs
        else:
            # Local environments prefer local containers for development speed
            capabilities.preferred_for_scans = capabilities.has_local_containers
            
        self._capabilities_cache = capabilities
        return capabilities
    
    async def _test_ecs_access(self) -> bool:
        """Test if ECS is accessible and functional."""
        if not BOTO3_AVAILABLE:
            return False
            
        try:
            client = boto3.client('ecs', region_name='us-east-1')
            # Test basic ECS access
            client.list_clusters()
            return True
        except (ClientError, NoCredentialsError, Exception):
            return False
    
    async def _test_local_containers(self) -> bool:
        """Test if local containers are available."""
        try:
            import docker
            client = docker.from_env()
            
            # Check if we can list containers
            client.containers.list()
            
            # Check if our scan containers exist
            # CLEANUP (2025-10-06): Removed 'neobotnet-cloud-ssl-analyzer' - module no longer used
            scan_containers = ['neobotnet-subfinder']
            existing_containers = [container.name for container in client.containers.list(all=True)]
            
            return any(container in existing_containers for container in scan_containers)
        except Exception:
            return False
    
    async def _test_redis_connectivity(self) -> bool:
        """Test Redis connectivity."""
        try:
            # Import here to avoid circular imports
            from ..core.config import settings
            
            # Use our Redis configuration
            import redis.asyncio as redis
            redis_config = settings.redis_connection_kwargs
            client = redis.Redis(**redis_config)
            
            await client.ping()
            await client.aclose()
            return True
        except Exception:
            return False
    
    async def _test_database_connectivity(self) -> bool:
        """Test database connectivity."""
        try:
            # Test Supabase connectivity
            from ..core.supabase_client import supabase_client
            
            # Simple query to test connectivity
            result = supabase_client.service_client.table("assets").select("id").limit(1).execute()
            return True
        except Exception:
            return False


class EnvironmentRouter:
    """Routes operations to the optimal environment."""
    
    def __init__(self):
        self.detector = EnvironmentDetector()
        self._capabilities: Optional[EnvironmentCapabilities] = None
    
    async def get_optimal_environment(self, operation_type: OperationType) -> Dict[str, Any]:
        """Get the optimal environment configuration for an operation type."""
        
        if not self._capabilities:
            self._capabilities = await self.detector.get_capabilities()
        
        environment = self.detector.detect_environment()
        
        routing_config = {
            "environment": environment,
            "operation_type": operation_type,
            "capabilities": self._capabilities,
            "execution_strategy": None,
            "fallback_strategy": None,
            "notifications": []
        }
        
        # Route based on operation type
        if operation_type == OperationType.SCAN_OPERATION:
            routing_config.update(await self._route_scan_operation())
        elif operation_type == OperationType.ASSET_MANAGEMENT:
            routing_config.update(self._route_asset_management())
        elif operation_type == OperationType.AUTHENTICATION:
            routing_config.update(self._route_authentication())
        elif operation_type == OperationType.DATA_RETRIEVAL:
            routing_config.update(self._route_data_retrieval())
            
        return routing_config
    
    async def _route_scan_operation(self) -> Dict[str, Any]:
        """Route scan operations to best available environment."""
        
        if self._capabilities.has_ecs and self._capabilities.preferred_for_scans:
            return {
                "execution_strategy": "cloud_ecs",
                "fallback_strategy": "local_containers" if self._capabilities.has_local_containers else None,
                "notifications": ["Using cloud ECS for optimal scan performance"]
            }
        elif self._capabilities.has_local_containers:
            return {
                "execution_strategy": "local_containers",
                "fallback_strategy": None,
                "notifications": ["Using local containers for development scanning"]
            }
        elif self._capabilities.has_ecs:
            return {
                "execution_strategy": "cloud_ecs",
                "fallback_strategy": None,
                "notifications": ["Using cloud ECS (only option available)"]
            }
        else:
            return {
                "execution_strategy": "mock",
                "fallback_strategy": None,
                "notifications": ["No scan capability available - using mock data for development"]
            }
    
    def _route_asset_management(self) -> Dict[str, Any]:
        """Route asset management to current environment."""
        return {
            "execution_strategy": "current_environment",
            "fallback_strategy": None,
            "notifications": ["Using current environment for asset management"]
        }
    
    def _route_authentication(self) -> Dict[str, Any]:
        """Route authentication to current environment."""
        return {
            "execution_strategy": "current_environment", 
            "fallback_strategy": None,
            "notifications": ["Using current environment for authentication"]
        }
    
    def _route_data_retrieval(self) -> Dict[str, Any]:
        """Route data retrieval to current environment."""
        return {
            "execution_strategy": "current_environment",
            "fallback_strategy": None,
            "notifications": ["Using current environment for data retrieval"]
        }


# Global instances
environment_detector = EnvironmentDetector()
environment_router = EnvironmentRouter()


# Convenience functions
async def get_current_environment() -> EnvironmentType:
    """Get current environment type."""
    return environment_detector.detect_environment()


async def get_environment_capabilities() -> EnvironmentCapabilities:
    """Get current environment capabilities."""
    return await environment_detector.get_capabilities()


async def route_operation(operation_type: OperationType) -> Dict[str, Any]:
    """Route an operation to the optimal environment."""
    return await environment_router.get_optimal_environment(operation_type)
