"""
Reconnaissance service for subdomain enumeration and other recon tasks.

⚠️  DEPRECATED: This service is being phased out in favor of asset_service.py
    which provides unified asset-level scanning with batch optimization.

MIGRATION: Use asset_service.enhanced_scan_asset_request() instead
"""
import uuid
import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from ..utils.json_encoder import safe_json_dumps
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

try:
    import redis.asyncio as redis
except ImportError:
    import redis

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    
from ..core.config import settings
from ..core.supabase_client import supabase_client
from ..schemas.recon import SubdomainScanRequest, ScanJobResponse, ReconModule
from .workflow_orchestrator import workflow_orchestrator

# ⚠️ DEPRECATION LOGGING
import logging
import warnings

logger = logging.getLogger(__name__)

# Log deprecation on module import
logger.warning(
    "⚠️  DEPRECATED MODULE: recon_service.py imported | "
    f"timestamp={datetime.utcnow().isoformat()} | "
    "message=This module is deprecated, use asset_service.py instead"
)

# Import usage service for quota checking (avoid circular import by importing here)
def get_usage_service():
    from .usage_service import usage_service
    return usage_service

class ReconService:
    """Service for managing reconnaissance operations."""
    
    def __init__(self):
        self.supabase = supabase_client.service_client  # Use service role for backend operations
        self.redis_client = None
        self.ecs_client = None
        self._init_aws_clients()
        
    async def get_redis(self):
        """Get Redis connection."""
        if not self.redis_client:
            try:
                self.redis_client = redis.Redis(
                    host=getattr(settings, 'redis_host', 'localhost'),
                    port=getattr(settings, 'redis_port', 6379),
                    decode_responses=True,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                # Test connection
                await self.redis_client.ping()
                
            except Exception as e:
                print(f"Redis connection failed: {str(e)}")
                self.redis_client = None
                
        return self.redis_client
    
    def _init_aws_clients(self):
        """Initialize AWS clients."""
        if boto3 is None:
            print("Warning: boto3 not available, ECS tasks will be disabled")
            return
            
        try:
            # Initialize ECS client
            self.ecs_client = boto3.client('ecs', region_name='us-east-1')
            
            # Test AWS credentials
            sts_client = boto3.client('sts', region_name='us-east-1')
            sts_client.get_caller_identity()
            
        except (ClientError, NoCredentialsError) as e:
            print(f"AWS client initialization failed: {str(e)}")
            self.ecs_client = None
    
    async def _run_subfinder_task(self, domain: str, job_id: str) -> bool:
        """Run subfinder ECS task."""
        if not self.ecs_client:
            raise Exception("ECS client not initialized")
            
        try:
            # Task definition and cluster names
            cluster = f"{getattr(settings, 'project_name', 'neobotnet-v2')}-{getattr(settings, 'environment', 'dev')}-cluster"
            task_definition = f"{getattr(settings, 'project_name', 'neobotnet-v2')}-{getattr(settings, 'environment', 'dev')}-subfinder"
            
            # Debug logging
            print(f"DEBUG: cluster = '{cluster}'")
            print(f"DEBUG: task_definition = '{task_definition}'")
            print(f"DEBUG: cluster repr = {repr(cluster)}")
            print(f"DEBUG: task_definition repr = {repr(task_definition)}")
            
            response = self.ecs_client.run_task(
                cluster=cluster,
                taskDefinition=task_definition,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': [
                            'subnet-0e079267d68d89d83',  # us-east-1a public subnet (current VPC)
                            'subnet-00dd7e59a4c2acddf',  # us-east-1b public subnet (current VPC)
                        ],
                        'securityGroups': [
                            'sg-01607c94e2d82ca08',  # neobotnet-v2-dev-ecs-tasks security group (current VPC)
                        ],
                        'assignPublicIp': 'ENABLED'  # Needed for internet access to fetch subdomains
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': 'subfinder',
                            'command': [job_id, domain],
                            'environment': [
                                {
                                    'name': 'REDIS_HOST',
                                    'value': getattr(settings, 'redis_host', 'localhost')
                                },
                                {
                                    'name': 'REDIS_PORT', 
                                    'value': str(getattr(settings, 'redis_port', 6379))
                                },
                                {
                                    'name': 'SUPABASE_URL',
                                    'value': getattr(settings, 'supabase_url', '')
                                },
                                {
                                    'name': 'SUPABASE_SERVICE_ROLE_KEY',
                                    'value': getattr(settings, 'supabase_service_role_key', '')
                                }
                            ]
                        }
                    ]
                },
                tags=[
                    {
                        'key': 'JobId',
                        'value': job_id
                    },
                    {
                        'key': 'Domain',
                        'value': domain
                    },
                    {
                        'key': 'Purpose',
                        'value': 'SubdomainScan'
                    }
                ]
            )
            
            task_arn = response['tasks'][0]['taskArn'] if response.get('tasks') else None
            if task_arn:
                # Store task ARN in Redis for tracking
                redis_client = await self.get_redis()
                if redis_client:
                    await redis_client.hset(f"job:{job_id}", "task_arn", task_arn)
                
                return True
            else:
                raise Exception("Failed to start ECS task - no task ARN returned")
                
        except Exception as e:
            raise Exception(f"Failed to run subfinder task: {str(e)}")
    
    async def start_subdomain_scan(
        self,
        domain: str,
        user_id: str,
        modules: Optional[List[ReconModule]] = None
    ) -> Dict[str, Any]:
        """
        Start a subdomain enumeration scan with multi-module support.
        
        ⚠️  DEPRECATED: Use asset_service.enhanced_scan_asset_request() instead
        
        Args:
            domain: Domain to scan
            user_id: User ID for quota tracking
            modules: List of reconnaissance modules to run
            
        Returns:
            Scan job information
        """
        # 📊 LOG: Track method usage for cleanup verification
        logger.warning(
            "⚠️  DEPRECATED: start_subdomain_scan() called | "
            f"timestamp={datetime.utcnow().isoformat()} | "
            f"domain={domain} | "
            f"user_id={user_id} | "
            f"modules={[m.value for m in modules] if modules else ['subfinder']} | "
            "action=START_SCAN | "
            "caller=recon_service | "
            "message=Use asset_service.enhanced_scan_asset_request() instead"
        )
        # Check scan quota before starting
        usage_service = get_usage_service()
        await usage_service.enforce_scan_quota(uuid.UUID(user_id))
        
        if modules is None:
            modules = [ReconModule.SUBFINDER]  # Default to subfinder for backward compatibility
            
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create scan job in database
        scan_job = {
            "id": job_id,
            "user_id": user_id,
            "domain": domain,
            "scan_type": "subdomain",
            "modules": [mod.value for mod in modules],
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            # Save to Supabase
            response = self.supabase.table("scan_jobs").insert(scan_job).execute()
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create scan job"
                )
            
            # Try to add to Redis queue if available
            redis_client = await self.get_redis()
            if redis_client:
                await redis_client.hset(f"job:{job_id}", mapping={
                    "domain": domain,
                    "user_id": user_id,
                    "modules": safe_json_dumps([mod.value for mod in modules]),
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat()
                })
            
            # Start distributed reconnaissance workflow
            try:
                if len(modules) == 1 and modules[0] == ReconModule.SUBFINDER:
                    # Single subfinder - use existing optimized path
                    await self._run_subfinder_task(domain, job_id)
                    scan_message = "Subdomain scan started successfully on AWS ECS"
                else:
                    # Multiple modules - use workflow orchestrator
                    workflow_result = await workflow_orchestrator.start_reconnaissance(
                        domain=domain,
                        modules=modules,
                        job_id=job_id
                    )
                    scan_message = f"Distributed reconnaissance started with {len(modules)} module(s)"
                    
            except Exception as e:
                # Update status to failed in both Redis and database
                if redis_client:
                    await redis_client.hset(f"job:{job_id}", "status", "failed")
                
                # Update database
                self.supabase.table("scan_jobs").update({
                    "status": "failed",
                    "error_message": str(e)
                }).eq("id", job_id).execute()
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start scan task: {str(e)}"
                )
            
            return {
                "job_id": job_id,
                "domain": domain,
                "modules": [mod.value for mod in modules],
                "status": "pending",
                "message": scan_message
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start scan: {str(e)}"
            )

    async def get_job_status(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Get the status of a scan job."""
        try:
            # First try Redis for real-time status
            redis_client = await self.get_redis()
            if redis_client:
                job_data = await redis_client.hgetall(f"job:{job_id}")
                if job_data:
                    # Get subdomains from Redis
                    subdomains = await redis_client.smembers(f"subdomains:{job_id}")
                    job_data['subdomains'] = list(subdomains) if subdomains else []
                    job_data['total_subdomains'] = len(job_data['subdomains'])
                    return job_data
            
            # Fallback to database - check both scan_jobs and asset_scan_jobs for compatibility
            response = self.supabase.table("scan_jobs").select("*").eq("id", job_id).eq("user_id", user_id).execute()
            
            # If not found in scan_jobs, try asset_scan_jobs (for new scans)
            if not response.data:
                response = self.supabase.table("asset_scan_jobs").select("*").eq("id", job_id).eq("user_id", user_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            job = response.data[0]
            
            # Get basic subdomains from database (for backward compatibility)
            subdomains_response = self.supabase.table("subdomains").select("*").eq("scan_job_id", job_id).execute()
            subdomains = [sub['subdomain'] for sub in subdomains_response.data] if subdomains_response.data else []
            
            return {
                **job,
                "subdomains": subdomains,
                "total_subdomains": len(subdomains)
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get job status: {str(e)}"
            )

    async def get_enhanced_subdomains(self, job_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get enhanced subdomains with full metadata including SSL certificates and source attribution."""
        try:
            # Verify job ownership - check both scan_jobs and asset_scan_jobs for compatibility  
            response = self.supabase.table("scan_jobs").select("id,domain").eq("id", job_id).eq("user_id", user_id).execute()
            
            # If not found in scan_jobs, try asset_scan_jobs (for new scans)
            if not response.data:
                response = self.supabase.table("asset_scan_jobs").select("id,asset_id").eq("id", job_id).eq("user_id", user_id).execute()
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            # Get all subdomain data with full metadata
            subdomains_response = self.supabase.table("subdomains").select("*").eq("scan_job_id", job_id).execute()
            
            if not subdomains_response.data:
                return []
            
            # Transform database records to enhanced subdomain format
            enhanced_subdomains = []
            for sub in subdomains_response.data:
                enhanced = {
                    "id": sub.get("id"),
                    "subdomain": sub.get("subdomain"),
                    "scan_job_id": sub.get("scan_job_id"),
                    "discovered_at": sub.get("discovered_at"),
                    "last_checked": sub.get("last_checked"),
                    
                    # IP and technical data
                    "ip_addresses": sub.get("ip_addresses", []),
                    "status_code": sub.get("status_code"),
                    "response_size": sub.get("response_size"),
                    "technologies": sub.get("technologies", []),
                    
                    # Source attribution
                    "source_module": sub.get("source_module", "subfinder"),
                    "source_ip_range": sub.get("source_ip_range"),
                    "cloud_provider": sub.get("cloud_provider"),
                    "discovery_method": sub.get("discovery_method"),
                    
                    # SSL Certificate information
                    "ssl_subject_cn": sub.get("ssl_subject_cn"),
                    "ssl_issuer": sub.get("ssl_issuer"),
                    "ssl_valid_from": sub.get("ssl_valid_from"),
                    "ssl_valid_until": sub.get("ssl_valid_until"),
                    "ssl_serial_number": sub.get("ssl_serial_number"),
                    "ssl_is_wildcard": sub.get("ssl_is_wildcard", False),
                    "ssl_is_valid": sub.get("ssl_is_valid", True),
                    "ssl_is_expired": sub.get("ssl_is_expired", False),
                    "ssl_days_until_expiry": sub.get("ssl_days_until_expiry"),
                }
                
                # Remove None values to clean up the response
                enhanced = {k: v for k, v in enhanced.items() if v is not None}
                enhanced_subdomains.append(enhanced)
            
            return enhanced_subdomains
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get enhanced subdomains: {str(e)}"
            )

    async def get_job_progress(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Get detailed real-time progress for a scan job."""
        try:
            # Verify job ownership
            response = self.supabase.table("scan_jobs").select("id,domain,status,created_at").eq("id", job_id).eq("user_id", user_id).execute()
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            job_info = response.data[0]
            
            # Get real-time progress from Redis
            redis_client = await self.get_redis()
            progress_data = {}
            
            if redis_client:
                # Get detailed progress from the cloud-ssl-analyzer progress tracking
                progress_key = f"job:progress:{job_id}"
                progress_data = await redis_client.hgetall(progress_key)
                
                if progress_data:
                    # Convert numeric fields
                    numeric_fields = [
                        'total_ip_ranges', 'processed_ip_ranges', 'total_results', 
                        'filtered_results', 'stored_batches', 'database_writes', 
                        'database_failures', 'memory_usage_mb', 'active_workers',
                        'total_errors', 'recoverable_errors', 'fatal_errors'
                    ]
                    for field in numeric_fields:
                        if field in progress_data:
                            try:
                                progress_data[field] = int(progress_data[field])
                            except (ValueError, TypeError):
                                progress_data[field] = 0
                    
                    # Convert float fields
                    float_fields = ['progress_percent', 'db_success_rate']
                    for field in float_fields:
                        if field in progress_data:
                            try:
                                progress_data[field] = float(progress_data[field])
                            except (ValueError, TypeError):
                                progress_data[field] = 0.0
            
            # If no progress data, provide basic status
            if not progress_data:
                progress_data = {
                    "current_phase": job_info.get("status", "unknown"),
                    "progress_percent": 0.0,
                    "total_results": 0,
                    "filtered_results": 0,
                    "database_writes": 0,
                    "database_failures": 0,
                    "db_success_rate": 100.0,
                    "memory_usage_mb": 0,
                    "total_errors": 0
                }
            
            return {
                "job_id": job_id,
                "domain": job_info["domain"],
                "status": job_info["status"],
                "created_at": job_info["created_at"],
                "progress": progress_data
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get job progress: {str(e)}"
            )

    async def get_job_errors(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Get detailed error information for a scan job."""
        try:
            # Verify job ownership
            response = self.supabase.table("scan_jobs").select("id,domain,error_message").eq("id", job_id).eq("user_id", user_id).execute()
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            job_info = response.data[0]
            
            # Get error details from Redis progress tracking
            redis_client = await self.get_redis()
            error_data = {
                "job_id": job_id,
                "domain": job_info["domain"],
                "database_error": job_info.get("error_message"),
                "total_errors": 0,
                "recoverable_errors": 0,
                "fatal_errors": 0,
                "errors_by_type": {},
                "recent_errors": []
            }
            
            if redis_client:
                progress_key = f"job:progress:{job_id}"
                progress_data = await redis_client.hgetall(progress_key)
                
                if progress_data:
                    # Extract error information
                    for field in ['total_errors', 'recoverable_errors', 'fatal_errors']:
                        if field in progress_data:
                            try:
                                error_data[field] = int(progress_data[field])
                            except (ValueError, TypeError):
                                error_data[field] = 0
                    
                    # Parse errors_by_type if it exists
                    if 'errors_by_type' in progress_data:
                        try:
                            error_data['errors_by_type'] = json.loads(progress_data['errors_by_type'])
                        except (json.JSONDecodeError, TypeError):
                            error_data['errors_by_type'] = {}
                    
                    # Parse recent_errors if it exists
                    if 'recent_errors' in progress_data:
                        try:
                            error_data['recent_errors'] = json.loads(progress_data['recent_errors'])
                        except (json.JSONDecodeError, TypeError):
                            error_data['recent_errors'] = []
            
            return error_data
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get job errors: {str(e)}"
            )

    async def stream_job_progress(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Get real-time streaming progress data optimized for live monitoring."""
        try:
            # Verify job ownership
            response = self.supabase.table("scan_jobs").select("id,domain,status,created_at").eq("id", job_id).eq("user_id", user_id).execute()
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            job_info = response.data[0]
            
            # Get minimal progress data for streaming
            redis_client = await self.get_redis()
            if redis_client:
                progress_key = f"job:progress:{job_id}"
                
                # Get specific fields optimized for streaming
                streaming_fields = [
                    'current_phase', 'progress_percent', 'total_results', 
                    'filtered_results', 'database_writes', 'database_failures',
                    'memory_usage_mb', 'estimated_eta', 'last_update_time'
                ]
                
                progress_data = {}
                for field in streaming_fields:
                    value = await redis_client.hget(progress_key, field)
                    if value is not None:
                        # Convert numeric fields
                        if field in ['total_results', 'filtered_results', 'database_writes', 'database_failures', 'memory_usage_mb']:
                            try:
                                progress_data[field] = int(value)
                            except (ValueError, TypeError):
                                progress_data[field] = 0
                        elif field == 'progress_percent':
                            try:
                                progress_data[field] = float(value)
                            except (ValueError, TypeError):
                                progress_data[field] = 0.0
                        else:
                            progress_data[field] = value
                
                # Calculate streaming metrics
                total_db_attempts = progress_data.get('database_writes', 0) + progress_data.get('database_failures', 0)
                db_success_rate = 100.0
                if total_db_attempts > 0:
                    db_success_rate = (progress_data.get('database_writes', 0) / total_db_attempts) * 100
                
                progress_data['db_success_rate'] = round(db_success_rate, 1)
                progress_data['total_db_attempts'] = total_db_attempts
                
                return {
                    "job_id": job_id,
                    "domain": job_info["domain"],
                    "status": job_info["status"],
                    "streaming_progress": progress_data,
                    "last_update": datetime.now().isoformat()
                }
            
            # Fallback for no Redis data
            return {
                "job_id": job_id,
                "domain": job_info["domain"],
                "status": job_info["status"],
                "streaming_progress": {
                    "current_phase": job_info["status"],
                    "progress_percent": 0.0,
                    "total_results": 0,
                    "database_writes": 0,
                    "memory_usage_mb": 0
                },
                "last_update": datetime.now().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stream job progress: {str(e)}"
            )

    async def list_jobs(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List scan jobs for a user."""
        try:
            response = self.supabase.table("scan_jobs").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list jobs: {str(e)}"
            )

    # ============================================================================
    # CLEANUP NOTE (2025-10-06): Removed cloud_ssl-specific methods
    # ============================================================================
    # The following methods were removed as they were ONLY used for cloud_ssl module:
    # - sync_redis_to_database() - Main Redis-to-DB sync method
    # - _process_batch_to_database() - Batch processing helper
    # - _convert_scan_result_to_supabase() - cloud_ssl result formatter
    # - _is_ssl_expired() - SSL expiry checker
    # - _calculate_days_until_expiry() - SSL expiry calculator
    #
    # Total: ~230 lines of cloud_ssl-only code eliminated
    #
    # These were part of the cloud_ssl Redis-to-Database sync workflow.
    # Subfinder uses a direct-to-database approach via Go containers.
    # Future modules (HTTPX, DNS) will follow subfinder's pattern.
    # ============================================================================


# Create a global instance of the service
recon_service = ReconService() 