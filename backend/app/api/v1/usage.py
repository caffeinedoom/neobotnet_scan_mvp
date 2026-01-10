"""
LEAN Usage API - Optimized Reconnaissance Data

This module provides the /api/v1/usage/recon-data endpoint that the frontend
expects. Uses optimized batch queries for performance.

LEAN ARCHITECTURE: All authenticated users see ALL data (no user filtering).

PERFORMANCE FIX (2025-01-02):
- Uses batch queries and database views for efficiency
- Avoids N+1 query patterns
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import logging
import time

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
    
    LEAN Architecture: All authenticated users see ALL data.
    OPTIMIZED: Uses batch queries instead of N+1 pattern.
    
    Returns:
        summary: Overview statistics
        assets: List of assets with stats
        recent_scans: Recent scan jobs
    """
    start_time = time.time()
    
    try:
        client = supabase_client.service_client
        user_id = current_user.id
        
        logger.info(f"🚀 Fetching recon-data (LEAN architecture) for user {user_id}")
        
        # ================================================================
        # BATCH QUERY 1: Use asset_overview view (has pre-computed subdomain counts)
        # This view already JOINs assets -> asset_scan_jobs -> subdomains
        # and computes domain_count, subdomain_count, active_domain_count
        # ================================================================
        assets_result = client.table("asset_overview").select(
            "id, name, description, bug_bounty_url, is_active, priority, tags, created_at, updated_at, domain_count, subdomain_count, active_domain_count"
        ).order("created_at", desc=True).execute()
        
        assets = assets_result.data or []
        asset_ids = [a["id"] for a in assets]
        
        if not asset_ids:
            logger.info("No assets found in database")
            return {
                "summary": {
                    "total_assets": 0,
                    "active_assets": 0,
                    "total_domains": 0,
                    "active_domains": 0,
                    "total_scans": 0,
                    "completed_scans": 0,
                    "failed_scans": 0,
                    "pending_scans": 0,
                    "total_subdomains": 0,
                    "total_probes": 0,
                    "total_dns_records": 0,
                    "total_urls": 0,
                    "last_scan_date": None
                },
                "assets": [],
                "recent_scans": []
            }
        
        # Pre-compute subdomain counts from view data
        asset_subdomain_counts = {a["id"]: a.get("subdomain_count", 0) for a in assets}
        domain_counts = {a["id"]: a.get("domain_count", 0) for a in assets}
        active_domain_counts = {a["id"]: a.get("active_domain_count", 0) for a in assets}
        
        total_domains = sum(domain_counts.values())
        active_domains = sum(active_domain_counts.values())
        total_subdomains = sum(asset_subdomain_counts.values())
        
        # ================================================================
        # BATCH QUERY 2: Get scan jobs with status (LIMIT for performance)
        # We only need recent scans for the dashboard - limit to 500 max
        # ================================================================
        scans_result = client.table("asset_scan_jobs").select(
            "id, asset_id, status, modules, total_domains, completed_domains, created_at, started_at, completed_at, error_message"
        ).in_("asset_id", asset_ids).order("created_at", desc=True).limit(500).execute()
        
        scans_data = scans_result.data or []
        scan_job_ids = [s["id"] for s in scans_data]
        
        # Pre-compute scan stats per asset
        scan_stats = {}
        for s in scans_data:
            aid = s["asset_id"]
            if aid not in scan_stats:
                scan_stats[aid] = {"total": 0, "completed": 0, "failed": 0, "pending": 0, "last_scan": None}
            scan_stats[aid]["total"] += 1
            status = s.get("status", "")
            if status == "completed":
                scan_stats[aid]["completed"] += 1
            elif status == "failed":
                scan_stats[aid]["failed"] += 1
            elif status in ["pending", "running"]:
                scan_stats[aid]["pending"] += 1
            # Track last scan date
            if scan_stats[aid]["last_scan"] is None or s["created_at"] > scan_stats[aid]["last_scan"]:
                scan_stats[aid]["last_scan"] = s["created_at"]
        
        # Global scan stats
        total_scans = len(scans_data)
        completed_scans = len([s for s in scans_data if s.get("status") == "completed"])
        failed_scans = len([s for s in scans_data if s.get("status") == "failed"])
        pending_scans = len([s for s in scans_data if s.get("status") in ["pending", "running"]])
        last_scan_date = scans_data[0]["created_at"] if scans_data else None
        
        # ================================================================
        # OPTIMIZED: Use asset_recon_counts VIEW for all counts in ONE query
        # Previously: 75 sequential queries taking ~10 seconds
        # Now: 1 query taking <1 second
        # ================================================================
        recon_counts_result = client.table("asset_recon_counts").select("*").execute()
        recon_counts_data = recon_counts_result.data or []
        
        # Build lookup dictionaries from single query result
        asset_probe_counts = {}
        asset_dns_counts = {}
        asset_url_counts = {}
        
        for row in recon_counts_data:
            aid = row["asset_id"]
            asset_probe_counts[aid] = row.get("probe_count", 0)
            asset_dns_counts[aid] = row.get("dns_count", 0)
            asset_url_counts[aid] = row.get("url_count", 0)
        
        total_probes = sum(asset_probe_counts.values())
        total_dns_records = sum(asset_dns_counts.values())
        total_urls = sum(asset_url_counts.values())
        
        # ================================================================
        # Build enriched assets (using pre-computed data from asset_overview view)
        # ================================================================
        enriched_assets = []
        for asset in assets:
            aid = asset["id"]
            stats = scan_stats.get(aid, {"total": 0, "completed": 0, "failed": 0, "pending": 0, "last_scan": None})
            
            enriched_assets.append({
                "id": aid,
                "name": asset["name"],
                "description": asset.get("description"),
                "bug_bounty_url": asset.get("bug_bounty_url"),
                "is_active": asset.get("is_active", True),
                "priority": asset.get("priority", 0),
                "tags": asset.get("tags", []),
                "created_at": asset["created_at"],
                "updated_at": asset["updated_at"],
                "apex_domain_count": domain_counts.get(aid, 0),
                "active_domain_count": active_domain_counts.get(aid, 0),
                "total_scans": stats["total"],
                "completed_scans": stats["completed"],
                "failed_scans": stats["failed"],
                "pending_scans": stats["pending"],
                "total_subdomains": asset_subdomain_counts.get(aid, 0),  # From asset_overview view
                "total_probes": asset_probe_counts.get(aid, 0),  # HTTP probes = live servers
                "total_dns_records": asset_dns_counts.get(aid, 0),
                "total_urls": asset_url_counts.get(aid, 0),  # Discovered URLs from crawlers
                "last_scan_date": stats["last_scan"]
            })
        
        # ================================================================
        # OPTIMIZED: Use scan_subdomain_counts VIEW for all counts in ONE query
        # Previously: 20 sequential queries taking ~2-3 seconds
        # Now: 1 query taking <0.1 seconds
        # ================================================================
        recent_scan_ids = [s["id"] for s in scans_data[:20]]
        scan_subdomain_counts = {}
        
        if recent_scan_ids:
            counts_result = client.table("scan_subdomain_counts").select(
                "scan_job_id, subdomain_count"
            ).in_("scan_job_id", recent_scan_ids).execute()
            
            for row in (counts_result.data or []):
                scan_subdomain_counts[row["scan_job_id"]] = row.get("subdomain_count", 0)
        
        # ================================================================
        # Build recent scans (limit to 20)
        # ================================================================
        recent_scans = []
        asset_name_map = {a["id"]: a["name"] for a in assets}
        
        for scan in scans_data[:20]:
            status_val = scan.get("status", "pending")
            progress = 0
            if status_val == "completed":
                progress = 100
            elif status_val == "running":
                td = scan.get("total_domains", 0)
                cd = scan.get("completed_domains", 0)
                progress = int((cd / td) * 100) if td > 0 else 50
            
            # Note: modules field removed for production - tool names not exposed via API
            recent_scans.append({
                "id": scan["id"],
                "asset_id": scan["asset_id"],
                "asset_name": asset_name_map.get(scan["asset_id"], "Unknown"),
                "status": status_val,
                "total_domains": scan.get("total_domains", 0),
                "completed_domains": scan.get("completed_domains", 0),
                "active_domains_only": True,
                "created_at": scan["created_at"],
                "started_at": scan.get("started_at"),
                "completed_at": scan.get("completed_at"),
                "estimated_completion": None,
                "error_message": scan.get("error_message"),
                "progress_percentage": progress,
                "subdomains_found": scan_subdomain_counts.get(scan["id"], 0),
                "scan_type": "reconnaissance"
            })
        
        # ================================================================
        # Build summary
        # ================================================================
        summary = {
            "total_assets": len(enriched_assets),
            "active_assets": len([a for a in enriched_assets if a.get("is_active", True)]),
            "total_domains": total_domains,
            "active_domains": active_domains,
            "total_scans": total_scans,
            "completed_scans": completed_scans,
            "failed_scans": failed_scans,
            "pending_scans": pending_scans,
            "total_subdomains": total_subdomains,
            "total_probes": total_probes,  # HTTP probes = live servers
            "total_dns_records": total_dns_records,
            "total_urls": total_urls,  # Discovered URLs from crawlers
            "last_scan_date": last_scan_date
        }
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            f"✅ Recon-data returned in {elapsed_ms:.0f}ms: "
            f"{len(enriched_assets)} assets, {total_subdomains} subdomains, {total_scans} scans"
        )
        
        return {
            "summary": summary,
            "assets": enriched_assets,
            "recent_scans": recent_scans
        }
        
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"❌ Error getting recon-data after {elapsed_ms:.0f}ms: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get reconnaissance data"
        )

