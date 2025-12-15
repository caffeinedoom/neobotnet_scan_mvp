"""
HTTP Probes API Endpoints.

Provides REST API endpoints for querying HTTP probe data from the httpx module.
Supports filtering, pagination, and aggregate statistics.

Author: Pluckware Development Team
Date: November 17, 2025
Phase: HTTPx Frontend Implementation - Phase 1
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from ...schemas.http_probes import HTTPProbeResponse, HTTPProbeStatsResponse
from ...schemas.auth import UserResponse
from ...core.dependencies import get_current_user
from ...core.supabase_client import supabase_client


router = APIRouter()


@router.get("", response_model=List[HTTPProbeResponse])
async def get_http_probes(
    asset_id: Optional[str] = Query(None, description="Filter by asset ID"),
    scan_job_id: Optional[str] = Query(None, description="Filter by scan job ID"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    subdomain: Optional[str] = Query(None, description="Filter by subdomain (partial match)"),
    technology: Optional[str] = Query(None, description="Filter by technology (e.g., 'IIS:10.0')"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of probes to return"),
    offset: int = Query(0, ge=0, description="Number of probes to skip (pagination)"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get HTTP probes with optional filtering and pagination.
    
    Returns HTTP probe results from the httpx scan module. Supports filtering by:
    - Asset ID: Get probes for a specific asset
    - Scan Job ID: Get probes from a specific scan
    - Status Code: Filter by HTTP response code (200, 404, 500, etc.)
    - Subdomain: Search by subdomain name (partial match)
    - Technology: Filter by detected technology (e.g., "IIS:10.0", "Apache")
    
    Pagination: Use `limit` and `offset` parameters (default: 100 items per page).
    
    Note: Users can only view HTTP probes from their own scans (RLS enforced).
    """
    try:
        supabase = supabase_client.client
        
        # Start building the query
        # Join with asset_scan_jobs to enforce RLS (users can only see their own probes)
        query = supabase.table("http_probes").select(
            "id, scan_job_id, asset_id, status_code, url, title, webserver, "
            "content_length, final_url, ip, technologies, cdn_name, content_type, "
            "asn, chain_status_codes, location, favicon_md5, subdomain, parent_domain, "
            "scheme, port, created_at"
        )
        
        # Apply filters
        if asset_id:
            query = query.eq("asset_id", asset_id)
        
        if scan_job_id:
            query = query.eq("scan_job_id", scan_job_id)
        
        if status_code:
            query = query.eq("status_code", status_code)
        
        if subdomain:
            # Use ilike for case-insensitive partial match
            query = query.ilike("subdomain", f"%{subdomain}%")
        
        if technology:
            # Filter by technology in JSONB array
            # Use Supabase's cs (contains) operator with proper JSON formatting
            # This searches for an exact match within the JSONB array
            import json
            query = query.filter("technologies", "cs", json.dumps([technology]))
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        # Order by created_at descending (most recent first)
        query = query.order("created_at", desc=True)
        
        # Execute query
        response = query.execute()
        
        if not response.data:
            return []
        
        # Filter results to only show user's probes (enforce RLS at application level)
        # Query asset_scan_jobs to get user's scan job IDs
        user_scan_jobs_response = supabase.table("asset_scan_jobs").select("id").eq(
            "user_id", current_user.id
        ).execute()
        
        user_scan_job_ids = {job["id"] for job in user_scan_jobs_response.data} if user_scan_jobs_response.data else set()
        
        # Filter probes to only include those from user's scans
        filtered_probes = [
            probe for probe in response.data 
            if probe["scan_job_id"] in user_scan_job_ids
        ]
        
        return filtered_probes
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch HTTP probes: {str(e)}"
        )


