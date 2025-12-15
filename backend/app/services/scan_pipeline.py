"""
🌊 Streaming Scan Pipeline Orchestrator

Coordinates reconnaissance modules in a streaming architecture using Redis Streams
for parallel execution and real-time data flow.

Architecture:
- Producer modules (Subfinder) write discoveries to Redis Streams
- Consumer modules (DNSx, HTTPx) read from streams and process in parallel
- All modules support streaming for maximum throughput

Features:
- Automatic dependency resolution (DNSx auto-included with Subfinder)
- Parallel consumer execution (DNSx + HTTPx run simultaneously)
- Real-time WebSocket updates via Redis pub/sub
- Timeout handling with graceful degradation
- Error propagation and retry logic

Author: Pluckware Development Team
Date: October 28, 2025
Phase: 5A - Streaming-Only Architecture (November 14, 2025 Refactor)

Version: 3.0.0 (2025-11-14)
Breaking Change: Sequential pipeline removed, streaming-only architecture
Update: Removed duplicate execution paths, fixed Bug 4 (missing await)
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import asyncio
import logging
from uuid import UUID

from ..core.supabase_client import SupabaseClient
from ..schemas.assets import EnhancedAssetScanRequest
from ..schemas.recon import ReconModule
from ..schemas.batch import BatchScanJob
from .module_registry import module_registry
from .module_config_loader import get_module_config

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Raised when module dependencies are not satisfied."""
    pass


class PipelineTimeoutError(Exception):
    """Raised when pipeline execution times out."""
    pass


