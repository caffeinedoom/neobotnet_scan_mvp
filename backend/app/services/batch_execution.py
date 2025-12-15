"""
Batch Execution Service for Reconnaissance Scans
===============================================

Handles the execution lifecycle of batch scan jobs including:
• Database storage and retrieval
• ECS task launching with dynamic resources
• Progress tracking and status updates
• Result aggregation back to asset scans

This service bridges the gap between batch optimization and 
actual container execution.
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging

from ..core.supabase_client import supabase_client
from ..schemas.batch import (
    BatchScanJob, BatchDomainAssignment, BatchStatus, 
    DomainAssignmentStatus, BatchProgressResponse, BatchScanResponse
)

logger = logging.getLogger(__name__)

class BatchExecutionService:
    """
    Manages the execution lifecycle of batch scan jobs.
    
    Responsibilities:
    • Store batch jobs and domain assignments to database
    • Launch ECS tasks with optimized resource allocation
    • Track progress across batch boundaries  
    • Aggregate results back to asset scan level
    """
    
    def __init__(self):
        self.supabase = supabase_client.service_client
        
    async def create_batch_jobs(self, batch_jobs: List[BatchScanJob]) -> Dict[str, Any]:
        """
        Store batch jobs to database and create domain assignments.
        
        Args:
            batch_jobs: List of optimized batch jobs to create
            
        Returns:
            Dict containing created batch job IDs and asset scan IDs
        """
        try:
            created_batch_ids = []
            created_asset_scan_ids = []  # 🔧 OPTION B: Collect asset_scan_ids for response
            inserted_asset_scan_ids = set()  # 🔧 Track which asset_scan_ids have been inserted to avoid duplicates
            
            for batch_job in batch_jobs:
                # Step 1: Create the batch job record
                batch_record = {
                    "id": str(batch_job.id),
                    "user_id": str(batch_job.user_id),
                    "batch_type": batch_job.batch_type.value,
                    "module": batch_job.module,
                    "status": batch_job.status.value,
                    "total_domains": batch_job.total_domains,
                    "completed_domains": batch_job.completed_domains,
                    "failed_domains": batch_job.failed_domains,
                    "batch_domains": batch_job.batch_domains,
                    "asset_scan_mapping": batch_job.asset_scan_mapping,
                    "allocated_cpu": batch_job.allocated_cpu,
                    "allocated_memory": batch_job.allocated_memory,
                    "estimated_duration_minutes": batch_job.estimated_duration_minutes,
                    "resource_profile": batch_job.resource_profile,
                    "created_at": batch_job.created_at.isoformat(),
                    "estimated_completion": batch_job.estimated_completion.isoformat() if batch_job.estimated_completion else None,
                    "retry_count": batch_job.retry_count,
                    "max_retries": batch_job.max_retries,
                    "metadata": batch_job.metadata
                }
                
                # Insert batch job
                response = self.supabase.table("batch_scan_jobs").insert(batch_record).execute()
                
                if not response.data:
                    raise Exception(f"Failed to create batch job {batch_job.id}")
                
                # 🔬 DIAGNOSTIC LOG 2: Before calling _create_asset_scan_jobs
                asset_scan_ids_in_mapping = list(set(batch_job.asset_scan_mapping.values()))
                logger.info(f"🔬 DIAGNOSTIC: About to call _create_asset_scan_jobs | batch_id={str(batch_job.id)[:8]}... | asset_scan_ids={asset_scan_ids_in_mapping} | source=batch_execution.create_batch_jobs | action=CALLING_CREATE_ASSET_SCAN_JOBS")
                
                # Step 2: Create asset scan job records (FK requirement)
                await self._create_asset_scan_jobs(batch_job, inserted_asset_scan_ids)
                
                # Step 3: Create domain assignments for progress tracking
                await self._create_domain_assignments(batch_job)
                
                created_batch_ids.append(str(batch_job.id))
                
                # 🔧 OPTION B: Collect asset_scan_ids for response
                batch_asset_scan_ids = list(set(batch_job.asset_scan_mapping.values()))
                created_asset_scan_ids.extend(batch_asset_scan_ids)
                
                logger.info(f"Created batch job {batch_job.id} with {batch_job.total_domains} domains")
            
            # 🔧 OPTION B: Return both batch_ids and asset_scan_ids
            return {
                "batch_ids": created_batch_ids,
                "asset_scan_ids": list(set(created_asset_scan_ids))  # Remove duplicates
            }
            
        except Exception as e:
            logger.error(f"Failed to create batch jobs: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create batch jobs: {str(e)}"
            )
    
    async def _create_asset_scan_jobs(self, batch_job: BatchScanJob, inserted_asset_scan_ids: set = None):
        """Create asset scan job records for FK constraint satisfaction.
        
        Args:
            batch_job: The batch job containing asset scan information
            inserted_asset_scan_ids: Set of asset_scan_ids that have already been inserted (to prevent duplicates)
        """
        
        if inserted_asset_scan_ids is None:
            inserted_asset_scan_ids = set()
        
        # 🔧 OPTION B: Use asset_scan_records from batch_job metadata instead of constructing from database
        asset_scan_records_from_metadata = batch_job.metadata.get('asset_scan_records', {})
        
        # Get unique asset scan IDs from the mapping
        unique_asset_scan_ids = set(batch_job.asset_scan_mapping.values())
        
        # 🔧 Filter out already inserted asset_scan_ids to prevent duplicate key errors
        new_asset_scan_ids = unique_asset_scan_ids - inserted_asset_scan_ids
        
        if not new_asset_scan_ids:
            logger.info(f"All asset_scan_ids for batch {batch_job.id} already inserted, skipping")
            return
        
        logger.info(f"Creating asset_scan_jobs for {len(new_asset_scan_ids)} new asset_scan_ids (skipped {len(unique_asset_scan_ids - new_asset_scan_ids)} already inserted)")
        
        asset_scan_records = []
        for asset_scan_id in new_asset_scan_ids:
            # Find domains for this asset scan
            domains_for_asset = [domain for domain, scan_id in batch_job.asset_scan_mapping.items() 
                               if scan_id == asset_scan_id]
            
            # 🔧 OPTION B: Get asset_scan_record from metadata instead of constructing it
            if asset_scan_id in asset_scan_records_from_metadata:
                # Use the prepared asset_scan_record from asset_service
                asset_scan_record = asset_scan_records_from_metadata[asset_scan_id].copy()
                
                # 🔬 DIAGNOSTIC: Verify asset_id is present in the record
                if "asset_id" not in asset_scan_record:
                    logger.error(f"🚨 BUG DETECTED: asset_scan_record from metadata is missing asset_id field for {asset_scan_id}")
                    raise Exception(f"asset_scan_record missing asset_id - this should never happen after the fix")
                
                logger.info(f"✅ Successfully retrieved asset_scan_record from metadata: asset_scan_id={asset_scan_id}, asset_id={asset_scan_record['asset_id']}, domains_count={len(domains_for_asset)}")
                
                # Update the asset_scan_record with the generated asset_scan_id
                asset_scan_record["id"] = asset_scan_id
                
                # Update domain count in case batch optimization changed the domain list
                asset_scan_record["total_domains"] = len(domains_for_asset)
                
                # Update metadata to include batch information
                if "metadata" not in asset_scan_record:
                    asset_scan_record["metadata"] = {}
                
                asset_scan_record["metadata"].update({
                    "batch_mode": True, 
                    "batch_id": str(batch_job.id),
                    "domains": domains_for_asset,
                    "scan_initiated_by": "unified_batch_processing",
                    "optimization_applied": True
                })
                
            else:
                # Fallback: construct record if not found in metadata
                logger.error(f"🚨 Asset scan record not found in metadata for {asset_scan_id} - this indicates a bug in asset_service")
                
                # 🔧 FIX: Extract asset_id from the first domain mapped to this asset_scan_id
                # This is a defensive fallback - ideally metadata should always have the record
                asset_id = None
                for domain, scan_id in batch_job.asset_scan_mapping.items():
                    if scan_id == asset_scan_id:
                        # We need to query the database to find which asset this domain belongs to
                        # This is inefficient but necessary for the fallback
                        try:
                            domain_query = self.supabase.table("apex_domains").select("asset_id").eq("domain", domain).limit(1).execute()
                            if domain_query.data:
                                asset_id = domain_query.data[0]["asset_id"]
                                break
                        except Exception as e:
                            logger.error(f"Failed to lookup asset_id for domain {domain}: {str(e)}")
                            continue
                
                if not asset_id:
                    # Critical error - we cannot create asset_scan_job without asset_id
                    raise Exception(f"Cannot determine asset_id for asset_scan_id {asset_scan_id}. This is a critical bug.")
                
                logger.warning(f"Using fallback asset_id lookup: {asset_id} for asset_scan_id {asset_scan_id}")
                
                asset_scan_record = {
                    "id": asset_scan_id,
                    "user_id": str(batch_job.user_id),
                    "asset_id": asset_id,  # ✅ FIX: Now includes asset_id!
                    "modules": [batch_job.module],
                    "status": "running",
                    "total_domains": len(domains_for_asset),
                    "completed_domains": 0,
                    "active_domains_only": True,
                    "created_at": datetime.utcnow().isoformat(),
                    "estimated_completion": batch_job.estimated_completion.isoformat() if batch_job.estimated_completion else None,
                    "metadata": {
                        "batch_mode": True, 
                        "batch_id": str(batch_job.id),
                        "domains": domains_for_asset,
                        "scan_initiated_by": "batch_processing_fallback",
                        "constructed_in_batch_execution": True,
                        "fallback_used": True  # ✅ Mark that fallback was used
                    }
                }
            
            asset_scan_records.append(asset_scan_record)
        
        if asset_scan_records:
            # 🔬 DIAGNOSTIC LOG 3: Before ONLY insert attempt (OPTION B FIX)
            scan_ids_to_insert = [record["id"] for record in asset_scan_records]
            logger.info(f"🔬 DIAGNOSTIC: About to INSERT asset_scan_jobs (ONLY ATTEMPT - OPTION B) | scan_ids={scan_ids_to_insert} | count={len(asset_scan_records)} | source=batch_execution._create_asset_scan_jobs | action=SINGLE_INSERT_ATTEMPT")
            
            try:
                response = self.supabase.table("asset_scan_jobs").insert(asset_scan_records).execute()
                
                if response.data:
                    logger.info(f"✅ Successfully created {len(response.data)} asset_scan_job records")
                    # 🔧 Mark these asset_scan_ids as inserted
                    inserted_asset_scan_ids.update(new_asset_scan_ids)
                else:
                    raise Exception("Insert returned no data")
                
            except Exception as e:
                logger.error(f"Error creating asset scan jobs: {str(e)}")
                raise Exception(f"Failed to create asset scan jobs: {str(e)}")
    
    async def _create_domain_assignments(self, batch_job: BatchScanJob):
        """Create individual domain assignments for progress tracking."""
        
        assignments = []
        
        for domain in batch_job.batch_domains:
            asset_scan_id = batch_job.asset_scan_mapping.get(domain)
            if not asset_scan_id:
                logger.warning(f"No asset scan mapping found for domain: {domain}")
                continue
            
            assignment = {
                "id": str(uuid.uuid4()),
                "batch_scan_id": str(batch_job.id),
                "domain": domain,
                "asset_scan_id": asset_scan_id,
                "status": DomainAssignmentStatus.PENDING.value
            }
            
            assignments.append(assignment)
        
        if assignments:
            response = self.supabase.table("batch_domain_assignments").insert(assignments).execute()
            
            if not response.data:
                logger.error(f"Failed to create domain assignments for batch {batch_job.id}")
                # Don't fail the entire batch creation for this
        
    async def launch_batch_execution(self, batch_id: str) -> Dict[str, Any]:
        """
        Launch ECS execution for a batch job.
        
        Args:
            batch_id: ID of the batch job to execute
            
        Returns:
            Execution details including ECS task ARN
        """
        try:
            # Get batch job details
            batch_job = await self._get_batch_job(batch_id)
            
            if batch_job["status"] != BatchStatus.PENDING.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Batch job {batch_id} is not in pending status"
                )
            
            # Update status to running
            await self._update_batch_status(batch_id, BatchStatus.RUNNING, {"started_at": datetime.utcnow().isoformat()})
            
            # Launch ECS task with optimized resources
            ecs_result = await self._launch_ecs_task(batch_job)
            
            # Update batch with ECS task ARN
            await self._update_batch_job(batch_id, {
                "ecs_task_arn": ecs_result.get("task_arn"),
                "metadata": {
                    **batch_job["metadata"],
                    "ecs_launch_time": datetime.utcnow().isoformat(),
                    "ecs_cluster": ecs_result.get("cluster"),
                    "actual_cpu": ecs_result.get("cpu"),
                    "actual_memory": ecs_result.get("memory")
                }
            })
            
            logger.info(f"Successfully launched batch {batch_id} with ECS task {ecs_result.get('task_arn')}")
            
            return {
                "batch_id": batch_id,
                "status": "launched",
                "ecs_task_arn": ecs_result.get("task_arn"),
                "estimated_completion": batch_job["estimated_completion"]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to launch batch execution {batch_id}: {str(e)}")
            
            # Update batch status to failed
            await self._update_batch_status(batch_id, BatchStatus.FAILED, {
                "error_message": str(e),
                "completed_at": datetime.utcnow().isoformat()
            })
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to launch batch execution: {str(e)}"
            )
    
    async def _launch_ecs_task(self, batch_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Launch ECS task for batch execution.
        
        This will integrate with the existing workflow_orchestrator but with
        optimized resource allocation from the batch job.
        """
        
        # For now, return a mock response. In the next phase, we'll integrate
        # with the actual ECS launch logic from workflow_orchestrator
        
        return {
            "task_arn": f"arn:aws:ecs:us-east-1:123456789012:task/batch-{batch_job['id'][:8]}",
            "cluster": "neobotnet-v2-dev-cluster",
            "cpu": batch_job["allocated_cpu"],
            "memory": batch_job["allocated_memory"],
            "status": "launched"
        }
    
    async def get_batch_progress(self, batch_id: str) -> BatchProgressResponse:
        """
        Get progress information for a batch job.
        
        Args:
            batch_id: ID of the batch job
            
        Returns:
            BatchProgressResponse with current status and progress
        """
        try:
            batch_job = await self._get_batch_job(batch_id)
            
            # Calculate progress percentage
            total_domains = batch_job["total_domains"]
            completed_domains = batch_job["completed_domains"]
            failed_domains = batch_job["failed_domains"]
            
            if total_domains == 0:
                progress_percentage = 0.0
            else:
                progress_percentage = ((completed_domains + failed_domains) / total_domains) * 100
            
            # Determine current phase
            if batch_job["status"] == BatchStatus.PENDING.value:
                current_phase = "queued"
            elif batch_job["status"] == BatchStatus.RUNNING.value:
                if progress_percentage < 10:
                    current_phase = "initializing"
                elif progress_percentage < 90:
                    current_phase = "scanning"
                else:
                    current_phase = "finalizing"
            elif batch_job["status"] == BatchStatus.COMPLETED.value:
                current_phase = "completed"
            elif batch_job["status"] == BatchStatus.FAILED.value:
                current_phase = "failed"
            else:
                current_phase = "unknown"
            
            return BatchProgressResponse(
                batch_id=uuid.UUID(batch_id),
                status=BatchStatus(batch_job["status"]),
                progress_percentage=progress_percentage,
                completed_domains=completed_domains,
                failed_domains=failed_domains,
                total_domains=total_domains,
                estimated_completion=datetime.fromisoformat(batch_job["estimated_completion"]) if batch_job["estimated_completion"] else None,
                current_phase=current_phase,
                ecs_task_arn=batch_job.get("ecs_task_arn")
            )
            
        except Exception as e:
            logger.error(f"Failed to get batch progress {batch_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch job not found or access denied: {batch_id}"
            )
    
    async def update_domain_progress(self, batch_id: str, domain: str, status: DomainAssignmentStatus, subdomains_found: int = 0, error_message: str = None):
        """
        Update progress for an individual domain within a batch.
        
        Args:
            batch_id: ID of the batch job
            domain: Domain that was processed
            status: New status for the domain
            subdomains_found: Number of subdomains discovered
            error_message: Error message if failed
        """
        try:
            update_data = {
                "status": status.value,
                "subdomains_found": subdomains_found
            }
            
            if status == DomainAssignmentStatus.RUNNING:
                update_data["started_at"] = datetime.utcnow().isoformat()
            elif status in [DomainAssignmentStatus.COMPLETED, DomainAssignmentStatus.FAILED]:
                update_data["completed_at"] = datetime.utcnow().isoformat()
                if error_message:
                    update_data["error_message"] = error_message
            
            # Update domain assignment
            response = self.supabase.table("batch_domain_assignments").update(update_data).eq(
                "batch_scan_id", batch_id
            ).eq("domain", domain).execute()
            
            # Update batch job progress counters
            await self._refresh_batch_progress(batch_id)
            
            logger.debug(f"Updated domain progress: {batch_id}/{domain} -> {status.value}")
            
        except Exception as e:
            logger.error(f"Failed to update domain progress {batch_id}/{domain}: {str(e)}")
            # Don't raise exception for progress updates to avoid breaking the scan
    
    async def _refresh_batch_progress(self, batch_id: str):
        """Refresh batch job progress counters based on domain assignments."""
        
        try:
            # Get domain assignment counts
            response = self.supabase.table("batch_domain_assignments").select(
                "status"
            ).eq("batch_scan_id", batch_id).execute()
            
            if not response.data:
                return
            
            assignments = response.data
            completed_count = sum(1 for a in assignments if a["status"] == DomainAssignmentStatus.COMPLETED.value)
            failed_count = sum(1 for a in assignments if a["status"] == DomainAssignmentStatus.FAILED.value)
            total_count = len(assignments)
            
            # Update batch job counters
            update_data = {
                "completed_domains": completed_count,
                "failed_domains": failed_count
            }
            
            # Check if batch is complete
            if (completed_count + failed_count) >= total_count:
                if failed_count == 0:
                    update_data["status"] = BatchStatus.COMPLETED.value
                else:
                    update_data["status"] = BatchStatus.COMPLETED.value  # Partial success is still completion
                update_data["completed_at"] = datetime.utcnow().isoformat()
            
            await self._update_batch_job(batch_id, update_data)
            
        except Exception as e:
            logger.error(f"Failed to refresh batch progress {batch_id}: {str(e)}")
    
    async def _get_batch_job(self, batch_id: str) -> Dict[str, Any]:
        """Get batch job details from database."""
        
        response = self.supabase.table("batch_scan_jobs").select("*").eq("id", batch_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch job not found: {batch_id}"
            )
        
        return response.data[0]
    
    async def _update_batch_status(self, batch_id: str, status: BatchStatus, additional_data: Dict[str, Any] = None):
        """Update batch job status."""
        
        update_data = {"status": status.value}
        if additional_data:
            update_data.update(additional_data)
        
        await self._update_batch_job(batch_id, update_data)
    
    async def _update_batch_job(self, batch_id: str, update_data: Dict[str, Any]):
        """Update batch job with given data."""
        
        response = self.supabase.table("batch_scan_jobs").update(update_data).eq("id", batch_id).execute()
        
        if not response.data:
            logger.error(f"Failed to update batch job {batch_id}")

# Global instance
batch_execution_service = BatchExecutionService()