@router.get("/{probe_id}", response_model=HTTPProbeResponse)
async def get_http_probe_by_id(
    probe_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a specific HTTP probe by ID.
    
    Returns detailed information for a single HTTP probe record.
    
    Args:
        probe_id: UUID of the HTTP probe
        
    Returns:
        HTTPProbeResponse: Full probe details
        
    Raises:
        404: If probe not found or user doesn't have access
    """
    try:
        supabase = supabase_client.client
        
        # Get the probe
        response = supabase.table("http_probes").select("*").eq("id", probe_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HTTP probe not found"
            )
        
        probe = response.data[0]
        
        # Verify user owns this probe (check via scan_job_id)
        scan_job_response = supabase.table("asset_scan_jobs").select("user_id").eq(
            "id", probe["scan_job_id"]
        ).execute()
        
        if not scan_job_response.data or scan_job_response.data[0]["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HTTP probe not found"
            )
        
        return probe
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch HTTP probe: {str(e)}"
        )


@router.get("/stats/summary", response_model=HTTPProbeStatsResponse)
async def get_http_probe_stats(
    asset_id: Optional[str] = Query(None, description="Filter stats by asset ID"),
    scan_job_id: Optional[str] = Query(None, description="Filter stats by scan job ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get aggregate statistics for HTTP probes.
    
    Returns summary metrics including:
    - Total probe count
    - Status code distribution (200s, 404s, 500s, etc.)
    - Top technologies detected
    - Top web servers
    - CDN usage
    - Redirect chain statistics
    
    Can be filtered by asset_id or scan_job_id to get statistics for specific scans.
    """
    try:
        supabase = supabase_client.client
        
        # First, get user's scan job IDs for RLS enforcement
        user_scan_jobs_response = supabase.table("asset_scan_jobs").select("id").eq(
            "user_id", current_user.id
        ).execute()
        
        user_scan_job_ids = [job["id"] for job in user_scan_jobs_response.data] if user_scan_jobs_response.data else []
        
        if not user_scan_job_ids:
            # User has no scans, return empty stats
            return HTTPProbeStatsResponse(
                total_probes=0,
                status_code_distribution={},
                top_technologies=[],
                top_servers=[],
                cdn_usage={},
                redirect_chains_count=0
            )
        
        # Build query with filters
        query = supabase.table("http_probes").select("*").in_("scan_job_id", user_scan_job_ids)
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        
        if scan_job_id:
            # Verify this scan job belongs to user
            if scan_job_id in user_scan_job_ids:
                query = query.eq("scan_job_id", scan_job_id)
            else:
                # User doesn't own this scan job, return empty stats
                return HTTPProbeStatsResponse(
                    total_probes=0,
                    status_code_distribution={},
                    top_technologies=[],
                    top_servers=[],
                    cdn_usage={},
                    redirect_chains_count=0
                )
        
        # Fetch all probes for statistics calculation
        response = query.execute()
        
        probes = response.data if response.data else []
        
        # Calculate statistics
        total_probes = len(probes)
        
        # Status code distribution
        status_code_dist = {}
        for probe in probes:
            code = probe.get("status_code")
            if code:
                status_code_dist[code] = status_code_dist.get(code, 0) + 1
        
        # Technology frequency
        tech_counts = {}
        for probe in probes:
            technologies = probe.get("technologies", [])
            if isinstance(technologies, list):
                for tech in technologies:
                    tech_counts[tech] = tech_counts.get(tech, 0) + 1
        
        top_technologies = [
            {"name": tech, "count": count}
            for tech, count in sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Server frequency
        server_counts = {}
        for probe in probes:
            server = probe.get("webserver")
            if server:
                server_counts[server] = server_counts.get(server, 0) + 1
        
        top_servers = [
            {"name": server, "count": count}
            for server, count in sorted(server_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # CDN usage
        cdn_counts = {}
        for probe in probes:
            cdn = probe.get("cdn_name")
            if cdn:
                cdn_counts[cdn] = cdn_counts.get(cdn, 0) + 1
        
        # Redirect chains count (probes with non-empty chain_status_codes)
        redirect_chains_count = sum(
            1 for probe in probes 
            if probe.get("chain_status_codes") and len(probe.get("chain_status_codes", [])) > 0
        )
        
        return HTTPProbeStatsResponse(
            total_probes=total_probes,
            status_code_distribution=status_code_dist,
            top_technologies=top_technologies,
            top_servers=top_servers,
            cdn_usage=cdn_counts,
            redirect_chains_count=redirect_chains_count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate HTTP probe statistics: {str(e)}"
        )