class ScanPipeline:
    """
    Manages sequential execution of scan modules with dependency resolution.
    
    Features:
    - Automatic dependency resolution (topological sort)
    - Sequential execution with polling
    - Timeout handling
    - Error propagation
    - Progress tracking
    
    Example:
        pipeline = ScanPipeline()
        result = await pipeline.execute_pipeline(
            asset_id="uuid",
            modules=["subfinder", "dnsx"],
            scan_request=request,
            user_id="uuid"
        )
    """
    
    # Module dependency graph
    # Key: module name, Value: list of dependencies (must run first)
    # Module dependencies now loaded from database via ModuleConfigLoader
    # See: backend/app/services/module_config_loader.py
    # This eliminates Layer 4 of the 7-layer issue
    
    # Timeout per module (seconds)
    MODULE_TIMEOUTS = {
        "subfinder": 600,  # 10 minutes
        "dnsx": 1800,      # 30 minutes (increased for large assets with 400+ subdomains)
        "httpx": 900,      # 15 minutes
        "nuclei": 1800,    # 30 minutes
    }
    
    # Polling interval for checking scan completion (seconds)
    POLL_INTERVAL = 5
    
    def __init__(self):
        self.supabase = SupabaseClient().service_client
        self.logger = logging.getLogger(__name__)
    
    def _resolve_execution_order(self, modules: List[str]) -> List[str]:
        """
        Topological sort of modules based on dependencies.
        
        Auto-includes required persistence modules:
        - DNSx is automatically added when Subfinder is present (Phase 4 architecture fix)
        
        Args:
            modules: List of module names
            
        Returns:
            Ordered list of modules (dependencies first)
            
        Raises:
            DependencyError: If circular dependency detected
            
        Example:
            Input: ["dnsx", "subfinder"]
            Output: ["subfinder", "dnsx"]  # subfinder first (dependency)
            
            Input: ["subfinder", "httpx"]
            Output: ["subfinder", "dnsx", "httpx"]  # dnsx auto-added for persistence
        """
        # Phase 4 Fix: Auto-include DNSx when Subfinder is present
        # Rationale: DNSx is the canonical persistence layer for subfinder's discoveries
        # Subfinder only streams data; DNSx writes to database
        modules_set = set(modules)
        if "subfinder" in modules_set and "dnsx" not in modules_set:
            self.logger.info(
                "🔧 Auto-including 'dnsx' module: Subfinder requires DNSx for data persistence"
            )
            modules_set.add("dnsx")
        
        # Convert back to list for processing
        modules = list(modules_set)
        
        ordered = []
        visited = set()
        visiting = set()  # For cycle detection
        
        def visit(module: str):
            if module in visited:
                return
            if module in visiting:
                raise DependencyError(f"Circular dependency detected involving module: {module}")
            
            visiting.add(module)
            
            # Visit dependencies first (loaded from database)
            try:
                deps = get_module_config().get_dependencies(module)
            except ValueError:
                # Module not found in config, assume no dependencies
                deps = []
            for dep in deps:
                if dep in modules:
                    visit(dep)
                else:
                    # Dependency not in requested modules
                    self.logger.warning(
                        f"⚠️  Module {module} requires {dep}, but {dep} not in scan request. "
                        f"This may cause {module} to fail."
                    )
            
            visiting.remove(module)
            visited.add(module)
            ordered.append(module)
        
        for module in modules:
            visit(module)
        
        return ordered
    
    async def _execute_module(
        self,
        asset_id: str,
        module: str,
        scan_request: EnhancedAssetScanRequest,
        user_id: str,
        parent_scan_job_id: str = None  # Bug #9 Fix: Parent scan job ID to maintain data linkage
    ) -> Dict[str, Any]:
        """
        Execute a single module scan by calling workflow orchestrator directly.
        
        REFACTORED (Bug #6 Fix): Calls batch_workflow_orchestrator directly instead of
        going through asset_service.start_asset_scan() to avoid circular dependency.
        
        REFACTORED (Bug #9 Fix): Now accepts parent_scan_job_id to ensure all modules
        in a sequential pipeline share the same scan job ID, allowing DNSX to find
        subdomains discovered by Subfinder.
        
        Previous flow (BROKEN):
          ScanPipeline → AssetService → ScanPipeline (infinite recursion)
        
        New flow (FIXED):
          ScanPipeline → WorkflowOrchestrator (direct execution)
        
        Args:
            asset_id: Asset UUID
            module: Module name to execute
            scan_request: Original scan request (for configuration)
            user_id: User UUID
            parent_scan_job_id: Optional parent scan job ID for sequential pipelines (Bug #9 Fix)
            
        Returns:
            Dict with scan job info:
            {
                "module": "subfinder",
                "asset_scan_id": "uuid",
                "batch_id": "uuid",
                "started_at": "2025-11-03T12:00:00"
            }
        """
        from .batch_workflow_orchestrator import batch_workflow_orchestrator
        from datetime import datetime
        import uuid
        
        self.logger.info(f"🚀 Launching {module} scan for asset {asset_id}")
        
        # Step 1: Fetch asset data
        asset_response = self.supabase.table('assets').select('*').eq(
            'id', asset_id
        ).eq('user_id', user_id).single().execute()
        
        if not asset_response.data:
            raise ValueError(f"Asset {asset_id} not found for user {user_id}")
        
        asset = asset_response.data
        
        # Step 2: Fetch domains for this asset
        domains_result = self.supabase.table('apex_domains').select(
            'id, domain, is_active'
        ).eq('asset_id', asset_id).execute()
        
        if scan_request.active_domains_only:
            apex_domains = [d for d in domains_result.data if d['is_active']]
        else:
            apex_domains = domains_result.data
        
        if not apex_domains:
            self.logger.warning(f"No domains found for asset {asset_id}, skipping {module}")
            return {
                "module": module,
                "status": "skipped",
                "reason": "no_domains",
                "asset_scan_id": None,
                "batch_id": None
            }
        
        # Step 3: Handle DNSX special case (database fetch mode)
        domains_to_process = apex_domains
        dnsx_metadata = None
        
        if module == "dnsx":
            # DNSX scans discovered subdomains, not apex domains
            # Check subdomain count
            subdomain_count_query = self.supabase.table('subdomains').select(
                'id', count='exact'
            ).eq('asset_id', asset_id).execute()
            
            subdomain_count = subdomain_count_query.count if subdomain_count_query.count is not None else 0
            
            if subdomain_count == 0:
                self.logger.warning(f"No subdomains found for DNSX scan on asset {asset_id}")
                return {
                    "module": module,
                    "status": "skipped",
                    "reason": "no_subdomains",
                    "asset_scan_id": None,
                    "batch_id": None
                }
            
            self.logger.info(f"✅ Found {subdomain_count} subdomains for DNSX scan")
            
            # Pass EMPTY domains list - container will fetch from database
            domains_to_process = []
            
            # Store metadata for orchestrator
            dnsx_metadata = {
                'fetch_from_database': True,
                'asset_id': asset_id,
                'subdomain_count': subdomain_count
            }
        
        # Step 4: Create asset_scan_job record
        # Bug #9 Fix: Use parent_scan_job_id if provided (sequential pipeline)
        # This ensures all modules share the same scan job ID so data flows correctly
        if parent_scan_job_id:
            asset_scan_id = parent_scan_job_id
            self.logger.info(
                f"🔗 Using parent scan_job_id for {module}: {parent_scan_job_id} "
                f"(enables data linkage between modules)"
            )
        else:
            asset_scan_id = str(uuid.uuid4())
            self.logger.info(f"🆕 Created new scan_job_id for {module}: {asset_scan_id}")
        
        batch_id = str(uuid.uuid4())
        
        # Bug #9 Fix: Only create asset_scan_job if this is a new scan (not using parent ID)
        # When using parent_scan_job_id, the record already exists from the first module
        if not parent_scan_job_id:
            asset_scan_record = {
                "id": asset_scan_id,
                "asset_id": asset_id,
                "user_id": user_id,
                "modules": [module],  # Single module for pipeline
                "status": "pending",
                "total_domains": len(apex_domains) if module != "dnsx" else subdomain_count,
                "completed_domains": 0,
                "active_domains_only": scan_request.active_domains_only,
                "metadata": {
                    "asset_name": asset['name'],
                    "scan_initiated_by": "scan_pipeline",
                    "pipeline_execution": True,
                    "batch_id": batch_id
                },
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Insert asset_scan_job record
            self.supabase.table("asset_scan_jobs").insert(asset_scan_record).execute()
            self.logger.info(f"✅ Created asset_scan_job record: {asset_scan_id}")
        else:
            self.logger.info(f"♻️  Reusing existing asset_scan_job record: {asset_scan_id}")
        
        # Step 5: Create batch_scan_job record
        batch_job_record = {
            "id": batch_id,
            "user_id": user_id,
            "batch_type": "single_asset",  # Pipeline executes modules for single asset
            "module": module,
            "status": "pending",
            "total_domains": len(domains_to_process) if module != "dnsx" else subdomain_count,
            "completed_domains": 0,
            "failed_domains": 0,
            "batch_domains": [d["domain"] for d in domains_to_process] if domains_to_process else [],
            "asset_scan_mapping": {
                # Map domains to asset_scan_id for result linking
                d["domain"]: asset_scan_id for d in domains_to_process
            } if domains_to_process else {},
            "metadata": {
                "asset_id": asset_id,
                "asset_scan_id": asset_scan_id,
                "asset_name": asset['name'],
                "execution_mode": "pipeline",
                "pipeline_execution": True,
                **(dnsx_metadata if dnsx_metadata else {})
            },
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Insert batch_scan_job record
        self.supabase.table("batch_scan_jobs").insert(batch_job_record).execute()
        
        # Step 6: Launch ECS task via workflow orchestrator (DIRECT CALL - NO RECURSION)
        self.logger.info(f"🚀 Launching {module} batch via workflow orchestrator (batch_id: {batch_id})")
        
        try:
            # Convert batch_job_record dict to BatchScanJob Pydantic model
            # Required by launch_module_task() for type safety and validation
            batch_job = BatchScanJob(**batch_job_record)
            
            # Launch task via new public API (proper encapsulation)
            launch_result = await batch_workflow_orchestrator.launch_module_task(
                batch_job=batch_job,
                resource_allocation=None  # Use default allocation from batch_job
            )
            
            self.logger.info(
                f"✅ Module '{module}' batch launched successfully: {batch_id}, "
                f"task_arn={launch_result.get('task_arn')}"
            )
            
            return {
                "module": module,
                "asset_scan_id": asset_scan_id,
                "batch_id": batch_id,
                "total_domains": batch_job_record["total_domains"],
                "started_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to launch {module} batch: {e}")
            
            # Update records to failed status
            self.supabase.table("asset_scan_jobs").update({
                "status": "failed",
                "metadata": {**asset_scan_record["metadata"], "error": str(e)}
            }).eq("id", asset_scan_id).execute()
            
            self.supabase.table("batch_scan_jobs").update({
                "status": "failed",
                "metadata": {**batch_job_record["metadata"], "error": str(e)}
            }).eq("id", batch_id).execute()
            
            raise
    
    async def _wait_for_completion(
        self,
        asset_scan_id: str,
        module: str,
        timeout: int
    ) -> str:
        """
        Poll scan job until completion or timeout.
        
        Args:
            asset_scan_id: Asset scan job UUID
            module: Module name (for logging)
            timeout: Maximum wait time in seconds
            
        Returns:
            Final status: "completed", "failed", or "timeout"
            
        Raises:
            PipelineTimeoutError: If timeout exceeded
        """
        start_time = datetime.utcnow()
        elapsed = 0
        
        while elapsed < timeout:
            try:
                # Query scan job status
                response = self.supabase.table("asset_scan_jobs") \
                    .select("status") \
                    .eq("id", asset_scan_id) \
                    .single() \
                    .execute()
                
                if not response.data:
                    self.logger.error(f"❌ Scan job {asset_scan_id} not found")
                    return "failed"
                
                status = response.data.get("status", "").lower()
                
                # Terminal statuses
                if status in ["completed", "success"]:
                    return "completed"
                elif status in ["failed", "error", "cancelled"]:
                    return status
                elif status in ["pending", "running", "in_progress"]:
                    # Still running, continue polling
                    pass
                else:
                    self.logger.warning(f"⚠️  Unknown status '{status}' for {module} scan")
                
                # Log progress every 30 seconds
                if elapsed % 30 == 0 and elapsed > 0:
                    self.logger.info(
                        f"⏳ {module} still running... "
                        f"({elapsed}s / {timeout}s, status: {status})"
                    )
                
            except Exception as e:
                self.logger.error(f"❌ Error checking {module} status: {e}")
                # Continue polling despite errors
            
            # Wait before next poll
            await asyncio.sleep(self.POLL_INTERVAL)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        # Timeout exceeded
        self.logger.error(
            f"❌ {module} scan timed out after {timeout}s "
            f"(asset_scan_id: {asset_scan_id})"
        )
        raise PipelineTimeoutError(
            f"Module {module} exceeded timeout of {timeout} seconds"
        )
    
    async def _validate_modules(self, modules: List[str]):
        """
        Validate all modules are active and available.
        
        Args:
            modules: List of module names to validate
            
        Raises:
            ValueError: If any module is invalid or inactive
        """
        validation_results = await module_registry.validate_modules(modules)
        
        invalid_modules = [
            name for name, is_valid in validation_results.items()
            if not is_valid
        ]
        
        if invalid_modules:
            raise ValueError(
                f"Invalid or inactive modules: {', '.join(invalid_modules)}"
            )
        
        self.logger.info(f"✅ All {len(modules)} module(s) validated successfully")
    
    def requires_pipeline(self, modules: List[str]) -> bool:
        """
        Check if the given modules require pipeline execution.
        
        A pipeline is required if any module has dependencies that are
        also in the module list.
        
        Args:
            modules: List of module names
            
        Returns:
            True if pipeline needed, False otherwise
            
        Example:
            requires_pipeline(["subfinder"]) → False (no dependencies)
            requires_pipeline(["dnsx"]) → False (dependency not in list)
            requires_pipeline(["subfinder", "dnsx"]) → True (dependency present)
        """
        for module in modules:
            try:
                deps = get_module_config().get_dependencies(module)
            except ValueError:
                # Module not found in config, assume no dependencies
                deps = []
            if any(dep in modules for dep in deps):
                return True
        return False
    
    async def _wait_for_jobs_completion(
        self,
        job_ids: List[str],
        timeout: int = 3600,
        check_interval: int = 10
    ) -> Dict[str, Any]:
        """
        Monitor batch_scan_jobs until all reach terminal status.
        
        Polls database every {check_interval}s to check job statuses.
        Returns when all jobs are "completed", "failed", or "timeout".
        
        This is the CANONICAL way to determine when containers have actually
        finished their work (not just when streams are consumed).
        
        Args:
            job_ids: List of batch_scan_job UUIDs to monitor
            timeout: Maximum wait time in seconds (default: 3600 = 1 hour)
            check_interval: Seconds between database checks (default: 10s)
            
        Returns:
            {
                "status": "completed" | "partial_failure" | "timeout",
                "module_statuses": {"subfinder": "completed", "dnsx": "completed", "httpx": "completed"},
                "successful_modules": 3,
                "total_modules": 3,
                "elapsed_seconds": 3603.5,
                "checks_performed": 360
            }
        """
        import asyncio
        
        start_time = datetime.utcnow()
        max_wait_seconds = timeout
        checks_performed = 0
        terminal_statuses = {"completed", "failed", "timeout"}
        
        self.logger.info(f"📊 Starting job completion monitoring...")
        self.logger.info(f"   Jobs to monitor: {len(job_ids)}")
        self.logger.info(f"   Check interval: {check_interval}s")
        self.logger.info(f"   Timeout: {timeout}s")
        
        while True:
            checks_performed += 1
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            # Check timeout
            if elapsed > max_wait_seconds:
                self.logger.warning(f"⚠️  Job monitoring timeout ({timeout}s) exceeded")
                
                # Get final statuses for timeout case
                try:
                    jobs_response = self.supabase.table("batch_scan_jobs")\
                        .select("id, module, status")\
                        .in_("id", job_ids)\
                        .execute()
                    
                    module_statuses = {job["module"]: job["status"] for job in jobs_response.data}
                except Exception as e:
                    self.logger.error(f"Failed to fetch final job statuses: {e}")
                    module_statuses = {}
                
                return {
                    "status": "timeout",
                    "module_statuses": module_statuses,
                    "successful_modules": sum(1 for s in module_statuses.values() if s == "completed"),
                    "total_modules": len(job_ids),
                    "elapsed_seconds": elapsed,
                    "checks_performed": checks_performed
                }
            
            # Query all job statuses
            try:
                jobs_response = self.supabase.table("batch_scan_jobs")\
                    .select("id, module, status, completed_at")\
                    .in_("id", job_ids)\
                    .execute()
                
                if not jobs_response.data:
                    self.logger.warning(f"No jobs found for IDs: {job_ids}")
                    await asyncio.sleep(check_interval)
                    continue
                
                # Build status map
                module_statuses = {}
                for job in jobs_response.data:
                    module_statuses[job["module"]] = job["status"]
                
                # Count statuses
                completed_count = sum(1 for s in module_statuses.values() if s in terminal_statuses)
                successful_count = sum(1 for s in module_statuses.values() if s == "completed")
                
                # Log progress
                self.logger.info(
                    f"📊 Job progress check #{checks_performed}: "
                    f"{completed_count}/{len(job_ids)} jobs terminal, "
                    f"{successful_count} completed, "
                    f"elapsed={int(elapsed)}s"
                )
                
                # Log individual module statuses
                for module, status in sorted(module_statuses.items()):
                    if status == "completed":
                        self.logger.info(f"   ✅ {module}: {status}")
                    elif status == "running":
                        self.logger.info(f"   🔄 {module}: {status}")
                    elif status == "failed":
                        self.logger.warning(f"   ❌ {module}: {status}")
                    else:
                        self.logger.info(f"   ⏳ {module}: {status}")
                
                # Check if all jobs reached terminal status
                if completed_count == len(job_ids):
                    # Determine final status
                    if successful_count == len(job_ids):
                        final_status = "completed"
                        self.logger.info(f"✅ All {len(job_ids)} jobs completed successfully!")
                    else:
                        final_status = "partial_failure"
                        failed_count = len(job_ids) - successful_count
                        self.logger.warning(
                            f"⚠️  Jobs finished with failures: "
                            f"{successful_count} succeeded, {failed_count} failed"
                        )
                    
                    return {
                        "status": final_status,
                        "module_statuses": module_statuses,
                        "successful_modules": successful_count,
                        "total_modules": len(job_ids),
                        "elapsed_seconds": elapsed,
                        "checks_performed": checks_performed
                    }
                
            except Exception as e:
                self.logger.error(f"Error checking job statuses: {e}")
                # Don't fail immediately, retry on next iteration
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def execute_pipeline(
        self,
        asset_id: str,
        modules: List[str],
        scan_request: EnhancedAssetScanRequest,
        user_id: str,
        scan_job_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute modules using Redis Streams for parallel real-time processing.
        
        This method implements the producer-consumer pattern where:
        - Subfinder (producer) streams subdomains to Redis
        - DNSx (consumer) reads from Redis and resolves DNS concurrently
        
        Both tasks run in parallel, enabling real-time processing.
        
        Args:
            asset_id: Asset UUID
            modules: List of module names (must include subfinder and dnsx)
            scan_request: Original scan request
            user_id: User UUID
            scan_job_id: Optional scan job ID for progress tracking (parent scan ID from scans table)
            
        Returns:
            Dict with pipeline results in same format as execute_pipeline
            
        Raises:
            ValueError: If streaming not applicable for given modules
        """
        from ..services.batch_workflow_orchestrator import batch_workflow_orchestrator
        from ..services.stream_coordinator import stream_coordinator
        from ..schemas.batch import BatchScanJob, BatchType
        import uuid
        
        self.logger.info(f"🌊 Starting STREAMING pipeline for asset {asset_id}")
        self.logger.info(f"   Modules: {modules}")
        
        # Phase 4 Fix: Auto-include DNSx when Subfinder is present
        # Rationale: DNSx is the canonical persistence layer for subfinder's discoveries
        # Subfinder only streams data; DNSx writes to database
        modules_set = set(modules)
        if "subfinder" in modules_set and "dnsx" not in modules_set:
            self.logger.info(
                "🔧 Auto-including 'dnsx' module: Subfinder requires DNSx for data persistence"
            )
            modules_set.add("dnsx")
            modules = list(modules_set)
        
        # Streaming-only architecture: All modules support streaming
        # No capability check needed - DNSx is auto-included above if needed
        
        # Validate modules
        await self._validate_modules(modules)
        
        pipeline_start = datetime.utcnow()
        
        # ============================================================
        # STEP 0: Create asset_scan_jobs Record (CRITICAL FIX)
        # ============================================================
        
        self.logger.info("📋 Creating asset_scan_jobs record...")
        
        # Generate asset_scan_job ID
        asset_scan_id = str(uuid.uuid4())
        
        # Get asset details
        asset_response = self.supabase.table("assets").select("*").eq("id", asset_id).execute()
        
        if not asset_response.data:
            raise ValueError(f"Asset not found: {asset_id}")
        
        asset = asset_response.data[0]
        
        # Query apex_domains table to get actual domains
        apex_response = self.supabase.table("apex_domains")\
            .select("domain")\
            .eq("asset_id", asset_id)\
            .eq("is_active", True)\
            .execute()
        
        parent_domains = [record["domain"] for record in apex_response.data]
        
        self.logger.info(f"📍 Retrieved {len(parent_domains)} active apex domains for asset {asset_id}")
        
        # Create asset_scan_jobs record
        asset_scan_record = {
            "id": asset_scan_id,
            "asset_id": asset_id,
            "user_id": user_id,
            "modules": modules,  # Both subfinder and dnsx
            "status": "pending",
            "total_domains": len(parent_domains),
            "completed_domains": 0,
            "active_domains_only": scan_request.active_domains_only if scan_request else True,
            "parent_scan_id": scan_job_id,  # Link to parent scan in scans table
            "metadata": {
                "asset_name": asset['name'],
                "scan_initiated_by": "streaming_pipeline",
                "streaming_mode": True,
                "parent_scan_id": scan_job_id
            }
        }
        
        # Insert asset_scan_job record
        self.supabase.table("asset_scan_jobs").insert(asset_scan_record).execute()
        self.logger.info(f"✅ Created asset_scan_jobs record: {asset_scan_id}")
        
        # ============================================================
        # STEP 1: Prepare Producer Job (Subfinder)
        # ============================================================
        
        self.logger.info("📋 Creating producer job (Subfinder)...")
        
        # Create BatchScanJob for subfinder (producer)
        producer_job = await self._create_batch_scan_job(
            asset_id=asset_id,
            module="subfinder",
            scan_request=scan_request,
            user_id=user_id,
            parent_scan_job_id=asset_scan_id  # ✅ FIX: Use asset_scan_id instead of scan_id
        )
        
        self.logger.info(f"✅ Producer job created: {producer_job.id}")
        
        # ============================================================
        # STEP 2: Prepare Consumer Jobs (DNSx, HTTPx, etc.)
        # ============================================================
        
        # Determine which consumers to launch (exclude subfinder, it's the producer)
        consumer_modules = [m for m in modules if m != "subfinder"]
        consumer_jobs = {}
        
        self.logger.info(f"📋 Creating {len(consumer_modules)} consumer job(s): {consumer_modules}")
        
        for module in consumer_modules:
            self.logger.info(f"   Creating {module} consumer job...")
            job = await self._create_batch_scan_job(
                asset_id=asset_id,
                module=module,
                scan_request=scan_request,
                user_id=user_id,
                parent_scan_job_id=asset_scan_id
            )
            consumer_jobs[module] = job
            self.logger.info(f"   ✅ {module} job created: {job.id}")
        
        # ============================================================
        # STEP 3: Generate Stream Identifiers
        # ============================================================
        
        # Generate unique stream key for this scan
        stream_key = stream_coordinator.generate_stream_key(
            scan_job_id=str(producer_job.id),
            producer_module="subfinder"
        )
        
        self.logger.info(f"📋 Stream configuration:")
        self.logger.info(f"   Stream key: {stream_key}")
        self.logger.info(f"   Consumers: {len(consumer_modules)} ({', '.join(consumer_modules)})")
        
        # ============================================================
        # STEP 4: Launch Streaming Pipeline (Producer + All Consumers in Parallel)
        # ============================================================
        
        self.logger.info(f"🚀 Launching streaming pipeline: 1 producer + {len(consumer_modules)} parallel consumers...")
        
        # Launch producer (Subfinder)
        self.logger.info("   📤 Launching producer (subfinder)...")
        producer_launch = await batch_workflow_orchestrator.launch_streaming_producer(
            producer_job=producer_job,
            stream_key=stream_key
        )
        producer_task_arn = producer_launch["task_arn"]
        self.logger.info(f"      ✅ Task: {producer_task_arn}")
        
        # Launch all consumers in parallel (each reads from same stream)
        consumer_task_arns = {}
        for module in consumer_modules:
            consumer_group_name = stream_coordinator.generate_consumer_group_name(module)
            consumer_name = stream_coordinator.generate_consumer_name(module, str(consumer_jobs[module].id)[:8])
            
            self.logger.info(f"   📥 Launching consumer ({module})...")
            self.logger.info(f"      Group: {consumer_group_name}")
            
            consumer_launch = await batch_workflow_orchestrator.launch_streaming_consumer(
                consumer_job=consumer_jobs[module],
                stream_key=stream_key,
                consumer_group_name=consumer_group_name,
                consumer_name=consumer_name
            )
            consumer_task_arns[module] = consumer_launch["task_arn"]
            self.logger.info(f"      ✅ Task: {consumer_launch['task_arn']}")
        
        self.logger.info(f"✅ All tasks launched successfully!")
        self.logger.info(f"   Producer: subfinder")
        self.logger.info(f"   Consumers: {', '.join(consumer_modules)} (running in parallel)")
        
        # ============================================================
        # STEP 5: Monitor Job Completion (NEW: Polling batch_scan_jobs)
        # ============================================================
        # 
        # REFACTORED (Option D-1): Changed from parallel stream monitoring to
        # sequential job status monitoring.
        #
        # OLD APPROACH (removed):
        #   - monitor_stream_progress() → returned when stream consumed (~5 min)
        #   - monitor_multiple_tasks() → only checked ECS tasks didn't crash
        #   - Problem: Returned before containers finished writing to DB
        #
        # NEW APPROACH (implemented):
        #   - _wait_for_jobs_completion() → polls batch_scan_jobs.status
        #   - Returns ONLY when containers update status = "completed"
        #   - Single source of truth: batch_scan_jobs table
        #
        # ============================================================
        
        self.logger.info(f"🔍 Monitoring {len(consumer_modules)} consumers + 1 producer...")
        self.logger.info(f"   Method: Sequential job status polling (batch_scan_jobs table)")
        
        # Collect all batch job IDs (producer + consumers)
        batch_ids = [str(producer_job.id)]  # Subfinder
        batch_ids.extend([str(job.id) for job in consumer_jobs.values()])  # DNSx, HTTPx, etc.
        
        self.logger.info(f"   Monitoring {len(batch_ids)} batch jobs:")
        self.logger.info(f"     • Producer: {producer_job.id} (subfinder)")
        for module, job in consumer_jobs.items():
            self.logger.info(f"     • Consumer: {job.id} ({module})")
        
        # Wait for ALL jobs to reach terminal status (completed/failed/timeout)
        try:
            job_completion_result = await self._wait_for_jobs_completion(
                job_ids=batch_ids,
                timeout=3600,  # 1 hour timeout (same as before)
                check_interval=10  # Check every 10 seconds
            )
            
            # Map result to match old format for backwards compatibility
            monitor_result = {
                "status": "complete" if job_completion_result["status"] == "completed" else job_completion_result["status"],
                "module_statuses": job_completion_result["module_statuses"],
                "successful_modules": job_completion_result["successful_modules"],
                "total_modules": job_completion_result["total_modules"],
                "elapsed_seconds": job_completion_result["elapsed_seconds"],
                "checks_performed": job_completion_result["checks_performed"]
            }
            
        except Exception as e:
            self.logger.error(f"❌ Job monitoring error: {str(e)}")
            monitor_result = {
                "status": "error",
                "error": str(e),
                "module_statuses": {},
                "successful_modules": 0,
                "total_modules": len(batch_ids)
            }
        
        pipeline_duration = (datetime.utcnow() - pipeline_start).total_seconds()
        
        self.logger.info(f"📊 Job monitoring result: {monitor_result.get('status', 'unknown')}")
        self.logger.info(f"   Duration: {pipeline_duration:.1f}s")
        self.logger.info(f"   Successful modules: {monitor_result.get('successful_modules', 0)}/{monitor_result.get('total_modules', 0)}")
        
        # Log any failed modules
        failed_modules = [
            module for module, status in monitor_result.get("module_statuses", {}).items()
            if status not in ["completed", "running"]
        ]
        if failed_modules:
            self.logger.warning(f"⚠️  Failed/timeout modules: {', '.join(failed_modules)}")
        
        # ============================================================
        # STEP 6: Cleanup and Results
        # ============================================================
        
        # Optional: Clean up stream (keep for debugging by default)
        # await stream_coordinator.cleanup_stream(stream_key, delete_stream=False)
        
        # Build results in same format as execute_pipeline (producer + all consumers)
        results = []
        
        # Producer result
        # Use module-specific status from job monitoring (more accurate than overall status)
        producer_status = monitor_result.get("module_statuses", {}).get("subfinder", "unknown")
        results.append({
            "module": "subfinder",
            "status": producer_status,
            "scan_job_id": str(producer_job.id),
            "task_arn": producer_task_arn,
            "role": "producer",
            "started_at": pipeline_start.isoformat(),
            "completed_at": datetime.utcnow().isoformat()
        })
        
        # All consumer results (dnsx, httpx, etc.)
        for module in consumer_modules:
            consumer_status = monitor_result.get("module_statuses", {}).get(module, "unknown")
            results.append({
                "module": module,
                "status": consumer_status,
                "scan_job_id": str(consumer_jobs[module].id),
                "task_arn": consumer_task_arns[module],
                "role": "consumer",
                "started_at": pipeline_start.isoformat(),
                "completed_at": datetime.utcnow().isoformat()
            })
        
        successful_modules = sum(1 for r in results if r["status"] == "completed")
        
        self.logger.info(f"✅ Streaming pipeline completed")
        self.logger.info(f"   Producer: subfinder")
        self.logger.info(f"   Consumers: {', '.join(consumer_modules)}")
        self.logger.info(f"   Successful: {successful_modules}/{len(results)} modules")
        self.logger.info(f"   Duration: {pipeline_duration:.1f}s")
        
        return {
            "pipeline_type": "streaming",
            "pipeline": ["subfinder", "dnsx"],
            "results": results,
            "total_modules": len(results),
            "successful_modules": successful_modules,
            "failed_modules": len(results) - successful_modules,
            "duration_seconds": pipeline_duration,
            "status": "completed" if successful_modules == len(results) else "partial_failure",
            "stream_key": stream_key,
            "stream_length": monitor_result.get("stream_length", 0),
            "monitor_result": monitor_result,
            "job_monitoring": {
                "method": "sequential_job_polling",
                "module_statuses": monitor_result.get("module_statuses", {}),
                "checks_performed": monitor_result.get("checks_performed", 0),
                "elapsed_seconds": monitor_result.get("elapsed_seconds", 0)
            }
        }
    
    async def _create_batch_scan_job(
        self,
        asset_id: str,
        module: str,
        scan_request: EnhancedAssetScanRequest,
        user_id: str,
        parent_scan_job_id: str = None
    ) -> "BatchScanJob":
        """
        Create a BatchScanJob record for a module.
        
        This is used by streaming pipeline to create separate jobs for
        producer and consumer modules.
        
        Args:
            asset_id: Asset UUID
            module: Module name (e.g., "subfinder", "dnsx")
            scan_request: Original scan request
            user_id: User UUID
            parent_scan_job_id: Optional parent scan job ID
            
        Returns:
            BatchScanJob Pydantic model
        """
        from ..schemas.batch import BatchScanJob, BatchType
        import uuid
        
        # Get asset domains for this module
        # For streaming, we use the same domain list for both producer and consumer
        asset_response = self.supabase.table("assets").select("*").eq("id", asset_id).execute()
        
        if not asset_response.data:
            raise ValueError(f"Asset not found: {asset_id}")
        
        asset = asset_response.data[0]
        
        # Query apex_domains table to get actual domains
        # Note: parent_domains doesn't exist on assets table - domains are in apex_domains table
        apex_response = self.supabase.table("apex_domains")\
            .select("domain")\
            .eq("asset_id", asset_id)\
            .eq("is_active", True)\
            .execute()
        
        parent_domains = [record["domain"] for record in apex_response.data]
        
        self.logger.info(f"📍 Retrieved {len(parent_domains)} active apex domains for asset {asset_id}")
        
        # Create batch job record
        batch_job_data = {
            "id": str(uuid.uuid4()),
            "module": module,
            "status": "pending",
            "user_id": user_id,
            "batch_domains": parent_domains,  # Fixed: Use batch_domains (text[]) instead of parent_domains
            "total_domains": len(parent_domains),
            "batch_type": BatchType.SINGLE_ASSET.value,  # Fixed: SINGLE_MODULE doesn't exist in enum
            "allocated_cpu": 1024,  # Default CPU units
            "allocated_memory": 2048,  # Default memory in MB
            "asset_scan_mapping": {domain: parent_scan_job_id for domain in parent_domains},  # 🔧 FIX: Map each domain to the asset_scan_id
            "metadata": {  # Store additional context in metadata instead
                "asset_id": asset_id,
                "parent_scan_job_id": parent_scan_job_id,  # Fixed: Use correct parameter name
                "priority": scan_request.priority if scan_request else 3,
                "streaming_mode": True
            }
        }
        
        # Insert into database
        insert_response = self.supabase.table("batch_scan_jobs").insert(batch_job_data).execute()
        
        if not insert_response.data:
            raise Exception(f"Failed to create batch scan job for {module}")
        
        # Return as Pydantic model
        return BatchScanJob(**insert_response.data[0])


# Global singleton
scan_pipeline = ScanPipeline()
