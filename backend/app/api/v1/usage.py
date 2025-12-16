"""
LEAN Usage API - Backwards Compatibility Layer

This module provides the /api/v1/usage/recon-data endpoint that the frontend
expects, using data from the programs/assets tables.

This is a compatibility shim to support the existing frontend while we
transition to the new /api/v1/programs endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import logging

from ...core.dependencies import get_current_user
from ...schemas.auth import UserResponse
from ...core.supabase_client import supabase_client

router = APIRouter(prefix="/usage", tags=["usage"])
logger = logging.getLogger(__name__)


@router.get("/recon-data", response_model=Dict[str, Any])
async def get_recon_data(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get unified reconnaissance data for the dashboard.
    
    This endpoint provides backwards compatibility with the existing frontend.
    It aggregates data from assets, scans, subdomains, etc.
    
    Returns:
        summary: Overview statistics
        assets: List of assets with stats
        recent_scans: Recent scan jobs
    """
    try:
        client = supabase_client.service_client
        
        # Get all assets (programs)
        assets_result = client.table("assets").select(
            "id, name, description, bug_bounty_url, is_active, priority, tags, created_at, updated_at"
        ).order("created_at", desc=True).execute()
        
        assets = assets_result.data or []
        
        # Enrich assets with statistics
        enriched_assets = []
        total_subdomains = 0
        total_scans = 0
        completed_scans = 0
        failed_scans = 0
        pending_scans = 0
        last_scan_date = None
        total_domains = 0
        
        for asset in assets:
            asset_id = asset["id"]
            
            # Count apex domains
            domains_result = client.table("apex_domains").select(
                "id", count="exact"
            ).eq("asset_id", asset_id).execute()
            domain_count = domains_result.count or 0
            total_domains += domain_count
            
            # Get scan jobs for this asset
            scan_jobs_result = client.table("asset_scan_jobs").select(
                "id, status, modules, created_at, completed_at"
            ).eq("asset_id", asset_id).execute()
            
            asset_scans = scan_jobs_result.data or []
            scan_job_ids = [job["id"] for job in asset_scans]
            
            # Count scans by status
            asset_total_scans = len(asset_scans)
            asset_completed_scans = len([s for s in asset_scans if s["status"] == "completed"])
            asset_failed_scans = len([s for s in asset_scans if s["status"] == "failed"])
            asset_pending_scans = len([s for s in asset_scans if s["status"] in ["pending", "running"]])
            
            total_scans += asset_total_scans
            completed_scans += asset_completed_scans
            failed_scans += asset_failed_scans
            pending_scans += asset_pending_scans
            
            # Count subdomains for this asset
            subdomain_count = 0
            if scan_job_ids:
                subdomains_result = client.table("subdomains").select(
                    "id", count="exact"
                ).in_("scan_job_id", scan_job_ids).execute()
                subdomain_count = subdomains_result.count or 0
            total_subdomains += subdomain_count
            
            # Get last scan date for this asset
            asset_last_scan = None
            if asset_scans:
                sorted_scans = sorted(asset_scans, key=lambda x: x["created_at"], reverse=True)
                asset_last_scan = sorted_scans[0]["created_at"]
                
                # Update global last scan date
                if last_scan_date is None or asset_last_scan > last_scan_date:
                    last_scan_date = asset_last_scan
            
            enriched_assets.append({
                "id": asset["id"],
                "name": asset["name"],
                "description": asset.get("description"),
                "bug_bounty_url": asset.get("bug_bounty_url"),
                "is_active": asset.get("is_active", True),
                "priority": asset.get("priority", 0),
                "tags": asset.get("tags", []),
                "created_at": asset["created_at"],
                "updated_at": asset["updated_at"],
                "apex_domain_count": domain_count,
                "active_domain_count": domain_count,  # Simplified
                "total_scans": asset_total_scans,
                "completed_scans": asset_completed_scans,
                "failed_scans": asset_failed_scans,
                "pending_scans": asset_pending_scans,
                "total_subdomains": subdomain_count,
                "last_scan_date": asset_last_scan
            })
        
        # Get recent scans (all assets)
        recent_scans_result = client.table("asset_scan_jobs").select(
            "id, asset_id, status, modules, total_domains, created_at, started_at, completed_at, error_message"
        ).order("created_at", desc=True).limit(20).execute()
        
        recent_scans = []
        for scan in (recent_scans_result.data or []):
            # Get asset name
            asset_name = "Unknown"
            for asset in enriched_assets:
                if asset["id"] == scan["asset_id"]:
                    asset_name = asset["name"]
                    break
            
            # Calculate progress
            progress = 0
            if scan["status"] == "completed":
                progress = 100
            elif scan["status"] == "running":
                progress = 50  # Simplified
            elif scan["status"] == "failed":
                progress = 0
            
            # Count subdomains for this scan
            scan_subdomains = 0
            subdomains_result = client.table("subdomains").select(
                "id", count="exact"
            ).eq("scan_job_id", scan["id"]).execute()
            scan_subdomains = subdomains_result.count or 0
            
            recent_scans.append({
                "id": scan["id"],
                "asset_id": scan["asset_id"],
                "asset_name": asset_name,
                "status": scan["status"],
                "modules": scan.get("modules", []),
                "total_domains": scan.get("total_domains", 0),
                "completed_domains": scan.get("total_domains", 0) if scan["status"] == "completed" else 0,
                "active_domains_only": True,
                "created_at": scan["created_at"],
                "started_at": scan.get("started_at"),
                "completed_at": scan.get("completed_at"),
                "estimated_completion": None,
                "error_message": scan.get("error_message"),
                "progress_percentage": progress,
                "subdomains_found": scan_subdomains,
                "scan_type": "reconnaissance"
            })
        
        # Build summary
        summary = {
            "total_assets": len(enriched_assets),
            "active_assets": len([a for a in enriched_assets if a.get("is_active", True)]),
            "total_domains": total_domains,
            "active_domains": total_domains,  # Simplified
            "total_scans": total_scans,
            "completed_scans": completed_scans,
            "failed_scans": failed_scans,
            "pending_scans": pending_scans,
            "total_subdomains": total_subdomains,
            "last_scan_date": last_scan_date
        }
        
        logger.info(f"Returning recon-data for user {current_user.id}: {len(enriched_assets)} assets, {total_subdomains} subdomains")
        
        return {
            "summary": summary,
            "assets": enriched_assets,
            "recent_scans": recent_scans
        }
        
    except Exception as e:
        logger.error(f"Error getting recon-data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get reconnaissance data"
        )

