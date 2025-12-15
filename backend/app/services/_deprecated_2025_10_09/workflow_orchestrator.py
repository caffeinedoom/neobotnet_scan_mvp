"""
Workflow Orchestrator for Distributed Reconnaissance
==================================================

Manages simultaneous execution of multiple reconnaissance modules
with Redis coordination and real-time status updates.
"""
import uuid
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from ..utils.json_encoder import safe_json_dumps

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
from ..schemas.recon import ReconModule, WorkflowStatus

# ⚠️ DEPRECATION LOGGING - Track usage before removal
import logging
import warnings

logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    """Orchestrates distributed reconnaissance workflows."""
    
    def __init__(self):
        # 🚨 DEPRECATION WARNING - This orchestrator is being phased out
        warnings.warn(
            "WorkflowOrchestrator is deprecated and will be removed. "
            "Use batch_workflow_orchestrator for all scans.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # 📊 LOG: Track instantiation for cleanup verification
        logger.warning(
            "⚠️  DEPRECATED: WorkflowOrchestrator instantiated | "
            f"timestamp={datetime.utcnow().isoformat()} | "
            "action=INIT | "
            "message=This class is deprecated, use batch_workflow_orchestrator"
        )
        
        self.redis_client = None
        self.ecs_client = None
        self._init_aws_clients()
        
        # Module configuration mapping
        # CLEANUP NOTE (2025-10-06): Removed CLOUD_SSL configuration
        self.module_configs = {
            ReconModule.SUBFINDER: {
                "task_definition": f"{getattr(settings, 'project_name', 'neobotnet-v2')}-{getattr(settings, 'environment', 'dev')}-subfinder",
                "container_name": "subfinder",
                "cpu": 256,
                "memory": 512,
                "estimated_duration": 120,  # 2 minutes per domain (will scale with domain count)
                "supports_multi_domain": True  # Go container supports multiple domains efficiently
            },
            # Future modules will be added here as they are implemented:
            # ReconModule.DNS_BRUTEFORCE: { ... },
            # ReconModule.HTTP_PROBE: { ... },
        }
    
    def _init_aws_clients(self):
        """Initialize AWS clients."""
        if boto3 is None:
            print("Warning: boto3 not available, ECS tasks will be disabled")
            return
            
        try:
            self.ecs_client = boto3.client('ecs', region_name='us-east-1')
            # Test AWS credentials
            sts_client = boto3.client('sts', region_name='us-east-1')
            sts_client.get_caller_identity()
        except (ClientError, NoCredentialsError) as e:
            print(f"AWS client initialization failed: {str(e)}")
            self.ecs_client = None
    
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
                await self.redis_client.ping()
            except Exception as e:
                print(f"Redis connection failed: {str(e)}")
                self.redis_client = None
        return self.redis_client

    async def start_reconnaissance(self, domain: str, modules: List[ReconModule], job_id: str) -> Dict[str, Any]:
        """
        Start distributed reconnaissance workflow.
        
        Args:
            domain: Target domain
            modules: List of reconnaissance modules to execute
            job_id: Unique job identifier
            
        Returns:
            Workflow status and task information
        """
        # 📊 LOG: Track method usage for cleanup verification
        logger.warning(
            "⚠️  DEPRECATED: start_reconnaissance() called | "
            f"timestamp={datetime.utcnow().isoformat()} | "
            f"domain={domain} | "
            f"modules={[m.value for m in modules]} | "
            f"job_id={job_id} | "
            "action=START_RECON | "
            "message=Use batch_workflow_orchestrator.execute_optimized_asset_scans() instead"
        )
        
        if not self.ecs_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ECS client not available"
            )
        
        redis_client = await self.get_redis()
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis connection not available"
            )
        
        try:
            # 1. Initialize workflow state in Redis
            await self._init_workflow_state(redis_client, job_id, domain, modules)
            
            # 2. Launch containers simultaneously
            container_tasks = await self._launch_containers(domain, modules, job_id)
            
            # 3. Set up monitoring task (non-blocking)
            asyncio.create_task(self._monitor_workflow(job_id, container_tasks))
            
            # 4. Calculate estimated completion
            estimated_completion = self._calculate_estimated_completion(modules)
            
            return {
                "job_id": job_id,
                "domain": domain,
                "modules": [mod.value for mod in modules],
                "total_containers": len(container_tasks),
                "launched_containers": len([t for t in container_tasks if t is not None]),
                "estimated_completion": estimated_completion,
                "status": "running"
            }
            
        except Exception as e:
            # Update workflow status to failed
            await redis_client.hset(f"workflow:{job_id}", "status", "failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start reconnaissance workflow: {str(e)}"
            )

    async def _init_workflow_state(self, redis_client, job_id: str, domain: str, modules: List[ReconModule]):
        """Initialize workflow state in Redis."""
        workflow_data = {
            "domain": domain,
            "modules": safe_json_dumps([mod.value for mod in modules]),
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "total_modules": len(modules),
            "completed_modules": 0
        }
        
        # Set workflow state
        await redis_client.hset(f"workflow:{job_id}", mapping=workflow_data)
        
        # Initialize module status
        for module in modules:
            await redis_client.hset(f"module_status:{job_id}", module.value, "pending")
        
        # Initialize result sets
        await redis_client.delete(f"subdomains:{job_id}")  # Clear any existing data
        await redis_client.delete(f"subdomain_sources:{job_id}")

    async def _launch_containers(self, domain: str, modules: List[ReconModule], job_id: str) -> List[Optional[str]]:
        """Launch ECS containers for all modules simultaneously."""
        cluster = f"{getattr(settings, 'project_name', 'neobotnet-v2')}-{getattr(settings, 'environment', 'dev')}-cluster"
        
        tasks = []
        for module in modules:
            if module not in self.module_configs:
                print(f"Warning: Module {module.value} not yet implemented, skipping")
                tasks.append(None)
                continue
                
            try:
                task_arn = await self._launch_single_container(cluster, module, domain, job_id)
                tasks.append(task_arn)
                print(f"✅ Launched {module.value} container: {task_arn}")
            except Exception as e:
                print(f"❌ Failed to launch {module.value} container: {str(e)}")
                tasks.append(None)
                # Update module status to failed
                redis_client = await self.get_redis()
                if redis_client:
                    await redis_client.hset(f"module_status:{job_id}", module.value, "failed")
        
        return tasks

    async def _launch_single_container(self, cluster: str, module: ReconModule, domain: str, job_id: str) -> str:
        """Launch a single ECS container for a specific module."""
        config = self.module_configs[module]
        
        # Build environment variables
        environment = [
            {"name": "REDIS_HOST", "value": getattr(settings, 'redis_host', 'localhost')},
            {"name": "REDIS_PORT", "value": str(getattr(settings, 'redis_port', 6379))},
            {"name": "MODULE_TYPE", "value": module.value},
            {"name": "DOMAIN", "value": domain},
            {"name": "JOB_ID", "value": job_id}
        ]
        
        # Add module-specific environment variables
        if module == ReconModule.SUBFINDER:
            environment.extend([
                {"name": "SUPABASE_URL", "value": getattr(settings, 'supabase_url', '')},
                {"name": "SUPABASE_SERVICE_ROLE_KEY", "value": getattr(settings, 'supabase_service_role_key', '')}
            ])
        
        response = self.ecs_client.run_task(
            cluster=cluster,
            taskDefinition=config["task_definition"],
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': [
                        'subnet-0e079267d68d89d83',  # us-east-1a public subnet
                        'subnet-00dd7e59a4c2acddf',  # us-east-1b public subnet
                    ],
                    'securityGroups': ['sg-01607c94e2d82ca08'],  # ECS tasks security group
                    'assignPublicIp': 'ENABLED'
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': config["container_name"],
                        'command': [job_id, domain],
                        'environment': environment
                    }
                ]
            },
            tags=[
                {'key': 'JobId', 'value': job_id},
                {'key': 'Domain', 'value': domain},
                {'key': 'Module', 'value': module.value},
                {'key': 'Purpose', 'value': 'DistributedRecon'}
            ]
        )
        
        if not response.get('tasks'):
            raise Exception(f"No tasks returned for {module.value}")
        
        task_arn = response['tasks'][0]['taskArn']
        
        # Update module status to running
        redis_client = await self.get_redis()
        if redis_client:
            await redis_client.hset(f"module_status:{job_id}", module.value, "running")
            await redis_client.hset(f"task_arn:{job_id}", module.value, task_arn)
        
        return task_arn

    async def _monitor_workflow(self, job_id: str, container_tasks: List[Optional[str]]):
        """Monitor workflow progress and update status."""
        redis_client = await self.get_redis()
        if not redis_client:
            return
        
        # Monitor for up to 10 minutes
        timeout = 600  # 10 minutes
        check_interval = 5  # 5 seconds
        elapsed = 0
        
        while elapsed < timeout:
            try:
                # Check module statuses
                module_statuses = await redis_client.hgetall(f"module_status:{job_id}")
                
                completed = sum(1 for status in module_statuses.values() if status == "completed")
                failed = sum(1 for status in module_statuses.values() if status == "failed")
                total = len(module_statuses)
                
                # Update workflow progress
                await redis_client.hset(f"workflow:{job_id}", "completed_modules", completed)
                
                # 🔥 NEW: Check for completed subfinder module and update database
                if "subfinder" in module_statuses and module_statuses["subfinder"] == "completed":
                    # Check if we haven't already synced this job
                    subfinder_synced_key = f"subfinder_synced:{job_id}"
                    if not await redis_client.get(subfinder_synced_key):
                        print(f"🚀 Subfinder module completed for job {job_id}, updating database status...")
                        await redis_client.set(subfinder_synced_key, "true", ex=86400)  # 24h expiry
                        
                        try:
                            # Import here to avoid circular imports
                            import asyncio
                            asyncio.create_task(self._sync_subfinder_completion(job_id))
                            
                            print(f"✅ Subfinder database sync initiated for job {job_id}")
                        except Exception as e:
                            print(f"❌ Failed to trigger subfinder database sync for job {job_id}: {e}")
                
                # Check if all modules are done
                if completed + failed >= total:
                    if failed == 0:
                        await redis_client.hset(f"workflow:{job_id}", "status", "completed")
                    elif completed > 0:
                        await redis_client.hset(f"workflow:{job_id}", "status", "partial_success")
                    else:
                        await redis_client.hset(f"workflow:{job_id}", "status", "failed")
                    
                    await redis_client.hset(f"workflow:{job_id}", "completed_at", datetime.utcnow().isoformat())
                    break
                
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
            except Exception as e:
                print(f"Error monitoring workflow {job_id}: {str(e)}")
                break
        
        # Timeout handling
        if elapsed >= timeout:
            await redis_client.hset(f"workflow:{job_id}", "status", "timeout")

    async def _sync_subfinder_completion(self, job_id: str):
        """Background task to update database with subfinder completion status."""
        try:
            print(f"🔄 Starting subfinder completion sync for job {job_id}")
            
            # Get Redis progress data
            redis_client = await self.get_redis()
            if not redis_client:
                print(f"❌ Redis not available for job {job_id}")
                return
            
            # Read progress data from Redis Hash
            progress_data = await redis_client.hgetall(f"job:{job_id}")
            if not progress_data:
                print(f"⚠️ No progress data found in Redis for job {job_id}")
                return
            
            # Import Supabase service for database updates
            from ..core.database import get_supabase
            supabase = get_supabase()
            
            # Get scan completion details
            total_subdomains = int(progress_data.get("total_subdomains", 0))
            status = progress_data.get("status", "completed")
            completed_at = progress_data.get("completed_at")
            
            # 🔧 MODERNIZED: Check if this is an asset scan or individual scan
            # Look for asset scan coordination data in Redis
            asset_scan_data = await redis_client.hgetall(f"asset_scan:{job_id}")
            
            if asset_scan_data and asset_scan_data.get("asset_scan_id"):
                # This is an asset scan - update asset_scan_jobs directly
                asset_scan_id = asset_scan_data.get("asset_scan_id")
                
                print(f"🔄 Updating asset scan {asset_scan_id} completion status")
                
                # Count actual stored subdomains for this asset scan
                subdomains_result = supabase.table("subdomains").select(
                    "id", count="exact"
                ).eq("scan_job_id", asset_scan_id).execute()
                
                actual_subdomain_count = subdomains_result.count or 0
                
                # Get current asset scan to check total domains
                asset_scan_result = supabase.table("asset_scan_jobs").select(
                    "total_domains, completed_domains"
                ).eq("id", asset_scan_id).execute()
                
                if asset_scan_result.data:
                    asset_scan = asset_scan_result.data[0]
                    total_domains = asset_scan.get("total_domains", 1)
                    
                    # Update asset scan with completion
                    asset_update = {
                        "status": "completed",
                        "completed_domains": total_domains,  # Mark all domains as completed
                        "result_count": actual_subdomain_count
                    }
                    
                    if completed_at:
                        asset_update["completed_at"] = completed_at
                    
                    # Update the asset scan job
                    update_result = supabase.table("asset_scan_jobs").update(asset_update).eq("id", asset_scan_id).execute()
                    
                    if update_result.data:
                        print(f"✅ Updated asset scan {asset_scan_id}: status=completed, subdomains={actual_subdomain_count}")
                    else:
                        print(f"⚠️ Failed to update asset scan {asset_scan_id}")
                else:
                    print(f"⚠️ Asset scan {asset_scan_id} not found in database")
                    
            else:
                # Individual scan jobs no longer supported - unified asset-level orchestration only
                print(f"⚠️ Job ID {job_id} not recognized as asset scan - unified architecture requires asset_scan_id")
                
        except Exception as e:
            print(f"❌ Subfinder completion sync failed for job {job_id}: {e}")
            
            # Mark sync as failed in Redis
            redis_client = await self.get_redis()
            if redis_client:
                await redis_client.hset(f"workflow:{job_id}", "subfinder_sync_failed", str(e))

    def _calculate_estimated_completion(self, modules: List[ReconModule]) -> str:
        """Calculate estimated completion time based on modules."""
        max_duration = max(
            self.module_configs.get(module, {}).get("estimated_duration", 30)
            for module in modules
            if module in self.module_configs
        )
        
        # Add buffer for container startup and coordination
        estimated_seconds = max_duration + 60
        completion_time = datetime.utcnow() + timedelta(seconds=estimated_seconds)
        return completion_time.isoformat()

    async def get_workflow_status(self, job_id: str) -> WorkflowStatus:
        """Get current workflow status."""
        redis_client = await self.get_redis()
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis connection not available"
            )
        
        # Get workflow data
        workflow_data = await redis_client.hgetall(f"workflow:{job_id}")
        if not workflow_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found"
            )
        
        # Get module statuses
        module_statuses = await redis_client.hgetall(f"module_status:{job_id}")
        
        running_modules = [mod for mod, status in module_statuses.items() if status == "running"]
        failed_modules = [mod for mod, status in module_statuses.items() if status == "failed"]
        
        return WorkflowStatus(
            job_id=job_id,
            domain=workflow_data.get("domain", ""),
            total_modules=int(workflow_data.get("total_modules", 0)),
            completed_modules=int(workflow_data.get("completed_modules", 0)),
            running_modules=running_modules,
            failed_modules=failed_modules,
            overall_status=workflow_data.get("status", "unknown"),
            estimated_completion=workflow_data.get("estimated_completion")
        )

    async def aggregate_results(self, job_id: str) -> Dict[str, Any]:
        """Aggregate results from all modules with automatic deduplication."""
        redis_client = await self.get_redis()
        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis connection not available"
            )
        
        # Get all unique subdomains (Redis Set automatically deduplicates)
        all_subdomains = await redis_client.smembers(f"subdomains:{job_id}")
        
        # Get source attribution
        subdomain_sources = await redis_client.hgetall(f"subdomain_sources:{job_id}")
        
        # Get module-specific results
        module_results = {}
        module_statuses = await redis_client.hgetall(f"module_status:{job_id}")
        
        for module in module_statuses:
            module_results[module] = {
                "status": module_statuses[module],
                "subdomains": list(await redis_client.smembers(f"{module}_subdomains:{job_id}") or []),
                "count": await redis_client.scard(f"{module}_subdomains:{job_id}") or 0
            }
        
        return {
            "total_unique_subdomains": len(all_subdomains) if all_subdomains else 0,
            "all_subdomains": list(all_subdomains) if all_subdomains else [],
            "subdomain_sources": subdomain_sources,
            "module_results": module_results,
            "deduplication_stats": {
                "total_discovered": sum(result["count"] for result in module_results.values()),
                "unique_after_dedup": len(all_subdomains) if all_subdomains else 0,
                "duplicates_removed": sum(result["count"] for result in module_results.values()) - (len(all_subdomains) if all_subdomains else 0)
            }
        }


    # ================================================================
    # REMOVED: Unified Asset-Level Orchestration (Deprecated)
    # ================================================================
    # The following methods have been REMOVED in favor of batch_workflow_orchestrator:
    # - start_asset_scan() 
    # - _init_asset_workflow_state()
    # - _launch_asset_containers()
    # - _launch_asset_container()
    # - _monitor_asset_workflow()
    # - _calculate_asset_completion_time()
    #
    # MIGRATION: Use batch_workflow_orchestrator.execute_optimized_asset_scans() instead
    # REASON: Unified architecture always uses batch mode for ALL scans
    # ================================================================


# Global instance
workflow_orchestrator = WorkflowOrchestrator()
