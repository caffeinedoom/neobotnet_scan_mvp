"""
Multi-tenant  asset management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, BackgroundTasks
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

from ...core.dependencies import get_current_user
from ...schemas.auth import UserResponse
from ...schemas.assets import (
    Asset, AssetCreate, AssetUpdate, AssetWithStats,
    ApexDomain, ApexDomainCreate, ApexDomainUpdate, ApexDomainWithStats,
    AssetWithDomains, UserAssetSummary, AssetScanRequest, AssetScanResponse, BulkAssetOperation,
    PaginatedSubdomainResponse, SubdomainWithAssetInfo, PaginationInfo, SubdomainFilters,
    # NEW: Enhanced schemas for consolidated endpoint
    EnhancedAssetScanRequest, EnhancedAssetScanResponse
)
from ...services.asset_service import asset_service
from ...services.module_registry import module_registry
from ...services.dns_service import dns_service
from ...schemas.dns import (
    DNSRecord, DNSRecordListResponse, DNSRecordWithAssetInfo, 
    PaginatedDNSResponse, PaginatedGroupedDNSResponse
)

router = APIRouter(prefix="/assets", tags=["assets"])
logger = logging.getLogger(__name__)

# ================================================================
# Asset CRUD Operations
# ================================================================

@router.post("", response_model=Asset, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_data: AssetCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new asset."""
    return await asset_service.create_asset(asset_data, current_user.id)

