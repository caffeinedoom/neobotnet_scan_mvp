"""
Batch Optimizer Service for Reconnaissance Scans
================================================

Intelligent batch processing that optimizes resource allocation and
minimizes costs through cross-asset domain grouping.

Key Features:
• Cross-asset domain batching for maximum efficiency
• Dynamic resource allocation based on workload
• Cost optimization through intelligent grouping
• Module-aware batch sizing

Performance Goals:
• 40-60% cost reduction vs individual scans
• 30-50% faster completion through optimized batching
• Minimal database writes (batches vs individual jobs)
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status
import logging

from ..core.supabase_client import supabase_client
from ..schemas.batch import (
    BatchOptimizationRequest, BatchOptimizationResult, BatchScanJob,
    BatchType, BatchStatus, ResourceProfile, ModuleProfile,
    BatchDomainAssignment, DomainAssignmentStatus
)

logger = logging.getLogger(__name__)

class BatchOptimizer:
    """
    Intelligent batch optimization for reconnaissance scans.
    
    This service groups domains across multiple assets to optimize
    resource utilization and minimize costs while maintaining
    asset-level progress tracking.
    """
    
    def __init__(self):
        self.supabase = supabase_client.service_client
        self.module_profiles_cache: Dict[str, ModuleProfile] = {}
        
    async def optimize_scans(self, request: BatchOptimizationRequest) -> BatchOptimizationResult:
        """
        Optimize multiple asset scan requests into efficient batches.
        
        Algorithm:
        1. Collect all domains across asset scans
        2. Group by module for optimal resource allocation  
        3. Create batches within module capacity limits
        4. Calculate resource profiles for each batch
        5. Estimate cost savings vs individual processing
        
        Args:
            request: Batch optimization request with asset scans and modules
            
        Returns:
            BatchOptimizationResult with optimized batch jobs
        """
        try:
            logger.info(f"Starting batch optimization for {len(request.asset_scan_requests)} asset scans")
            
            # Step 1: Extract and validate all domains
            all_domains = []
            asset_scan_mapping = {}  # domain -> asset_scan_id
            asset_scan_records = {}  # asset_scan_id -> asset_scan_record
            
            for asset_request in request.asset_scan_requests:
                asset_id = asset_request.get("asset_id")
                domains = asset_request.get("domains", [])
                
                # 🔧 OPTION B: Generate asset_scan_id here instead of expecting it to exist
                asset_scan_id = asset_request.get("asset_scan_id")
                if not asset_scan_id:
                    asset_scan_id = str(uuid.uuid4())
                
                # Store asset_scan_record data for batch_execution to use
                asset_scan_record = asset_request.get("asset_scan_record")
                if asset_scan_record:
                    asset_scan_records[asset_scan_id] = asset_scan_record
                
                if not domains:
                    # For database-fetch modules (DNSX), empty domains is valid
                    # Container will fetch from database using metadata
                    if asset_scan_record and asset_scan_record.get('metadata', {}).get('dnsx_metadata'):
                        logger.info(f"Empty domains allowed for DNSX database-fetch mode (asset_scan_id: {asset_scan_id})")
                    else:
                        continue
                    
                for domain in domains:
                    all_domains.append(domain)
                    asset_scan_mapping[domain] = asset_scan_id
            
            # Check if we have domains OR if this is a DNSX database-fetch request
            has_dnsx_metadata = any(
                record.get('metadata', {}).get('dnsx_metadata') 
                for record in asset_scan_records.values()
            )
            
            if not all_domains and not has_dnsx_metadata:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid domains found in asset scan requests"
                )
            
            logger.info(f"Processing {len(all_domains)} total domains across {len(request.modules)} modules")
            
            # Step 2: Create optimized batches for each module
            all_batch_jobs = []
            total_estimated_duration = 0
            
            for module in request.modules:
                module_batches = await self._create_module_batches(
                    module=module,
                    domains=all_domains,
                    asset_scan_mapping=asset_scan_mapping,
                    asset_scan_records=asset_scan_records,
                    user_id=request.user_id,
                    priority=request.priority
                )
                
                all_batch_jobs.extend(module_batches)
                
                # Add to total duration (modules can run in parallel)
                module_duration = max([batch.estimated_duration_minutes for batch in module_batches], default=0)
                total_estimated_duration = max(total_estimated_duration, module_duration)
            
            # Step 3: Calculate cost savings
            cost_savings = self._calculate_cost_savings(
                total_domains=len(all_domains),
                total_batches=len(all_batch_jobs),
                modules=request.modules
            )
            
            # Step 4: Determine optimization strategy
            strategy = self._get_optimization_strategy(
                total_domains=len(all_domains),
                total_batches=len(all_batch_jobs),
                modules=request.modules
            )
            
            result = BatchOptimizationResult(
                total_domains=len(all_domains),
                total_batches=len(all_batch_jobs),
                estimated_cost_savings_percent=cost_savings,
                estimated_duration_minutes=total_estimated_duration,
                batch_jobs=all_batch_jobs,
                optimization_strategy=strategy
            )
            
            logger.info(f"Batch optimization complete: {len(all_batch_jobs)} batches, {cost_savings:.1f}% cost savings")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Batch optimization failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Batch optimization failed: {str(e)}"
            )
    
    async def _create_module_batches(
        self, 
        module: str, 
        domains: List[str],
        asset_scan_mapping: Dict[str, str],
        asset_scan_records: Dict[str, Dict[str, Any]],
        user_id: uuid.UUID,
        priority: int
    ) -> List[BatchScanJob]:
        """Create optimized batches for a specific module."""
        
        # Get module profile for batching capabilities
        module_profile = await self._get_module_profile(module)
        
        # Special handling for database-fetch modules (DNSX)
        if module == "dnsx":
            logger.info(f"🔍 DNSX detected - using database fetch batch creation")
            
            # Extract dnsx_metadata from asset_scan_records
            dnsx_metadata = None
            for record in asset_scan_records.values():
                metadata = record.get('metadata', {})
                dnsx_metadata = metadata.get('dnsx_metadata')
                if dnsx_metadata:
                    break
            
            if not dnsx_metadata or not dnsx_metadata.get('fetch_from_database'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="DNSX module requires dnsx_metadata with fetch_from_database flag"
                )
            
            subdomain_count = dnsx_metadata.get('subdomain_count', 0)
            if subdomain_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="DNSX module requires subdomain_count > 0 in metadata"
                )
            
            logger.info(f"✅ Creating database-fetch batch for {subdomain_count} subdomains")
            
            # Create special database-fetch batch
            return await self._create_database_fetch_batch(
                module, subdomain_count, dnsx_metadata, asset_scan_mapping, 
                asset_scan_records, user_id, priority, module_profile
            )
        
        if not module_profile.supports_batching:
            # Create individual batches for each domain
            return await self._create_individual_batches(
                module, domains, asset_scan_mapping, asset_scan_records, user_id, priority, module_profile
            )
        
        # Create optimized multi-domain batches
        return await self._create_optimized_batches(
            module, domains, asset_scan_mapping, asset_scan_records, user_id, priority, module_profile
        )
    
    async def _create_optimized_batches(
        self,
        module: str,
        domains: List[str], 
        asset_scan_mapping: Dict[str, str],
        asset_scan_records: Dict[str, Dict[str, Any]],
        user_id: uuid.UUID,
        priority: int,
        module_profile: ModuleProfile
    ) -> List[BatchScanJob]:
        """Create optimized multi-domain batches."""
        
        batches = []
        max_batch_size = module_profile.max_batch_size
        
        # Split domains into optimal batch sizes
        for i in range(0, len(domains), max_batch_size):
            batch_domains = domains[i:i + max_batch_size]
            
            # Calculate resources for this batch size
            resource_profile = await self._calculate_batch_resources(module, len(batch_domains))
            
            # Determine batch type and extract asset_id for single-asset batches
            asset_ids_in_batch = set(
                asset_scan_records[asset_scan_id].get("asset_id")
                for asset_scan_id in [asset_scan_mapping[d] for d in batch_domains]
                if asset_scan_id in asset_scan_records
            )
            is_single_asset = len(asset_ids_in_batch) == 1
            batch_type = BatchType.SINGLE_ASSET if is_single_asset else BatchType.MULTI_ASSET
            
            # Build metadata
            batch_metadata = {
                "optimization_batch": True,
                "priority": priority,
                "module_profile_version": module_profile.version,
                "batch_strategy": "multi_domain_optimized",
                "asset_scan_records": asset_scan_records
            }
            
            # ✅ NEW: Add asset_id for single-asset batches (required for DNSX)
            if is_single_asset:
                batch_metadata["asset_id"] = list(asset_ids_in_batch)[0]
            
            # Create batch job
            batch_job = BatchScanJob(
                id=uuid.uuid4(),
                user_id=user_id,
                batch_type=batch_type,
                module=module,
                status=BatchStatus.PENDING,
                total_domains=len(batch_domains),
                batch_domains=batch_domains,
                asset_scan_mapping={domain: asset_scan_mapping[domain] for domain in batch_domains},
                allocated_cpu=resource_profile.cpu,
                allocated_memory=resource_profile.memory,
                estimated_duration_minutes=resource_profile.estimated_duration_minutes,
                resource_profile=resource_profile.model_dump(),
                created_at=datetime.utcnow(),
                estimated_completion=datetime.utcnow() + timedelta(minutes=resource_profile.estimated_duration_minutes),
                metadata=batch_metadata
            )
            
            batches.append(batch_job)
        
        logger.info(f"Created {len(batches)} optimized batches for {module} module")
        return batches
    
    async def _create_individual_batches(
        self,
        module: str,
        domains: List[str],
        asset_scan_mapping: Dict[str, str],
        asset_scan_records: Dict[str, Dict[str, Any]],
        user_id: uuid.UUID,
        priority: int,
        module_profile: ModuleProfile
    ) -> List[BatchScanJob]:
        """Create individual batches for modules that don't support multi-domain processing."""
        
        batches = []
        
        for domain in domains:
            resource_profile = await self._calculate_batch_resources(module, 1)
            
            # Extract asset_id for this domain
            asset_scan_id = asset_scan_mapping[domain]
            asset_id = asset_scan_records[asset_scan_id].get("asset_id") if asset_scan_id in asset_scan_records else None
            
            # Build metadata
            batch_metadata = {
                "optimization_batch": False,
                "priority": priority,
                "module_profile_version": module_profile.version,
                "batch_strategy": "individual_domains",
                "asset_scan_records": asset_scan_records
            }
            
            # ✅ NEW: Add asset_id (required for DNSX)
            if asset_id:
                batch_metadata["asset_id"] = asset_id
            
            batch_job = BatchScanJob(
                id=uuid.uuid4(),
                user_id=user_id,
                batch_type=BatchType.SINGLE_ASSET,
                module=module,
                status=BatchStatus.PENDING,
                total_domains=1,
                batch_domains=[domain],
                asset_scan_mapping={domain: asset_scan_mapping[domain]},
                allocated_cpu=resource_profile.cpu,
                allocated_memory=resource_profile.memory,
                estimated_duration_minutes=resource_profile.estimated_duration_minutes,
                resource_profile=resource_profile.model_dump(),
                created_at=datetime.utcnow(),
                estimated_completion=datetime.utcnow() + timedelta(minutes=resource_profile.estimated_duration_minutes),
                metadata=batch_metadata
            )
            
            batches.append(batch_job)
        
        logger.info(f"Created {len(batches)} individual batches for {module} module")
        return batches
    
    async def _get_parent_domains_for_asset(self, asset_id: str) -> List[str]:
        """
        Query parent domains (apex domains) for an asset from the database.
        
        This is used to create proper asset_scan_mapping for DNSX module,
        where mapping keys should be parent domains (not asset_id).
        
        Args:
            asset_id: UUID of the asset
            
        Returns:
            List of parent domain names (e.g., ["epicgames.com", "rocketleague.com"])
        """
        try:
            result = self.supabase.table("apex_domains")\
                .select("domain")\
                .eq("asset_id", asset_id)\
                .execute()
            
            domains = [row['domain'] for row in result.data]
            logger.info(f"✅ Found {len(domains)} parent domains for asset {asset_id}")
            return domains
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch parent domains for asset {asset_id}: {e}")
            return []
    
    async def _create_database_fetch_batch(
        self,
        module: str,
        subdomain_count: int,
        dnsx_metadata: Dict[str, Any],
        asset_scan_mapping: Dict[str, str],
        asset_scan_records: Dict[str, Dict[str, Any]],
        user_id: uuid.UUID,
        priority: int,
        module_profile: ModuleProfile
    ) -> List[BatchScanJob]:
        """
        Create batch jobs for database-fetch modules (DNSX).
        
        These modules fetch their input data directly from the database,
        so we pass empty batch_domains and use metadata for configuration.
        """
        batches = []
        max_batch_size = module_profile.max_batch_size
        asset_id = dnsx_metadata.get('asset_id')
        
        logger.info(f"Creating database-fetch batches: {subdomain_count} subdomains, "
                   f"max_batch_size={max_batch_size}, asset_id={asset_id}")
        
        # 🔧 FIX: For database-fetch mode, asset_scan_mapping is empty (no domains)
        # We need to populate it with parent_domain -> asset_scan_id mapping
        if not asset_scan_mapping and asset_scan_records:
            # Get the first (and only) asset_scan_id from asset_scan_records
            asset_scan_id = list(asset_scan_records.keys())[0] if asset_scan_records else None
            if asset_scan_id:
                # Query parent domains for this asset
                parent_domains = await self._get_parent_domains_for_asset(asset_id)
                
                # Create proper mapping: parent_domain -> asset_scan_id
                # This allows DNSX container to look up scan_job_id by parent_domain
                asset_scan_mapping = {domain: asset_scan_id for domain in parent_domains}
                
                logger.info(f"🔍 DEBUG [Backend Checkpoint]: Created asset_scan_mapping for DNSX")
                logger.info(f"   Parent domains fetched: {len(parent_domains)}")
                logger.info(f"   Mapping size: {len(asset_scan_mapping)} entries")
                logger.info(f"   ALL mapping keys (parent domains):")
                for domain in parent_domains:
                    logger.info(f"     - '{domain}' → '{asset_scan_id}'")
                logger.debug(f"   Asset scan ID: {asset_scan_id}")
        
        # Split into batches if subdomain_count > max_batch_size
        for batch_offset in range(0, subdomain_count, max_batch_size):
            batch_size = min(max_batch_size, subdomain_count - batch_offset)
            
            # Calculate resources for this batch size
            resource_profile = await self._calculate_batch_resources(module, batch_size)
            
            # Determine batch type (single asset for DNSX)
            batch_type = BatchType.SINGLE_ASSET
            
            # Build comprehensive metadata for container
            batch_metadata = {
                'fetch_from_database': True,
                'asset_id': asset_id,
                'subdomain_count': subdomain_count,
                'subdomain_batch_offset': batch_offset,
                'subdomain_batch_limit': batch_size,
                'optimization_batch': True,
                'priority': priority,
                'module_profile_version': module_profile.version,
                'batch_strategy': 'database_fetch',
                'asset_scan_records': asset_scan_records
            }
            
            # 🔍 DEBUG LOG: Before creating batch job
            logger.info(f"🔍 DEBUG [Backend Checkpoint]: Creating batch job #{len(batches) + 1}")
            logger.info(f"   Batch offset: {batch_offset}, Batch size: {batch_size}")
            logger.info(f"   asset_scan_mapping has {len(asset_scan_mapping)} entries")
            logger.info(f"   asset_scan_mapping keys: {list(asset_scan_mapping.keys())}")
            
            # Create batch job with EMPTY batch_domains (container fetches from DB)
            batch = BatchScanJob(
                id=uuid.uuid4(),
                user_id=user_id,
                batch_type=batch_type,
                module=module,
                status=BatchStatus.PENDING,
                total_domains=batch_size,
                batch_domains=[],  # ✅ EMPTY - container fetches from database
                asset_scan_mapping=asset_scan_mapping,
                allocated_cpu=resource_profile.cpu,
                allocated_memory=resource_profile.memory,
                estimated_duration_minutes=int(batch_size * module_profile.estimated_duration_per_domain // 60),
                resource_profile=resource_profile.model_dump(),  # Convert Pydantic model to dict
                created_at=datetime.utcnow(),
                estimated_completion=datetime.utcnow() + timedelta(
                    minutes=int(batch_size * module_profile.estimated_duration_per_domain // 60)
                ),
                metadata=batch_metadata
            )
            
            batches.append(batch)
            
            logger.info(f"Created database-fetch batch {batch.id}: "
                       f"{batch_size} subdomains (offset={batch_offset}), "
                       f"cpu={batch.allocated_cpu}, memory={batch.allocated_memory}MB")
        
        logger.info(f"✅ Created {len(batches)} database-fetch batch(es) for {subdomain_count} subdomains")
        return batches
    
    async def _get_module_profile(self, module_name: str) -> ModuleProfile:
        """Get module profile with caching."""
        
        if module_name in self.module_profiles_cache:
            return self.module_profiles_cache[module_name]
        
        # Query from database
        response = self.supabase.table("scan_module_profiles").select("*").eq(
            "module_name", module_name
        ).eq("is_active", True).order("version", desc=True).limit(1).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module profile not found: {module_name}"
            )
        
        profile_data = response.data[0]
        
        # Parse the profile
        module_profile = ModuleProfile(
            id=profile_data["id"],
            module_name=profile_data["module_name"],
            version=profile_data["version"],
            supports_batching=profile_data["supports_batching"],
            max_batch_size=profile_data["max_batch_size"],
            resource_scaling=profile_data["resource_scaling"],
            estimated_duration_per_domain=profile_data["estimated_duration_per_domain"],
            task_definition_template=profile_data["task_definition_template"],
            container_name=profile_data["container_name"],
            is_active=profile_data["is_active"],
            created_at=profile_data["created_at"],
            updated_at=profile_data["updated_at"]
        )
        
        # Cache it
        self.module_profiles_cache[module_name] = module_profile
        return module_profile
    
    async def _calculate_batch_resources(self, module_name: str, domain_count: int) -> ResourceProfile:
        """Calculate optimal resources for a batch using database function."""
        
        try:
            # Use the database function for consistent resource calculation
            response = self.supabase.rpc(
                "calculate_module_resources",
                {"p_module_name": module_name, "p_domain_count": domain_count}
            ).execute()
            
            if not response.data:
                raise Exception("No resource calculation returned")
            
            resource_data = response.data
            
            return ResourceProfile(
                cpu=resource_data["cpu"],
                memory=resource_data["memory"],
                estimated_duration_minutes=int(resource_data["estimated_duration_minutes"]),  # Ensure int, DB might return float
                description=resource_data["description"],
                domain_count=resource_data["domain_count"],
                module_name=resource_data["module_name"]
            )
            
        except Exception as e:
            logger.error(f"Resource calculation failed for {module_name}/{domain_count}: {str(e)}")
            # Fallback to basic allocation
            return ResourceProfile(
                cpu=256 * min(domain_count, 4),  # Scale up to 1 vCPU
                memory=512 * min(domain_count, 4),  # Scale up to 2GB
                estimated_duration_minutes=max(5, domain_count * 2),  # 2 min per domain
                description=f"Fallback allocation for {domain_count} domains",
                domain_count=domain_count,
                module_name=module_name
            )
    
    def _calculate_cost_savings(self, total_domains: int, total_batches: int, modules: List[str]) -> float:
        """Calculate estimated cost savings vs individual domain processing."""
        
        # Cost model: Each ECS task has fixed overhead + variable compute
        # Fixed overhead: ~$0.01 per task (networking, startup, etc.)
        # Variable: $0.04 per vCPU-hour + $0.005 per GB-hour
        
        # Current approach: would create total_domains * len(modules) tasks
        individual_tasks = total_domains * len(modules)
        
        # Batch approach: creates total_batches tasks
        batch_tasks = total_batches
        
        # Savings come from reduced task overhead and better resource utilization
        if individual_tasks == 0:
            return 0.0
        
        # Fixed overhead savings
        overhead_savings = (individual_tasks - batch_tasks) * 0.01
        
        # Resource utilization improvement (batching is ~20% more efficient)
        utilization_improvement = 0.20
        
        # Calculate percentage savings
        individual_cost = individual_tasks * 0.05  # Approximate cost per task
        batch_cost = batch_tasks * 0.05 * (1 - utilization_improvement)
        
        savings_percent = ((individual_cost - batch_cost) / individual_cost) * 100
        
        # Apply progressive cap based on scale to show realistic differences
        if total_domains <= 20:
            return min(savings_percent, 50.0)  # Small batches: up to 50%
        elif total_domains <= 100:
            return min(savings_percent, 65.0)  # Medium batches: up to 65%
        else:
            return min(savings_percent, 80.0)  # Large batches: up to 80%
    
    def _get_optimization_strategy(self, total_domains: int, total_batches: int, modules: List[str]) -> str:
        """Generate human-readable optimization strategy description."""
        
        if total_batches == 1:
            return f"Single optimized batch processing {total_domains} domains with {len(modules)} modules for maximum efficiency"
        
        if total_domains <= 50:
            return f"Small-scale optimization: {total_batches} batches for {total_domains} domains with efficient resource allocation"
        
        if total_domains <= 200:
            return f"Medium-scale optimization: {total_batches} batches for {total_domains} domains with cross-asset batching"
        
        return f"Large-scale optimization: {total_batches} intelligent batches for {total_domains} domains with enterprise-grade resource scaling"

# Global instance
batch_optimizer = BatchOptimizer()
