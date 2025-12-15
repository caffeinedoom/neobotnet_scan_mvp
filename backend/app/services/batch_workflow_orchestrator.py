"""
Enhanced Batch Workflow Orchestrator
===================================

Intelligent ECS task orchestration with dynamic resource allocation,
cost optimization, and scalable batch processing for reconnaissance scans.

Key Improvements over original workflow_orchestrator:
• Dynamic resource allocation based on workload
• Cross-asset batch optimization
• Real-time cost tracking and optimization
• Enhanced error handling and retry logic
• Progress aggregation across batch boundaries
"""

import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging

from ..utils.json_encoder import safe_json_dumps
from .module_registry import module_registry
from .module_config_loader import get_module_config

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None

try:
    import redis.asyncio as redis
except ImportError:
    import redis

from ..core.config import settings
from ..core.supabase_client import supabase_client
from .module_registry import module_registry
from ..schemas.batch import (
    BatchScanJob, BatchStatus, BatchOptimizationRequest, 
    BatchOptimizationResult, DomainAssignmentStatus
)
from .resource_calculator import resource_calculator, ResourceAllocation
from .batch_optimizer import batch_optimizer
from .batch_execution import batch_execution_service

logger = logging.getLogger(__name__)

class BatchWorkflowOrchestrator:
    """
    Enhanced workflow orchestrator for batch reconnaissance scans.
    
    Coordinates the entire batch workflow from optimization through
    execution with intelligent resource allocation and cost optimization.
    """
    
    def __init__(self):
        self.supabase = supabase_client.service_client
        self.redis_client = None
        self.ecs_client = None
        self._init_aws_clients()
        
    def _init_aws_clients(self):
        """Initialize AWS clients for ECS and Redis."""
        try:
            if boto3:
                self.ecs_client = boto3.client(
                    'ecs',
                    region_name=getattr(settings, 'aws_region', 'us-east-1'),
                    aws_access_key_id=getattr(settings, 'aws_access_key_id', None),
                    aws_secret_access_key=getattr(settings, 'aws_secret_access_key', None)
                )
                logger.info("ECS client initialized successfully")
            else:
                logger.warning("boto3 not available - ECS operations will be mocked")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
    
    async def get_redis(self):
        """Get Redis connection for progress tracking."""
        if not self.redis_client:
            try:
                self.redis_client = redis.Redis(
                    host=getattr(settings, 'redis_host', 'localhost'),
                    port=getattr(settings, 'redis_port', 6379),
                    decode_responses=True,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry_on_timeout=True
                )
                await self.redis_client.ping()
                logger.info("Redis client connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {str(e)}")
                self.redis_client = None
        return self.redis_client
    
    async def _get_module_configuration(
        self, 
        module_name: str, 
        batch_job: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Get module configuration from registry with fallbacks.
        
        This centralizes module configuration logic and removes
        hardcoded module checks throughout the orchestrator.
        
        Args:
            module_name: Name of the module (e.g., "subfinder", "dnsx")
            batch_job: Optional batch job for context-specific config
            
        Returns:
            Dict with module configuration:
            {
                "module_profile": ModuleProfile object,
                "task_role_arn": str,
                "container_name": str,
                "resource_requirements": dict,
                "optimization_hints": dict
            }
            
        Raises:
            ValueError: If module not found in registry
            
        Example:
            >>> config = await orchestrator._get_module_configuration("dnsx")
            >>> print(config["container_name"])  # "dnsx-go"
            >>> print(config["optimization_hints"])  # {"requires_database_fetch": true}
        """
        # Get module from registry
        module_profile = await module_registry.get_module(module_name)
        if not module_profile:
            # Get list of available modules for helpful error message
            try:
                available = await module_registry.list_active_modules()
                available_str = ", ".join(available) if available else "none"
            except Exception:
                available_str = "unknown"
            
            raise ValueError(
                f"Module '{module_name}' not found in registry. "
                f"Available modules: {available_str}. "
                f"Please register the module in scan_module_profiles table."
            )
        
        # Build configuration dict
        config = {
            "module_profile": module_profile,
            "container_name": module_profile.container_name,
            "resource_requirements": module_profile.resource_scaling,
            "optimization_hints": module_profile.optimization_hints or {}
        }
        
        # Extract task role ARN
        config["task_role_arn"] = (
            config["optimization_hints"].get("task_role_arn") or
            settings.ecs_task_role_arn
        )
        
        # Add batch-specific overrides if provided
        if batch_job and batch_job.get("metadata"):
            overrides = batch_job["metadata"].get("module_config_overrides", {})
            if overrides:
                logger.debug(f"Applying config overrides for {module_name}: {overrides}")
                config.update(overrides)
        
        logger.debug(
            f"Module configuration for '{module_name}': "
            f"container={config['container_name']}, "
            f"role_arn={config['task_role_arn'][:20]}..., "
            f"hints={list(config['optimization_hints'].keys())}"
        )
        
        return config
    
    async def execute_optimized_asset_scans(
        self, 
        asset_scan_requests: List[Dict[str, Any]], 
        modules: List[str],
        user_id: str,
        priority: int = 1
    ) -> Dict[str, Any]:
        """
        Execute optimized batch scans for multiple assets.
        
        This is the main entry point that replaces the individual
        asset scan workflow with intelligent batch processing.
        
        Args:
            asset_scan_requests: List of asset scan requests
            modules: Scan modules to execute
            user_id: User ID for tracking
            priority: Priority level (1=highest, 5=lowest)
            
        Returns:
            Execution summary with batch details and cost analysis
        """
        try:
            start_time = datetime.utcnow()
            logger.info(f"Starting optimized batch execution for {len(asset_scan_requests)} assets")
            
            # Step 1: Optimize asset scans into efficient batches
            optimization_request = BatchOptimizationRequest(
                asset_scan_requests=asset_scan_requests,
                modules=modules,
                priority=priority,
                user_id=uuid.UUID(user_id)
            )
            
            optimization_result = await batch_optimizer.optimize_scans(optimization_request)
            
            logger.info(f"Optimization complete: {optimization_result.total_batches} batches, "
                       f"{optimization_result.estimated_cost_savings_percent:.1f}% cost savings")
            
            # Step 2: Create batch jobs in database
            batch_creation_result = await batch_execution_service.create_batch_jobs(optimization_result.batch_jobs)
            batch_ids = batch_creation_result["batch_ids"]
            asset_scan_ids = batch_creation_result["asset_scan_ids"]  # 🔧 OPTION B: Extract asset_scan_ids
            
            # Step 3: Calculate enhanced resource allocations
            enhanced_allocations = await self._calculate_enhanced_allocations(
                optimization_result.batch_jobs, priority
            )
            
            # Step 4: Launch ECS tasks with optimized resources
            launch_results = await self._launch_batch_tasks(
                optimization_result.batch_jobs, enhanced_allocations
            )
            
            # Step 5: Initialize progress tracking
            await self._initialize_batch_progress_tracking(
                optimization_result.batch_jobs, user_id
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Step 6: Return comprehensive execution summary
            return {
                "execution_id": str(uuid.uuid4()),
                "batch_count": optimization_result.total_batches,
                "total_domains": optimization_result.total_domains,
                "estimated_cost_savings_percent": optimization_result.estimated_cost_savings_percent,
                "estimated_duration_minutes": optimization_result.estimated_duration_minutes,
                "optimization_strategy": optimization_result.optimization_strategy,
                "batch_ids": batch_ids,
                "asset_scan_ids": asset_scan_ids,  # 🔧 OPTION B: Include asset_scan_ids for asset_service
                "launch_results": launch_results,
                "enhanced_allocations": [alloc.__dict__ for alloc in enhanced_allocations],
                "execution_time_seconds": execution_time,
                "status": "launched",
                "created_at": start_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Batch execution failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Batch execution failed: {str(e)}"
            )
    
    async def launch_module_task(
        self,
        batch_job: BatchScanJob,
        resource_allocation: Optional[ResourceAllocation] = None
    ) -> Dict[str, Any]:
        """
        Launch an ECS task for a single scan module.
        
        This method is the proper public API entry point for launching individual 
        module tasks. It's designed for use by ScanPipeline and other services that 
        need direct task execution without the overhead of multi-asset batch optimization.
        
        This method maintains architectural integrity by ensuring BatchWorkflowOrchestrator
        remains the ONLY service responsible for ECS task launching.
        
        Args:
            batch_job: BatchScanJob Pydantic model with complete task configuration
                      including module name, domains, resource allocation, metadata, etc.
            resource_allocation: Optional custom ResourceAllocation to override batch_job
                               defaults. If None, uses batch_job.allocated_cpu and 
                               batch_job.allocated_memory.
        
        Returns:
            Dict with task launch result containing:
            {
                "batch_id": str,           # Batch job ID
                "task_arn": str,           # ECS task ARN (or mock ARN if ECS unavailable)
                "status": str,             # Launch status ("launched" or "mock_launched")
                "cpu": int,                # Allocated CPU units
                "memory": int              # Allocated memory in MB
            }
        
        Raises:
            Exception: If ECS task launch fails (propagated from _launch_single_batch_task)
        
        Usage Example:
            # From ScanPipeline._execute_module()
            from app.schemas.batch import BatchScanJob
            
            batch_job = BatchScanJob(**batch_job_record)
            result = await batch_workflow_orchestrator.launch_module_task(batch_job)
            
            task_arn = result["task_arn"]
            logger.info(f"Task launched: {task_arn}")
        
        Note:
            This method is intentionally lightweight - it delegates directly to 
            _launch_single_batch_task() without optimization overhead. For multi-asset
            batch optimization with cost analysis, use execute_optimized_asset_scans().
        """
        logger.info(
            f"🚀 Launching module task via public API: "
            f"module={batch_job.module}, batch_id={batch_job.id}, "
            f"domains={batch_job.total_domains}"
        )
        
        # Delegate to internal task launcher
        # This maintains single responsibility while providing clean public API
        result = await self._launch_single_batch_task(batch_job, resource_allocation)
        
        logger.info(
            f"✅ Module task launched successfully: "
            f"batch_id={result.get('batch_id')}, "
            f"task_arn={result.get('task_arn')}, "
            f"status={result.get('status')}"
        )
        
        return result
    
    async def _calculate_enhanced_allocations(
        self, 
        batch_jobs: List[BatchScanJob], 
        priority: int
    ) -> List[ResourceAllocation]:
        """Calculate enhanced resource allocations for all batch jobs."""
        
        allocations = []
        
        for batch_job in batch_jobs:
            try:
                allocation = await resource_calculator.calculate_resources(
                    module_name=batch_job.module,
                    domain_count=batch_job.total_domains,
                    priority=priority,
                    cost_optimization=True
                )
                allocations.append(allocation)
                
                logger.info(f"Enhanced allocation for batch {batch_job.id}: "
                           f"{allocation.cpu} CPU, {allocation.memory}MB, "
                           f"${allocation.cost_estimate.estimated_total_cost:.4f}")
                
            except Exception as e:
                logger.error(f"Failed to calculate allocation for batch {batch_job.id}: {str(e)}")
                # Use the basic allocation from batch optimization as fallback
                allocations.append(None)
        
        return allocations
    
    async def _launch_batch_tasks(
        self, 
        batch_jobs: List[BatchScanJob], 
        allocations: List[ResourceAllocation]
    ) -> List[Dict[str, Any]]:
        """Launch ECS tasks for all batch jobs with optimized resources."""
        
        launch_results = []
        
        for i, batch_job in enumerate(batch_jobs):
            allocation = allocations[i] if i < len(allocations) and allocations[i] else None
            
            try:
                result = await self._launch_single_batch_task(batch_job, allocation)
                launch_results.append(result)
                
                # Update batch job with ECS task ARN
                if result.get("task_arn"):
                    await batch_execution_service._update_batch_job(str(batch_job.id), {
                        "ecs_task_arn": result["task_arn"],
                        "status": BatchStatus.RUNNING.value,
                        "started_at": datetime.utcnow().isoformat()
                    })
                
            except Exception as e:
                logger.error(f"Failed to launch batch {batch_job.id}: {str(e)}")
                launch_results.append({
                    "batch_id": str(batch_job.id),
                    "status": "failed",
                    "error": str(e)
                })
                
                # Update batch status to failed
                await batch_execution_service._update_batch_status(
                    str(batch_job.id), BatchStatus.FAILED, {"error_message": str(e)}
                )
        
        return launch_results
    
    async def _launch_single_batch_task(
        self, 
        batch_job: BatchScanJob, 
        allocation: Optional[ResourceAllocation]
    ) -> Dict[str, Any]:
        """Launch a single ECS task for a batch job."""
        
        if not self.ecs_client:
            logger.warning("ECS client not available - returning mock result")
            return {
                "batch_id": str(batch_job.id),
                "task_arn": f"arn:aws:ecs:us-east-1:123456789012:task/mock-{batch_job.id}",
                "status": "mock_launched",
                "cpu": allocation.cpu if allocation else batch_job.allocated_cpu,
                "memory": allocation.memory if allocation else batch_job.allocated_memory
            }
        
        try:
            # Use enhanced allocation if available, otherwise fall back to batch job allocation
            cpu = allocation.cpu if allocation else batch_job.allocated_cpu
            memory = allocation.memory if allocation else batch_job.allocated_memory
            
            # Get task definition for the module
            task_definition = self._get_task_definition_name(batch_job.module)
            
            # Build environment variables for the container
            environment = await self._build_container_environment(batch_job, allocation)
            
            # Launch ECS task
            response = self.ecs_client.run_task(
                cluster=self._get_cluster_name(),
                taskDefinition=task_definition,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': self._get_subnet_ids(),
                        'securityGroups': self._get_security_group_ids(),
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides={
                    'taskRoleArn': await self._get_task_role_arn(batch_job.module),
                    'executionRoleArn': self._get_execution_role_arn(),
                    'cpu': str(cpu),
                    'memory': str(memory),
                    'containerOverrides': [{
                        'name': self._get_container_name(batch_job.module),
                        'environment': environment,
                        # No 'command' key - containers use environment variables only ✅
                    }]
                },
                tags=[
                    {'key': 'BatchId', 'value': str(batch_job.id)},
                    {'key': 'Module', 'value': batch_job.module},
                    {'key': 'DomainCount', 'value': str(batch_job.total_domains)},
                    {'key': 'BatchType', 'value': batch_job.batch_type.value},
                    {'key': 'Purpose', 'value': 'BatchRecon'}
                ]
            )
            
            if not response.get('tasks'):
                raise Exception("No tasks returned from ECS")
            
            task_arn = response['tasks'][0]['taskArn']
            
            logger.info(f"Successfully launched ECS task {task_arn} for batch {batch_job.id}")
            
            return {
                "batch_id": str(batch_job.id),
                "task_arn": task_arn,
                "status": "launched",
                "cpu": cpu,
                "memory": memory,
                "cluster": self._get_cluster_name(),
                "task_definition": task_definition
            }
            
        except Exception as e:
            logger.error(f"ECS task launch failed for batch {batch_job.id}: {str(e)}")
            raise
    
    async def _build_container_environment(
        self, 
        batch_job: BatchScanJob, 
        allocation: Optional[ResourceAllocation]
    ) -> List[Dict[str, str]]:
        """
        Build STANDARD environment variables for ALL scan module containers.
        
        This method implements the Container Interface Standard (Nov 2025).
        All scan modules receive identical base environment variables,
        with module-specific extensions via MODULE_CONFIG.
        
        See: docs/container_standard/CONTAINER_INTERFACE_STANDARD.md
        """
        
        # ============================================================
        # STANDARD ENVIRONMENT VARIABLES (ALL MODULES)
        # ============================================================
        
        environment = [
            # Module identification
            {"name": "MODULE_NAME", "value": batch_job.module},
            {"name": "SCAN_JOB_ID", "value": str(batch_job.id)},
            {"name": "USER_ID", "value": str(batch_job.user_id)},
            
            # Execution mode
            {"name": "BATCH_MODE", "value": "true"},
            
            # Batch-specific context
            {"name": "BATCH_ID", "value": str(batch_job.id)},
            
            # Database connection
            {"name": "SUPABASE_URL", "value": getattr(settings, 'supabase_url', '')},
            {"name": "SUPABASE_SERVICE_ROLE_KEY", "value": getattr(settings, 'supabase_service_role_key', '')},
            
            # Redis connection (optional)
            {"name": "REDIS_HOST", "value": getattr(settings, 'redis_host', 'localhost')},
            {"name": "REDIS_PORT", "value": str(getattr(settings, 'redis_port', 6379))},
        ]
        
        # ============================================================
        # MODULE-SPECIFIC CONFIGURATION
        # ============================================================
        
        # Get module profile from registry
        module_profile = await module_registry.get_module(batch_job.module)
        if not module_profile:
            logger.warning(
                f"⚠️ Module '{batch_job.module}' not found in registry for batch {batch_job.id}. "
                f"Falling back to default behavior."
            )
            module_config = {}
        else:
            module_config = module_profile.optimization_hints or {}
        
        # Extract asset_id for database fetch modules
        asset_id = batch_job.metadata.get("asset_id") if batch_job.metadata else None
        
        # Check if module requires database fetch mode (e.g., DNSX fetching subdomains)
        if module_config.get("requires_database_fetch") and asset_id:
            # ✅ Database fetch mode with pagination
            batch_offset = batch_job.metadata.get("subdomain_batch_offset", 0)
            batch_limit = batch_job.metadata.get("subdomain_batch_limit", batch_job.total_domains)
            
            environment.extend([
                {"name": "ASSET_ID", "value": str(asset_id)},
                {"name": "BATCH_OFFSET", "value": str(batch_offset)},
                {"name": "BATCH_LIMIT", "value": str(batch_limit)},
                {"name": "FETCH_FROM_DATABASE", "value": "true"},
            ])
            
            logger.info(
                f"🔍 Module '{batch_job.module}' will fetch from database for asset {asset_id}: "
                f"offset={batch_offset}, limit={batch_limit}"
            )
        else:
            # ✅ Standard modules: Use DOMAINS from batch_domains (JSON format)
            import json
            environment.extend([
                {"name": "ASSET_ID", "value": str(asset_id) if asset_id else ""},
                {"name": "BATCH_OFFSET", "value": "0"},
                {"name": "BATCH_LIMIT", "value": str(batch_job.total_domains)},
                {"name": "DOMAINS", "value": json.dumps(batch_job.batch_domains)},  # ✅ JSON array, not CSV
            ])
        
        # ============================================================
        # BATCH JOB CONTEXT (JSON format)
        # ============================================================
        
        # ASSET_SCAN_MAPPING: Domain → asset_scan_id mapping (always include if available)
        if batch_job.asset_scan_mapping:
            import json
            environment.append({
                "name": "ASSET_SCAN_MAPPING",
                "value": json.dumps(batch_job.asset_scan_mapping)  # ✅ JSON object
            })
        
        # Module-specific config from registry (if available)
        if module_config.get("module_config"):
            import json
            environment.append({
                "name": "MODULE_CONFIG",
                "value": json.dumps(module_config["module_config"])
            })
        
        # Add resource allocation info for container optimization
        if allocation:
            environment.extend([
                {"name": "ALLOCATED_CPU", "value": str(allocation.cpu)},
                {"name": "ALLOCATED_MEMORY", "value": str(allocation.memory)},
                {"name": "ESTIMATED_DURATION", "value": str(allocation.estimated_duration_minutes)},
                {"name": "OPTIMIZATION_APPLIED", "value": allocation.optimization_applied}
            ])
        
        return environment
    
    async def _initialize_batch_progress_tracking(
        self, 
        batch_jobs: List[BatchScanJob], 
        user_id: str
    ):
        """Initialize Redis progress tracking for batch jobs."""
        
        redis_client = await self.get_redis()
        if not redis_client:
            logger.warning("Redis not available - progress tracking disabled")
            return
        
        try:
            for batch_job in batch_jobs:
                # Initialize batch progress in Redis
                await redis_client.hset(f"batch_progress:{batch_job.id}", mapping={
                    "status": BatchStatus.RUNNING.value,
                    "total_domains": batch_job.total_domains,
                    "completed_domains": 0,
                    "failed_domains": 0,
                    "started_at": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "module": batch_job.module
                })
                
                # Set expiration (24 hours)
                await redis_client.expire(f"batch_progress:{batch_job.id}", 86400)
                
            logger.info(f"Initialized Redis progress tracking for {len(batch_jobs)} batch jobs")
            
        except Exception as e:
            logger.error(f"Failed to initialize progress tracking: {str(e)}")
    
    # Configuration helper methods
    def _get_cluster_name(self) -> str:
        """Get ECS cluster name."""
        project = getattr(settings, 'project_name', 'neobotnet-v2')
        env = getattr(settings, 'environment', 'dev')
        return f"{project}-{env}-cluster"
    
    def _get_task_definition_name(self, module: str) -> str:
        """Get batch-enabled task definition name for a module."""
        project = getattr(settings, 'project_name', 'neobotnet-v2')
        env = getattr(settings, 'environment', 'dev')
        # 🔧 FIX: Use batch-enabled task definitions for proper container execution
        return f"{project}-{env}-{module}-batch"
    
    def _get_container_name(self, module: str) -> str:
        """
        Get ECS container name for a module.
        
        Loads from scan_module_profiles.container_name via ModuleConfigLoader.
        This eliminates Layer 7 of the 7-layer issue.
        
        Args:
            module: Module name (e.g., 'httpx')
            
        Returns:
            Container name (e.g., 'httpx-scanner')
        """
        return get_module_config().get_container_name(module)
    
    def _get_subnet_ids(self) -> List[str]:
        """Get subnet IDs for ECS tasks."""
        return [
            'subnet-0e079267d68d89d83',  # us-east-1a public subnet
            'subnet-00dd7e59a4c2acddf',  # us-east-1b public subnet
        ]
    
    def _get_security_group_ids(self) -> List[str]:
        """Get security group IDs for ECS tasks."""
        return ['sg-04fd4ee68cb17298d']  # ECS tasks security group (ALB-compatible)
    
    async def _get_task_role_arn(self, module: str = None) -> str:
        """
        Get task role ARN for the specific module.
        
        Uses database-driven configuration from module optimization_hints.
        Falls back to settings if not configured in database.
        """
        role_arn = None
        
        # Try to get module-specific role from database
        if module:
            try:
                module_profile = await module_registry.get_module(module)
                if module_profile and module_profile.optimization_hints:
                    role_arn = module_profile.optimization_hints.get("task_role_arn")
                    if role_arn:
                        logger.debug(f"Using task role from database for {module}: {role_arn}")
            except Exception as e:
                logger.warning(f"Could not fetch module profile for {module}: {e}")
        
        # Fallback to default role ARN if not configured in module registry
        if not role_arn:
            role_arn = settings.ecs_task_role_arn
            logger.debug(f"Using default task role ARN for module '{module}': {role_arn}")
        
        # Safety check for cloud deployment
        if not role_arn:
            logger.warning(f"⚠️ No task role ARN configured for module '{module}' - containers may fail")
        
        return role_arn
    
    def _get_execution_role_arn(self) -> str:
        """Get the ECS execution role ARN from settings."""
        # 🔧 FIX: Use configured execution role ARN for container startup
        role_arn = settings.ecs_task_execution_role_arn
        
        # Safety check for cloud deployment
        if not role_arn:
            logger.warning("⚠️ No execution role ARN configured - containers may fail to start")
        return role_arn

    def _debug_asset_scan_mapping_before_serialization(self, asset_scan_mapping: Dict[str, Any]) -> str:
        """
        🔍 DIAGNOSTIC METHOD - Debug asset_scan_mapping before serialization.
        
        This helps us validate our hypothesis that UUID objects are causing 
        the 'Object of type UUID is not JSON serializable' error.
        
        ⚠️ TECHNICAL DEBT NOTE: 
        ECS environment variables have a 4KB limit per task. For assets with 150+ 
        parent domains, consider refactoring to use Redis or database lookup instead.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("🔍 DEBUGGING: Analyzing asset_scan_mapping content")
            logger.info(f"🔍 Mapping type: {type(asset_scan_mapping)}")
            logger.info(f"🔍 Mapping keys count: {len(asset_scan_mapping) if asset_scan_mapping else 0}")
            
            # Check each value for UUID objects
            debug_info = []
            debug_mapping = {}
            
            for key, value in asset_scan_mapping.items():
                value_type = type(value).__name__
                if isinstance(value, uuid.UUID):
                    debug_info.append(f"🎯 FOUND UUID: {key} = {value} (type: {value_type})")
                    debug_mapping[key] = str(value)  # Convert UUID to string
                else:
                    debug_info.append(f"✅ Safe value: {key} = {value} (type: {value_type})")
                    debug_mapping[key] = value
            
            # Log our findings
            for info in debug_info:
                logger.info(info)
            
            # Try to serialize the cleaned mapping using UUID-aware encoder
            result = safe_json_dumps(debug_mapping)
            
            # ⚠️ Validate size against ECS limit (4KB total for all env vars)
            mapping_size_bytes = len(result.encode('utf-8'))
            if mapping_size_bytes > 2048:  # 2KB warning threshold
                logger.warning(f"⚠️ ASSET_SCAN_MAPPING is large ({mapping_size_bytes} bytes). "
                             f"ECS has a 4KB limit for ALL environment variables. "
                             f"Consider refactoring to use Redis or database lookup for larger assets.")
            
            logger.info(f"✅ Serialization successful with UUID-aware encoder ({len(debug_mapping)} entries, {mapping_size_bytes} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in debug serialization: {e}")
            # Fallback - return a safe string
            return safe_json_dumps({"error": f"Debug serialization failed: {str(e)}"})

    # ============================================================
    # STREAMING PIPELINE METHODS (Phase 4: Redis Streams)
    # ============================================================
    
    async def get_task_status(
        self,
        task_arn: str,
        cluster_name: str = None
    ) -> Dict[str, Any]:
        """
        Get current status of an ECS task.
        
        Queries AWS ECS DescribeTasks API to get real-time task status.
        
        Args:
            task_arn: ECS task ARN
            cluster_name: Optional cluster name (uses default if not provided)
            
        Returns:
            Dictionary with task status:
            {
                "task_arn": str,
                "status": str,  # PROVISIONING, PENDING, RUNNING, STOPPED
                "last_status": str,
                "desired_status": str,
                "health_status": str,
                "stop_code": str,  # Only if stopped
                "stopped_reason": str,  # Only if stopped
                "exit_code": int,  # Container exit code if stopped
                "is_healthy": bool
            }
        """
        if not self.ecs_client:
            logger.warning("ECS client not available - returning mock status")
            return {
                "task_arn": task_arn,
                "status": "RUNNING",
                "last_status": "RUNNING",
                "desired_status": "RUNNING",
                "health_status": "HEALTHY",
                "is_healthy": True,
                "mock": True
            }
        
        try:
            cluster = cluster_name or self._get_cluster_name()
            
            response = self.ecs_client.describe_tasks(
                cluster=cluster,
                tasks=[task_arn]
            )
            
            if not response.get('tasks'):
                logger.error(f"Task not found: {task_arn}")
                return {
                    "task_arn": task_arn,
                    "status": "NOT_FOUND",
                    "is_healthy": False,
                    "error": "Task not found in ECS"
                }
            
            task = response['tasks'][0]
            
            # Extract task status
            last_status = task.get('lastStatus', 'UNKNOWN')
            desired_status = task.get('desiredStatus', 'UNKNOWN')
            health_status = task.get('healthStatus', 'UNKNOWN')
            
            # Check if task is healthy
            is_healthy = (
                last_status == 'RUNNING' and
                desired_status == 'RUNNING' and
                health_status in ['HEALTHY', 'UNKNOWN']
            )
            
            result = {
                "task_arn": task_arn,
                "status": last_status,
                "last_status": last_status,
                "desired_status": desired_status,
                "health_status": health_status,
                "is_healthy": is_healthy
            }
            
            # If task stopped, get stop details
            if last_status == 'STOPPED':
                result["stop_code"] = task.get('stopCode', 'UNKNOWN')
                result["stopped_reason"] = task.get('stoppedReason', 'Unknown reason')
                
                # Get container exit code
                containers = task.get('containers', [])
                if containers:
                    result["exit_code"] = containers[0].get('exitCode')
                
                is_healthy = False
                result["is_healthy"] = False
            
            logger.debug(f"Task {task_arn[:50]}... status: {last_status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return {
                "task_arn": task_arn,
                "status": "ERROR",
                "is_healthy": False,
                "error": str(e)
            }
    
    async def monitor_multiple_tasks(
        self,
        task_arns: List[str],
        task_names: List[str],
        check_interval: int = 30,
        max_checks: int = 120
    ) -> Dict[str, Any]:
        """
        Monitor multiple ECS tasks for health and failures.
        
        Used for streaming pipelines with multiple consumers (e.g., DNSx + HTTPx).
        Periodically checks ECS task status for all tasks.
        
        Args:
            task_arns: List of ECS task ARNs to monitor
            task_names: List of task names (for logging, corresponds to task_arns)
            check_interval: Seconds between health checks (default: 30)
            max_checks: Maximum number of checks before timeout (default: 120 = 1 hour)
            
        Returns:
            Dictionary with monitoring results:
            {
                "task_statuses": Dict[str, Dict[str, Any]],  # task_name -> status
                "all_healthy": bool,
                "checks_performed": int,
                "issues_detected": List[str]
            }
        """
        import asyncio
        from datetime import datetime
        
        logger.info(f"🔍 Starting multi-task monitoring:")
        for name, arn in zip(task_names, task_arns):
            logger.info(f"   {name}: {arn[:50]}...")
        logger.info(f"   Check interval: {check_interval}s, Max checks: {max_checks}")
        
        checks_performed = 0
        issues_detected = []
        task_statuses = {name: {} for name in task_names}
        
        for check_num in range(max_checks):
            checks_performed += 1
            await asyncio.sleep(check_interval)
            
            logger.info(f"🔍 Health check {check_num + 1}/{max_checks}:")
            
            # Check status of all tasks
            all_running = True
            for name, arn in zip(task_names, task_arns):
                try:
                    status = await self._get_task_status(arn)
                    task_statuses[name] = status
                    
                    last_status = status.get("last_status", "UNKNOWN")
                    desired_status = status.get("desired_status", "UNKNOWN")
                    
                    logger.info(f"   {name}: {last_status} (desired: {desired_status})")
                    
                    # Check for failures
                    if last_status in ["STOPPED", "FAILED"]:
                        issue = f"{name} task stopped/failed: {last_status}"
                        logger.error(f"   ❌ {issue}")
                        issues_detected.append(issue)
                        all_running = False
                    elif last_status != "RUNNING":
                        all_running = False
                        
                except Exception as e:
                    issue = f"Error checking {name} task: {str(e)}"
                    logger.error(f"   ❌ {issue}")
                    issues_detected.append(issue)
                    all_running = False
            
            # If any task failed, return early
            if not all_running and any(s.get("last_status") in ["STOPPED", "FAILED"] for s in task_statuses.values()):
                logger.error(f"❌ One or more tasks failed. Stopping monitoring.")
                break
        
        all_healthy = all([s.get("last_status") == "RUNNING" for s in task_statuses.values()])
        
        return {
            "task_statuses": task_statuses,
            "all_healthy": all_healthy,
            "checks_performed": checks_performed,
            "issues_detected": issues_detected
        }
    
    async def monitor_streaming_tasks(
        self,
        producer_task_arn: str,
        consumer_task_arn: str,
        check_interval: int = 30,
        max_checks: int = 120
    ) -> Dict[str, Any]:
        """
        Monitor producer and consumer tasks for health and failures.
        
        DEPRECATED: Use monitor_multiple_tasks() for more flexibility.
        
        Periodically checks ECS task status for both producer and consumer.
        Detects failures early and returns detailed status information.
        
        Args:
            producer_task_arn: ECS task ARN for producer (Subfinder)
            consumer_task_arn: ECS task ARN for consumer (DNSx)
            check_interval: Seconds between health checks (default: 30)
            max_checks: Maximum number of checks before timeout (default: 120 = 1 hour)
            
        Returns:
            Dictionary with monitoring results:
            {
                "producer_status": Dict[str, Any],
                "consumer_status": Dict[str, Any],
                "both_healthy": bool,
                "checks_performed": int,
                "issues_detected": List[str]
            }
        """
        import asyncio
        from datetime import datetime
        
        logger.info(f"🔍 Starting task monitoring:")
        logger.info(f"   Producer: {producer_task_arn[:50]}...")
        logger.info(f"   Consumer: {consumer_task_arn[:50]}...")
        logger.info(f"   Check interval: {check_interval}s, Max checks: {max_checks}")
        
        checks_performed = 0
        issues_detected = []
        
        for check_num in range(max_checks):
            checks_performed += 1
            
            # Check producer status
            producer_status = await self.get_task_status(producer_task_arn)
            
            # Check consumer status
            consumer_status = await self.get_task_status(consumer_task_arn)
            
            both_healthy = producer_status.get("is_healthy", False) and consumer_status.get("is_healthy", False)
            
            # Log status
            logger.info(
                f"📊 Health check {check_num + 1}/{max_checks}: "
                f"Producer={producer_status['status']}, "
                f"Consumer={consumer_status['status']}, "
                f"Both healthy={both_healthy}"
            )
            
            # Detect issues
            if not producer_status.get("is_healthy"):
                issue = f"Producer unhealthy: {producer_status.get('status')}"
                if issue not in issues_detected:
                    issues_detected.append(issue)
                    logger.warning(f"⚠️  {issue}")
                    
                    # If stopped with error, get details
                    if producer_status.get("status") == "STOPPED":
                        reason = producer_status.get("stopped_reason", "Unknown")
                        exit_code = producer_status.get("exit_code", "N/A")
                        logger.error(f"❌ Producer stopped: {reason} (exit code: {exit_code})")
            
            if not consumer_status.get("is_healthy"):
                issue = f"Consumer unhealthy: {consumer_status.get('status')}"
                if issue not in issues_detected:
                    issues_detected.append(issue)
                    logger.warning(f"⚠️  {issue}")
                    
                    # If stopped with error, get details
                    if consumer_status.get("status") == "STOPPED":
                        reason = consumer_status.get("stopped_reason", "Unknown")
                        exit_code = consumer_status.get("exit_code", "N/A")
                        logger.error(f"❌ Consumer stopped: {reason} (exit code: {exit_code})")
            
            # If both tasks have stopped, exit monitoring
            if (producer_status.get("status") == "STOPPED" and 
                consumer_status.get("status") == "STOPPED"):
                logger.info("🏁 Both tasks stopped, ending monitoring")
                break
            
            # Wait before next check
            await asyncio.sleep(check_interval)
        
        return {
            "producer_status": producer_status,
            "consumer_status": consumer_status,
            "both_healthy": both_healthy,
            "checks_performed": checks_performed,
            "issues_detected": issues_detected
        }
    
    async def launch_streaming_producer(
        self,
        producer_job: BatchScanJob,
        stream_key: str
    ) -> Dict[str, Any]:
        """
        Launch a streaming producer task (e.g., Subfinder).
        
        The producer streams discoveries to Redis in real-time.
        
        Args:
            producer_job: BatchScanJob for producer module
            stream_key: Redis Stream key for output
            
        Returns:
            Dictionary with task ARN and launch info
        """
        from app.services.stream_coordinator import stream_coordinator
        
        logger.info(f"📤 Launching streaming producer: {producer_job.module}")
        logger.info(f"   Stream: {stream_key}")
        
        # Build environment variables for producer
        producer_env = await self._build_streaming_producer_environment(
            producer_job,
            stream_key
        )
        
        # Launch producer task
        producer_result = await self._launch_streaming_task(
            producer_job,
            producer_env,
            role="producer"
        )
        
        logger.info(f"✅ Producer launched: {producer_result['task_arn']}")
        
        return {
            "task_arn": producer_result["task_arn"],
            "batch_id": str(producer_job.id),
            "module": producer_job.module,
            "role": "producer"
        }
    
    async def launch_streaming_consumer(
        self,
        consumer_job: BatchScanJob,
        stream_key: str,
        consumer_group_name: str,
        consumer_name: str
    ) -> Dict[str, Any]:
        """
        Launch a streaming consumer task (e.g., DNSx, HTTPx).
        
        The consumer reads from Redis Stream and processes messages in real-time.
        Multiple consumers can read from the same stream in parallel using different groups.
        
        Args:
            consumer_job: BatchScanJob for consumer module
            stream_key: Redis Stream key to consume from
            consumer_group_name: Consumer group name (e.g., "dnsx-consumers")
            consumer_name: Unique consumer identifier
            
        Returns:
            Dictionary with task ARN and launch info
        """
        from app.services.stream_coordinator import stream_coordinator
        
        logger.info(f"📥 Launching streaming consumer: {consumer_job.module}")
        logger.info(f"   Stream: {stream_key}")
        logger.info(f"   Group: {consumer_group_name}")
        
        # Create consumer group (idempotent - safe to call multiple times)
        await stream_coordinator.create_consumer_group(stream_key, consumer_group_name)
        
        # Build environment variables for consumer
        consumer_env = await self._build_streaming_consumer_environment(
            consumer_job,
            stream_key,
            consumer_group_name,
            consumer_name
        )
        
        # Launch consumer task
        consumer_result = await self._launch_streaming_task(
            consumer_job,
            consumer_env,
            role="consumer"
        )
        
        logger.info(f"✅ Consumer launched: {consumer_result['task_arn']}")
        
        return {
            "task_arn": consumer_result["task_arn"],
            "batch_id": str(consumer_job.id),
            "module": consumer_job.module,
            "role": "consumer",
            "consumer_group": consumer_group_name
        }
    
    async def launch_streaming_pipeline(
        self,
        producer_job: BatchScanJob,
        consumer_job: BatchScanJob,
        stream_key: str,
        consumer_group_name: str,
        consumer_name: str
    ) -> Dict[str, Any]:
        """
        Launch a streaming pipeline with producer and consumer running concurrently.
        
        This method implements the Redis Streams-based producer-consumer pattern:
        1. Generate unique stream key for the scan job
        2. Create consumer group (idempotent)
        3. Launch producer task (e.g., Subfinder) with STREAMING_MODE=true
        4. Launch consumer task (e.g., DNSx) with STREAMING_MODE=true
        5. Both tasks run concurrently, communicating via Redis Streams
        
        Args:
            producer_job: BatchScanJob for producer module (e.g., Subfinder)
            consumer_job: BatchScanJob for consumer module (e.g., DNSx)
            stream_key: Redis Stream key for communication
            consumer_group_name: Consumer group name
            consumer_name: Unique consumer identifier
            
        Returns:
            Dictionary with both task ARNs and stream information
        """
        from app.services.stream_coordinator import stream_coordinator
        
        logger.info(f"🌊 Launching streaming pipeline")
        logger.info(f"   Producer: {producer_job.module} (batch_id={producer_job.id})")
        logger.info(f"   Consumer: {consumer_job.module} (batch_id={consumer_job.id})")
        logger.info(f"   Stream: {stream_key}")
        logger.info(f"   Consumer Group: {consumer_group_name}")
        
        # Step 1: Create consumer group (idempotent)
        await stream_coordinator.create_consumer_group(stream_key, consumer_group_name)
        
        # Step 2: Build environment variables for producer
        producer_env = await self._build_streaming_producer_environment(
            producer_job,
            stream_key
        )
        
        # Step 3: Build environment variables for consumer
        consumer_env = await self._build_streaming_consumer_environment(
            consumer_job,
            stream_key,
            consumer_group_name,
            consumer_name
        )
        
        # Step 4: Launch both tasks concurrently
        logger.info("🚀 Launching producer and consumer tasks concurrently...")
        
        # Launch producer
        producer_result = await self._launch_streaming_task(
            producer_job,
            producer_env,
            "producer"
        )
        
        # Launch consumer
        consumer_result = await self._launch_streaming_task(
            consumer_job,
            consumer_env,
            "consumer"
        )
        
        logger.info(f"✅ Streaming pipeline launched successfully")
        logger.info(f"   Producer task: {producer_result.get('task_arn')}")
        logger.info(f"   Consumer task: {consumer_result.get('task_arn')}")
        
        return {
            "stream_key": stream_key,
            "producer": producer_result,
            "consumer": consumer_result,
            "consumer_group": consumer_group_name,
            "status": "launched"
        }
    
    async def _build_streaming_producer_environment(
        self,
        batch_job: BatchScanJob,
        stream_key: str
    ) -> List[Dict[str, str]]:
        """
        Build environment variables for streaming producer (e.g., Subfinder).
        
        Adds streaming-specific variables:
        - STREAMING_MODE=true
        - STREAM_OUTPUT_KEY={stream_key}
        
        Args:
            batch_job: Producer BatchScanJob
            stream_key: Redis Stream key for output
            
        Returns:
            List of environment variable dictionaries
        """
        # Start with standard environment
        environment = await self._build_container_environment(batch_job, None)
        
        # Add streaming-specific variables
        streaming_vars = [
            {"name": "STREAMING_MODE", "value": "true"},
            {"name": "STREAM_OUTPUT_KEY", "value": stream_key},
            {"name": "MODULE_ROLE", "value": "producer"},
        ]
        
        environment.extend(streaming_vars)
        
        logger.debug(f"📋 Built streaming producer environment: {len(environment)} variables")
        return environment
    
    async def _build_streaming_consumer_environment(
        self,
        batch_job: BatchScanJob,
        stream_key: str,
        consumer_group_name: str,
        consumer_name: str
    ) -> List[Dict[str, str]]:
        """
        Build environment variables for streaming consumer (e.g., DNSx).
        
        Adds streaming-specific variables:
        - STREAMING_MODE=true
        - STREAM_INPUT_KEY={stream_key}
        - CONSUMER_GROUP_NAME={consumer_group_name}
        - CONSUMER_NAME={consumer_name}
        - BATCH_SIZE=50 (default)
        - BLOCK_MILLISECONDS=5000 (default)
        - MAX_PROCESSING_TIME=3600 (default)
        
        Args:
            batch_job: Consumer BatchScanJob
            stream_key: Redis Stream key to read from
            consumer_group_name: Consumer group name
            consumer_name: Unique consumer identifier
            
        Returns:
            List of environment variable dictionaries
        """
        # Start with standard environment
        environment = await self._build_container_environment(batch_job, None)
        
        # Add streaming-specific variables
        streaming_vars = [
            {"name": "STREAMING_MODE", "value": "true"},
            {"name": "STREAM_INPUT_KEY", "value": stream_key},
            {"name": "CONSUMER_GROUP_NAME", "value": consumer_group_name},
            {"name": "CONSUMER_NAME", "value": consumer_name},
            {"name": "MODULE_ROLE", "value": "consumer"},
            {"name": "BATCH_SIZE", "value": "50"},  # Messages per XREADGROUP
            {"name": "BLOCK_MILLISECONDS", "value": "5000"},  # 5 seconds blocking
            {"name": "MAX_PROCESSING_TIME", "value": "3600"},  # 1 hour timeout
        ]
        
        environment.extend(streaming_vars)
        
        logger.debug(f"📋 Built streaming consumer environment: {len(environment)} variables")
        return environment
    
    async def _launch_streaming_task(
        self,
        batch_job: BatchScanJob,
        environment: List[Dict[str, str]],
        role: str
    ) -> Dict[str, Any]:
        """
        Launch a single streaming task (producer or consumer).
        
        Similar to _launch_single_batch_task but with custom environment.
        
        Args:
            batch_job: BatchScanJob configuration
            environment: Custom environment variables (including streaming vars)
            role: "producer" or "consumer" (for logging)
            
        Returns:
            Dictionary with task launch result
        """
        if not self.ecs_client:
            logger.warning(f"ECS client not available - returning mock result for {role}")
            return {
                "batch_id": str(batch_job.id),
                "task_arn": f"arn:aws:ecs:us-east-1:123456789012:task/mock-{role}-{batch_job.id}",
                "status": "mock_launched",
                "role": role,
                "cpu": batch_job.allocated_cpu,
                "memory": batch_job.allocated_memory
            }
        
        try:
            task_definition = self._get_task_definition_name(batch_job.module)
            
            # Launch ECS task with custom environment
            response = self.ecs_client.run_task(
                cluster=self._get_cluster_name(),
                taskDefinition=task_definition,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': self._get_subnet_ids(),
                        'securityGroups': self._get_security_group_ids(),
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides={
                    'taskRoleArn': await self._get_task_role_arn(batch_job.module),
                    'executionRoleArn': self._get_execution_role_arn(),
                    'cpu': str(batch_job.allocated_cpu),
                    'memory': str(batch_job.allocated_memory),
                    'containerOverrides': [{
                        'name': self._get_container_name(batch_job.module),
                        'environment': environment,
                    }]
                },
                tags=[
                    {'key': 'BatchId', 'value': str(batch_job.id)},
                    {'key': 'Module', 'value': batch_job.module},
                    {'key': 'Role', 'value': role},
                    {'key': 'StreamingMode', 'value': 'true'},
                    {'key': 'Purpose', 'value': 'StreamingPipeline'}
                ]
            )
            
            if not response.get('tasks'):
                raise Exception(f"No tasks returned from ECS for {role}")
            
            task_arn = response['tasks'][0]['taskArn']
            
            logger.info(f"✅ Launched {role} task: {task_arn}")
            
            return {
                "batch_id": str(batch_job.id),
                "task_arn": task_arn,
                "status": "launched",
                "role": role,
                "cpu": batch_job.allocated_cpu,
                "memory": batch_job.allocated_memory
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to launch {role} task: {str(e)}")
            raise


# Global instance
batch_workflow_orchestrator = BatchWorkflowOrchestrator()