@router.get("", response_model=List[AssetWithStats])
async def get_assets(
    include_stats: bool = Query(True, description="Include asset statistics"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get all assets for the current user."""
    return await asset_service.get_assets(current_user.id, include_stats)

@router.get("/summary", response_model=UserAssetSummary)
async def get_user_asset_summary(
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user's asset summary statistics."""
    return await asset_service.get_user_summary(current_user.id)

# ================================================================
# Asset Scan Job Management (MOVED HERE - Must come before /{asset_id})
# ================================================================

@router.get("/scans", response_model=List[Dict[str, Any]])
async def list_asset_scans(
    limit: int = Query(50, description="Maximum number of asset scans to return"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    List asset scan jobs for the current user.
    
    This returns asset-level scans instead of confusing individual domain scans.
    Each result represents one logical scan operation on an asset.
    """
    return await asset_service.list_asset_scans(current_user.id, limit)

@router.get("/scan-jobs/{asset_scan_id}", response_model=Dict[str, Any])
async def get_asset_scan_status(
    asset_scan_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get detailed status and progress for a specific asset scan.
    
    Returns progress information, subdomain counts, and individual domain scan details.
    """
    return await asset_service.get_asset_scan_status(asset_scan_id, current_user.id)

# ================================================================
# NEW: Comprehensive Filter Options Endpoint (Phase 1b) - Must come BEFORE {asset_id}
# ================================================================

@router.get("/filter-options", response_model=Dict[str, Any])
async def get_comprehensive_filter_options(
    asset_id: Optional[str] = Query(None, description="Filter domains by specific asset/program"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get comprehensive filter options for user reconnaissance data.
    
    When asset_id is provided, domains are filtered to only those
    belonging to that specific program. This enables cascading filters
    where selecting a program updates the available domains.
    
    Returns:
    - domains: Apex domains (filtered by asset_id if provided)
    - assets: All assets user owns with reconnaissance data
    """
    try:
        # Get comprehensive filter options, optionally filtered by asset
        result = await asset_service.get_comprehensive_filter_options(
            user_id=current_user.id,
            asset_id=asset_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_comprehensive_filter_options: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving filter options"
        )

@router.get("/{asset_id}", response_model=AssetWithStats)
async def get_asset(
    asset_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get a specific asset with statistics."""
    return await asset_service.get_asset_with_stats(asset_id, current_user.id)

@router.patch("/{asset_id}", response_model=Asset)
async def update_asset(
    asset_id: str,
    asset_update: AssetUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an asset."""
    return await asset_service.update_asset(asset_id, asset_update, current_user.id)

@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete an asset and all associated data."""
    return await asset_service.delete_asset(asset_id, current_user.id)

# ================================================================
# Apex Domain Management
# ================================================================

@router.get("/{asset_id}/domains", response_model=List[ApexDomainWithStats])
async def get_apex_domains(
    asset_id: str,
    include_stats: bool = Query(True, description="Include domain statistics"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get apex domains for an asset."""
    return await asset_service.get_apex_domains(asset_id, current_user.id, include_stats)

@router.post("/{asset_id}/domains", response_model=ApexDomain, status_code=status.HTTP_201_CREATED)
async def create_apex_domain(
    asset_id: str,
    domain_data: ApexDomainCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new apex domain for an asset."""
    # Set asset_id from URL path
    domain_data.asset_id = asset_id
    return await asset_service.create_apex_domain(domain_data, current_user.id)

@router.patch("/{asset_id}/domains/{domain_id}", response_model=ApexDomain)
async def update_apex_domain(
    asset_id: str,
    domain_id: str,
    domain_update: ApexDomainUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update an apex domain."""
    return await asset_service.update_apex_domain(asset_id, domain_id, domain_update, current_user.id)

@router.delete("/{asset_id}/domains/{domain_id}")
async def delete_apex_domain(
    asset_id: str,
    domain_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete an apex domain."""
    return await asset_service.delete_apex_domain(asset_id, domain_id, current_user.id)

# ================================================================
# Asset Scan Operations (NEW - Asset-Level Scan Tracking)
# ================================================================

# ================================================================
# Background Task Wrapper (Bug #8 Fix)
# ================================================================

async def _run_pipeline_background(
    scan_job_id: str,
    asset_id: str,
    modules: List[str],
    scan_request: EnhancedAssetScanRequest,
    user_id: str
):
    """
    Background task wrapper for pipeline execution.
    
    This function runs the scan pipeline in the background, updating
    the scan job status on completion or failure. It provides comprehensive
    error handling to ensure scan jobs are always updated, even if the
    pipeline fails unexpectedly.
    
    Args:
        scan_job_id: UUID of the scan job to track
        asset_id: UUID of the asset being scanned
        modules: List of module names to execute
        scan_request: Original scan request parameters
        user_id: User ID for authorization
    """
    from app.services.scan_pipeline import scan_pipeline
    
    logger.info(
        f"🚀 Background pipeline started: scan_job={scan_job_id}, "
        f"asset={asset_id}, modules={modules}"
    )
    
    try:
        # Update status to running
        await asset_service.update_scan_job_progress(
            scan_job_id=scan_job_id,
            status="running",
            current_module=modules[0] if modules else None,
            progress_percent=0
        )
        
        # ============================================================
        # STREAMING PIPELINE DETECTION (Phase 4, Task 4.5)
        # ============================================================
        # Execute streaming pipeline (streaming-only architecture)
        # All modules use Redis Streams for parallel real-time processing
        
        logger.info(
            f"🌊 STREAMING pipeline for scan_job={scan_job_id}. "
            f"Modules: {modules}. Parallel execution enabled."
        )
        
        # Execute streaming pipeline
        pipeline_result = await scan_pipeline.execute_pipeline(
            asset_id=asset_id,
            modules=modules,
            scan_request=scan_request,
            user_id=user_id,
            scan_job_id=scan_job_id
        )
        
        logger.info(
            f"✅ Streaming pipeline completed: scan_job={scan_job_id}, "
            f"success={pipeline_result.get('successful_modules', 0)}/"
            f"{pipeline_result.get('total_modules', 0)} modules, "
            f"duration={pipeline_result.get('duration_seconds', 0):.1f}s"
        )
        
        # Mark scan job as completed
        await asset_service.complete_scan_job(
            scan_job_id=scan_job_id,
            result=pipeline_result
        )
        
    except Exception as e:
        # Log the error with full context
        logger.error(
            f"❌ Background pipeline failed: scan_job={scan_job_id}, "
            f"asset={asset_id}, error={str(e)}"
        )
        logger.exception(e)  # Log full traceback
        
        # Mark scan job as failed
        try:
            await asset_service.fail_scan_job(
                scan_job_id=scan_job_id,
                error=str(e)
            )
        except Exception as update_error:
            # If we can't even update the status, log it but don't raise
            logger.critical(
                f"💥 Failed to update scan job status after pipeline failure: "
                f"scan_job={scan_job_id}, update_error={str(update_error)}"
            )

# Asset Scan Job Management routes moved above to prevent route conflicts

# ================================================================
# 🔍 Bug #8 Fix: Polling Endpoint for Background Scan Progress
# ================================================================

@router.get("/scans/{scan_job_id}/status", response_model=Dict[str, Any])
async def get_scan_job_status_endpoint(
    scan_job_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get real-time status and progress of a background scan job.
    
    **Bug #8 Fix - Task 8.2.1**: Polling endpoint for async scans.
    
    Clients should poll this endpoint every 2-5 seconds to get:
    - Current scan status (pending, running, completed, failed)
    - Progress information (percent complete, current module)
    - Module execution details (which modules completed, which is running)
    - Partial results (subdomains discovered, DNS records created, etc.)
    - Estimated completion time
    
    Args:
        scan_job_id: UUID of the scan job (from scan initiation response)
        current_user: Authenticated user (injected by dependency)
    
    Returns:
        Detailed scan status with progress information
    
    Example Response:
        {
            "scan_job_id": "uuid",
            "status": "running",
            "progress": {
                "total_modules": 2,
                "completed_modules": 1,
                "current_module": "dnsx",
                "percent_complete": 50
            },
            "modules": [
                {"name": "subfinder", "status": "completed", "started_at": "...", "completed_at": "..."},
                {"name": "dnsx", "status": "running", "started_at": "...", "completed_at": null}
            ],
            "created_at": "2025-11-05T16:08:17Z",
            "started_at": "2025-11-05T16:08:18Z",
            "estimated_completion": "2025-11-05T16:18:18Z",
            "results": {
                "subdomains_discovered": 748,
                "dns_records_created": 2892
            }
        }
    """
    logger.info(f"User {current_user.id} polling scan job status: {scan_job_id}")
    
    try:
        # Task 8.2.2: Get scan job from database (already implemented in asset_service)
        scan_job = await asset_service.get_scan_job_status(
            scan_job_id=scan_job_id,
            user_id=current_user.id
        )
        
        if not scan_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan job {scan_job_id} not found or you don't have permission to access it"
            )
        
        # Task 8.2.3: Calculate progress
        # Note: get_scan_job_status already returns flattened data
        modules = scan_job.get("modules", [])
        completed_modules = scan_job.get("completed_modules", [])
        current_module = scan_job.get("current_module")
        
        # Progress percentage
        if modules:
            progress_percent = scan_job.get("progress_percent", 0)
            if progress_percent is None or progress_percent == 0:
                # Fallback calculation
                progress_percent = int((len(completed_modules) / len(modules)) * 100)
        else:
            progress_percent = 0
        
        # Task 8.2.4: Calculate estimated completion time
        estimated_completion = None
        if scan_job.get("status") == "running" and scan_job.get("started_at"):
            from datetime import datetime, timedelta
            import dateutil.parser
            
            started_at = dateutil.parser.isoparse(scan_job["started_at"])
            elapsed_seconds = (datetime.now(started_at.tzinfo) - started_at).total_seconds()
            
            if progress_percent > 0:
                # Estimate based on current progress
                estimated_total_seconds = (elapsed_seconds / progress_percent) * 100
                remaining_seconds = estimated_total_seconds - elapsed_seconds
                estimated_completion = (datetime.now(started_at.tzinfo) + timedelta(seconds=remaining_seconds)).isoformat()
        
        # Build module status list with timing info
        module_statuses = []
        # Get pipeline_result from scan_job if available for module timings
        pipeline_result = scan_job.get("pipeline_result", {}) or {}
        for module_name in modules:
            if module_name in completed_modules:
                module_status = "completed"
            elif module_name == current_module:
                module_status = "running"
            else:
                module_status = "pending"
            
            module_statuses.append({
                "name": module_name,
                "status": module_status,
                "started_at": pipeline_result.get(f"{module_name}_started_at"),
                "completed_at": pipeline_result.get(f"{module_name}_completed_at")
            })
        
        # Task 8.2.5: Return partial results from pipeline_result or database
        results = pipeline_result.get("results", {})
        
        # If no results in metadata, try to fetch from database
        if not results:
            asset_id = scan_job.get("asset_id")
            if asset_id:
                try:
                    # Count subdomains discovered
                    subdomains_response = asset_service.supabase.table("subdomains").select(
                        "id", count="exact"
                    ).eq("asset_id", asset_id).execute()
                    
                    # Count DNS records
                    dns_response = asset_service.supabase.table("dns_records").select(
                        "id", count="exact"
                    ).eq("asset_id", asset_id).execute()
                    
                    results = {
                        "subdomains_discovered": subdomains_response.count or 0,
                        "dns_records_created": dns_response.count or 0
                    }
                except Exception as e:
                    logger.warning(f"Failed to fetch partial results for scan {scan_job_id}: {e}")
                    results = {}
        
        # Task 8.2.6: Build response (schema already matches EnhancedAssetScanResponse for compatibility)
        response = {
            "scan_job_id": scan_job.get("scan_job_id"),
            "asset_id": scan_job.get("asset_id"),
            "asset_name": scan_job.get("asset_name"),
            "status": scan_job.get("status", "unknown"),
            "progress": {
                "total_modules": len(modules),
                "completed_modules": len(completed_modules),
                "current_module": current_module,
                "percent_complete": progress_percent
            },
            "modules": module_statuses,
            "created_at": scan_job.get("created_at"),
            "started_at": scan_job.get("started_at"),
            "completed_at": scan_job.get("completed_at"),
            "estimated_completion": estimated_completion,
            "results": results,
            "error_message": scan_job.get("error_message")
        }
        
        logger.info(
            f"Returning scan status for job {scan_job_id}: "
            f"status={response['status']}, progress={progress_percent}%"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan job status for {scan_job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scan job status: {str(e)}"
        )


@router.get("/{asset_id}/scan-history", response_model=List[Dict[str, Any]])
async def get_asset_scan_history(
    asset_id: str,
    limit: int = Query(50, description="Maximum number of scans to return"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get scan history for a specific asset.
    
    Returns asset-level scan records filtered by asset ID.
    """
    # Get all asset scans for the user and filter by asset_id
    all_scans = await asset_service.list_asset_scans(current_user.id, limit * 2)  # Get more to ensure we have enough after filtering
    asset_scans = [scan for scan in all_scans if scan.get("asset_id") == asset_id][:limit]
    return asset_scans

# ================================================================
# Legacy Support and Bulk Operations  
# ================================================================

@router.post("/with-domains", response_model=Dict[str, Any])
async def create_asset_with_domains(
    asset_data: AssetWithDomains,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create an asset with multiple apex domains in one operation."""
    try:
        # Create the asset first
        asset_create = AssetCreate(
            name=asset_data.name,
            description=asset_data.description,
            bug_bounty_url=asset_data.bug_bounty_url,
            priority=asset_data.priority
        )
        
        asset = await asset_service.create_asset(asset_create, current_user.id)
        
        # Create apex domains
        domains = []
        for domain_name in asset_data.domains:
            domain_create = ApexDomainCreate(
                asset_id=asset.id,
                domain=domain_name
            )
            domain = await asset_service.create_apex_domain(domain_create, current_user.id)
            domains.append(domain)
        
        return {
            "asset": asset,
            "domains": domains
        }
        
    except Exception as e:
        logger.error(f"Error creating asset with domains: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create asset with domains: {str(e)}"
        )

@router.post("/bulk", response_model=Dict[str, Any])
async def bulk_asset_operation(
    operation: BulkAssetOperation,
    current_user: UserResponse = Depends(get_current_user)
):
    """Perform bulk operations on multiple assets."""
    try:
        results = []
        
        if operation.operation == "scan":
            # Start scans for multiple assets
            for asset_id in operation.asset_ids:
                try:
                    scan_request = EnhancedAssetScanRequest()  # Use enhanced defaults
                    result = await asset_service.start_asset_scan(str(asset_id), scan_request, current_user.id)
                    results.append({
                        "asset_id": str(asset_id),
                        "status": "success",
                        "scan_id": str(result.asset_scan_id)
                    })
                except Exception as e:
                    results.append({
                        "asset_id": str(asset_id),
                        "status": "failed",
                        "error": str(e)
                    })
        
        elif operation.operation == "delete":
            # Delete multiple assets
            for asset_id in operation.asset_ids:
                try:
                    await asset_service.delete_asset(str(asset_id), current_user.id)
                    results.append({
                        "asset_id": str(asset_id),
                        "status": "success"
                    })
                except Exception as e:
                    results.append({
                        "asset_id": str(asset_id),
                        "status": "failed",
                        "error": str(e)
                    })
        
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]
        
        return {
            "operation": operation.operation,
            "total_assets": len(operation.asset_ids),
            "successful": len(successful),
            "failed": len(failed),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk operation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}"
        )

# ================================================================
# Debug/Diagnostic Endpoints
# ================================================================

@router.get("/debug/subdomains-count", response_model=Dict[str, Any])
async def debug_subdomains_count(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Debug endpoint to understand subdomain data relationships.
    This helps diagnose why the main subdomains endpoint might not be working.
    """
    try:
        # Get user's assets
        assets = await asset_service.get_assets(current_user.id, include_stats=False)
        
        debug_info = {
            "user_id": current_user.id,
            "total_assets": len(assets),
            "asset_ids": [asset.id for asset in assets],
        }
        
        if assets:
            # Get asset scan jobs for these assets
            asset_ids = [asset.id for asset in assets]
            
            # Use the service's supabase client directly for debugging
            asset_scan_jobs_response = asset_service.supabase.table("asset_scan_jobs").select(
                "id, asset_id, status, modules, total_domains"
            ).in_("asset_id", asset_ids).execute()
            
            debug_info["total_asset_scan_jobs"] = len(asset_scan_jobs_response.data) if asset_scan_jobs_response.data else 0
            debug_info["asset_scan_jobs_sample"] = asset_scan_jobs_response.data[:3] if asset_scan_jobs_response.data else []
            
            if asset_scan_jobs_response.data:
                asset_scan_job_ids = [job["id"] for job in asset_scan_jobs_response.data]
                
                # Count subdomains for these asset scan jobs
                subdomains_response = asset_service.supabase.table("subdomains").select(
                    "id, subdomain, scan_job_id, parent_domain"
                ).in_("scan_job_id", asset_scan_job_ids).limit(10).execute()
                
                debug_info["total_subdomains_found"] = len(subdomains_response.data) if subdomains_response.data else 0
                debug_info["subdomains_sample"] = subdomains_response.data[:3] if subdomains_response.data else []
        
        return debug_info
        
    except Exception as e:
        return {
            "error": str(e),
            "user_id": current_user.id
        }

@router.get("/{asset_id}/subdomains", response_model=List[Dict[str, Any]])
async def get_asset_subdomains(
    asset_id: str,
    module: str = Query(None, description="Filter by reconnaissance module"),
    limit: int = Query(1000, description="Maximum number of subdomains to return"),
    offset: int = Query(0, description="Pagination offset"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get all subdomains discovered for an asset.
    
    This endpoint retrieves subdomains through the proper data model:
    assets → asset_scan_jobs → subdomains
    
    Returns subdomains with metadata including discovery source, SSL info, 
    and parent scan job details.
    """
    return await asset_service.get_asset_subdomains(
        asset_id=asset_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        module_filter=module
    )

@router.get("/{asset_id}/analytics", response_model=Dict[str, Any])
async def get_asset_analytics(
    asset_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get analytics and insights for an asset."""
    # TODO: Implement asset analytics
    # This would provide reconnaissance effectiveness metrics, trends, etc.
    return {
        "asset_id": asset_id,
        "total_subdomains": 0,
        "module_effectiveness": {},
        "cloud_provider_distribution": {},
        "scan_success_rate": 0.0
    }

@router.post("/{asset_id}/domains/upload")
async def bulk_upload_domains(
    asset_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user)
):
    """Bulk upload apex domains from a file."""
    try:
        # Verify asset ownership
        asset = await asset_service.get_asset(asset_id, current_user.id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        # Read and process the uploaded file
        content = await file.read()
        text_content = content.decode('utf-8')
        
        # Parse domains from file (support various formats)
        domains_to_add = []
        failed_lines = []
        total_lines_processed = 0
        
        for line_num, line in enumerate(text_content.splitlines(), 1):
            total_lines_processed += 1
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Handle different formats: domain, domain:port, http://domain, etc.
            domain = line.lower()
            
            # Remove common prefixes
            for prefix in ['http://', 'https://', 'ftp://']:
                if domain.startswith(prefix):
                    domain = domain[len(prefix):]
                    break
            
            # Remove port numbers
            if ':' in domain:
                domain = domain.split(':')[0]
                
            # Remove paths
            if '/' in domain:
                domain = domain.split('/')[0]
            
            # Enhanced domain validation
            if not domain or len(domain) > 253:
                failed_lines.append(f"Line {line_num}: Invalid domain format")
                continue
                
            # Must have at least one dot and valid TLD
            if '.' not in domain:
                failed_lines.append(f"Line {line_num}: Invalid domain format")
                continue
                
            # Split into parts for validation
            parts = domain.split('.')
            if len(parts) < 2:
                failed_lines.append(f"Line {line_num}: Invalid domain format")
                continue
                
            # Check each part is valid
            valid_domain = True
            for part in parts:
                if not part or len(part) > 63 or not part.replace('-', '').replace('_', '').isalnum():
                    valid_domain = False
                    break
                    
            if not valid_domain:
                failed_lines.append(f"Line {line_num}: Invalid domain format")
                continue
                
            domains_to_add.append(domain)
        
        # Remove duplicates while preserving order
        unique_domains = list(dict.fromkeys(domains_to_add))
        duplicates_removed = len(domains_to_add) - len(unique_domains)
        
        # Add domains to the asset
        added_count = 0
        duplicates_in_db = 0
        failed_to_add = 0
        
        for domain in unique_domains:
            try:
                domain_data = ApexDomainCreate(domain=domain, asset_id=asset_id)
                await asset_service.create_apex_domain(domain_data, current_user.id)
                added_count += 1
            except HTTPException as e:
                if "already exists" in str(e.detail).lower():
                    duplicates_in_db += 1
                else:
                    failed_to_add += 1
                    failed_lines.append(f"Domain {domain}: {e.detail}")
            except Exception as e:
                failed_to_add += 1
                failed_lines.append(f"Domain {domain}: {str(e)}")
        
        # Return response in the format expected by frontend
        return {
            "summary": {
                "added": added_count,
                "duplicates": duplicates_in_db + duplicates_removed,
                "failed": failed_to_add + len([l for l in failed_lines if "Invalid domain" in l]),
                "total_lines_processed": total_lines_processed
            },
            "details": {
                "file_name": file.filename,
                "failed_lines": failed_lines if failed_lines else []
            }
        }
        
    except Exception as e:
        logger.error(f"Error in bulk upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}"
        )

# ================================================================
# NEW: Asset Domain Pagination Endpoint
# ================================================================

@router.get("/{asset_id}/domains/paginated", response_model=Dict[str, Any])
async def get_paginated_asset_domains(
    asset_id: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search domain names"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get paginated apex domains for a specific asset.
    
    This endpoint provides efficient pagination for domain management
    on asset detail pages, supporting filtering and search.
    
    Performance optimizations:
    - Server-side pagination (default 20 items)
    - Indexed domain name searches
    - Lightweight domain statistics
    - Smart query optimization
    """
    try:
        result = await asset_service.get_paginated_asset_domains(
            user_id=current_user.id,
            asset_id=asset_id,
            page=page,
            per_page=per_page,
            is_active=is_active,
            search=search
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_paginated_asset_domains: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving domains"
        )


# ================================================================
# DNS Records Endpoints
# ================================================================

@router.get("/{asset_id}/dns-records", response_model=DNSRecordListResponse)
async def get_asset_dns_records(
    asset_id: str,
    record_type: Optional[str] = Query(None, description="Filter by DNS record type (A, AAAA, CNAME, MX, TXT)"),
    subdomain_name: Optional[str] = Query(None, description="Filter by subdomain name (e.g., api.epicgames.com)"),
    resolved_after: Optional[str] = Query(None, description="Filter by resolution date (ISO format, >= comparison)"),
    resolved_before: Optional[str] = Query(None, description="Filter by resolution date (ISO format, <= comparison)"),
    scan_job_id: Optional[str] = Query(None, description="Filter by scan job UUID"),
    batch_scan_id: Optional[str] = Query(None, description="Filter by batch scan UUID"),
    limit: Optional[int] = Query(50, ge=1, le=1000, description="Records per page (default: 50, max: 1000)"),
    offset: Optional[int] = Query(0, ge=0, le=5000, description="Pagination offset (default: 0, max: 5000)"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get DNS records for a specific asset with filtering and pagination.
    
    This endpoint retrieves DNS resolution data discovered by the DNSX module.
    All filters use AND logic for precise querying.
    
    **Key Features:**
    - Protected pagination for large datasets (10k+ records)
    - Multiple filter options (record type, subdomain, date ranges, scan metadata)
    - Performance-optimized queries using indexed columns
    - Warning messages for large result sets
    
    **Authorization:** User must own the asset
    
    **Performance Tips:**
    - Use `record_type` filter to narrow results (e.g., only A records)
    - Use date filters for recent scans: `resolved_after=2025-11-01T00:00:00Z`
    - Combine filters to reduce result set size
    - Avoid deep pagination (offset > 5000) - use filters instead
    
    **Example Queries:**
    - Get all A records: `?record_type=A&limit=100`
    - Get recent DNS records: `?resolved_after=2025-11-01T00:00:00Z`
    - Get specific subdomain: `?subdomain_name=api.epicgames.com`
    - Combine filters: `?record_type=A&resolved_after=2025-11-01T00:00:00Z&limit=50`
    
    **Returns:**
    - `dns_records`: List of DNS record objects
    - `total_count`: Total matching records (for pagination UI)
    - `limit`: Applied records per page
    - `offset`: Applied pagination offset
    - `warning`: Optional warning for large result sets or performance tips
    """
    try:
        # Parse UUID parameters
        try:
            from uuid import UUID
            asset_uuid = UUID(asset_id)
            scan_job_uuid = UUID(scan_job_id) if scan_job_id else None
            batch_scan_uuid = UUID(batch_scan_id) if batch_scan_id else None
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid UUID format for asset_id, scan_job_id, or batch_scan_id"
            )
        
        # Verify user owns the asset
        asset = await asset_service.get_asset(asset_id, current_user.id)
        if not asset:
            raise HTTPException(
                status_code=404,
                detail=f"Asset {asset_id} not found"
            )
        
        logger.info(f"User {current_user.id} querying DNS records for asset {asset_id}")
        
        # If subdomain_name filter is provided, use the subdomain-specific query
        if subdomain_name:
            result = await dns_service.get_dns_records_by_subdomain(
                asset_id=asset_uuid,
                subdomain_name=subdomain_name,
                record_type=record_type,
                resolved_after=resolved_after,
                resolved_before=resolved_before,
                scan_job_id=scan_job_uuid,
                batch_scan_id=batch_scan_uuid,
                limit=limit,
                offset=offset
            )
        else:
            # Standard asset-level query
            result = await dns_service.get_dns_records_by_asset(
                asset_id=asset_uuid,
                record_type=record_type,
                resolved_after=resolved_after,
                resolved_before=resolved_before,
                scan_job_id=scan_job_uuid,
                batch_scan_id=batch_scan_uuid,
                limit=limit,
                offset=offset
            )
        
        logger.info(f"Returning {len(result['dns_records'])} DNS records (total: {result['total_count']})")
        
        return DNSRecordListResponse(**result)
        
    except ValueError as e:
        # Service layer validation error (invalid filters, excessive offset, etc.)
        logger.warning(f"Validation error in get_asset_dns_records: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, etc.)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_asset_dns_records for asset {asset_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving DNS records"
        )


@router.get("/dns-records/{record_id}", response_model=DNSRecord, tags=["dns"])
async def get_dns_record_by_id(
    record_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a single DNS record by its ID.
    
    This endpoint retrieves detailed information about a specific DNS record.
    The user must own the asset associated with this DNS record.
    
    **Authorization:** User must own the asset associated with the DNS record
    
    **Use Cases:**
    - View full details of a specific DNS resolution
    - Deep-linking to individual DNS records from dashboard
    - Audit trail for DNS changes over time
    
    **Returns:** Complete DNS record with all fields including:
    - Subdomain and parent domain
    - Record type and value (IP, hostname, or text)
    - TTL and priority (for MX records)
    - Resolution timestamp
    - Cloud provider detection
    - Scan metadata (job ID, batch ID, asset ID)
    """
    try:
        # Parse UUID
        try:
            from uuid import UUID
            record_uuid = UUID(record_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid UUID format for record_id"
            )
        
        logger.info(f"User {current_user.id} requesting DNS record {record_id}")
        
        # Get the DNS record
        record = await dns_service.get_dns_record_by_id(record_uuid)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"DNS record {record_id} not found"
            )
        
        # Verify user owns the associated asset
        if record.asset_id:
            asset = await asset_service.get_asset(record.asset_id, current_user.id)
            if not asset:
                # Asset exists but user doesn't own it
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to access this DNS record"
                )
        
        logger.info(f"Returning DNS record {record_id} for user {current_user.id}")
        return record
        
    except HTTPException:
        # Re-raise HTTP exceptions (400, 403, 404)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_dns_record_by_id for record {record_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving DNS record"
        )


