"""
HTTP Probes API Endpoints.

Provides REST API endpoints for querying HTTP probe data from the httpx module.
Supports filtering, pagination, and aggregate statistics.

Author: Pluckware Development Team
Date: November 17, 2025
Phase: HTTPx Frontend Implementation - Phase 1
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from ...schemas.http_probes import HTTPProbeResponse, HTTPProbeStatsResponse
from ...schemas.auth import UserResponse
from ...core.dependencies import get_current_user
from ...core.supabase_client import supabase_client


router = APIRouter()


@router.get("")
async def get_http_probes(
    asset_id: Optional[str] = Query(None, description="Filter by asset ID"),
    scan_job_id: Optional[str] = Query(None, description="Filter by scan job ID"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    subdomain: Optional[str] = Query(None, description="Filter by subdomain (partial match)"),
    technology: Optional[str] = Query(None, description="Filter by technology (e.g., 'IIS:10.0')"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of probes to return"),
    offset: int = Query(0, ge=0, description="Number of probes to skip (pagination)"),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get HTTP probes with optional filtering and pagination.
    
    Returns HTTP probe results from the httpx scan module. Supports filtering by:
    - Asset ID: Get probes for a specific asset
    - Scan Job ID: Get probes from a specific scan
    - Status Code: Filter by HTTP response code (200, 404, 500, etc.)
    - Subdomain: Search by subdomain name (partial match)
    - Technology: Filter by detected technology (e.g., "IIS:10.0", "Apache")
    
    Pagination: Use `limit` and `offset` parameters (default: 100 items per page).
    
    Returns probes array with total count for proper pagination.
    
    LEAN Architecture: All authenticated users see ALL data.
    """
    try:
        # Use service_client to bypass RLS - LEAN architecture allows all authenticated users
        supabase = supabase_client.service_client
        
        # Start building the query with count for efficient pagination
        query = supabase.table("http_probes").select(
            "id, scan_job_id, asset_id, status_code, url, title, webserver, "
            "content_length, final_url, ip, technologies, cdn_name, content_type, "
            "asn, chain_status_codes, location, favicon_md5, subdomain, parent_domain, "
            "scheme, port, created_at",
            count="exact"
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
            import json
            query = query.filter("technologies", "cs", json.dumps([technology]))
        
        # Order by created_at descending (most recent first)
        query = query.order("created_at", desc=True)
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        # Execute query (count included via count="exact")
        response = query.execute()
        
        probes_data = response.data or []
        total_count = response.count if response.count is not None else len(probes_data)
        
        # Return with pagination info
        return {
            "probes": probes_data,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch HTTP probes: {str(e)}"
        )


# NOTE: Static routes like /stats/summary MUST be defined BEFORE dynamic routes like /{probe_id}
# FastAPI matches routes in order of definition
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
        # Use service_client to bypass RLS - LEAN architecture allows all authenticated users
        supabase = supabase_client.service_client
        
        # Get accurate total count first (using count="exact")
        count_query = supabase.table("http_probes").select("id", count="exact")
        if asset_id:
            count_query = count_query.eq("asset_id", asset_id)
        if scan_job_id:
            count_query = count_query.eq("scan_job_id", scan_job_id)
        count_result = count_query.limit(1).execute()
        total_probes = count_result.count or 0
        
        # Fetch probes in batches for statistics calculation
        # Note: For large datasets, this should be replaced with database-level aggregation
        probes = []
        batch_size = 1000
        offset = 0
        
        while offset < total_probes:
            query = supabase.table("http_probes").select(
                "status_code, webserver, technologies, cdn_name, chain_status_codes"
            )
            if asset_id:
                query = query.eq("asset_id", asset_id)
            if scan_job_id:
                query = query.eq("scan_job_id", scan_job_id)
            
            batch_response = query.range(offset, offset + batch_size - 1).execute()
            batch_data = batch_response.data or []
            probes.extend(batch_data)
            
            if len(batch_data) < batch_size:
                break
            offset += batch_size
        
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


# Dynamic route MUST be after static routes
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
        404: If probe not found
    """
    try:
        # Use service_client to bypass RLS - LEAN architecture allows all authenticated users
        supabase = supabase_client.service_client
        
        # Get the probe
        response = supabase.table("http_probes").select("*").eq("id", probe_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="HTTP probe not found"
            )
        
        probe = response.data[0]
        
        # LEAN Architecture: All authenticated users see ALL data
        return probe
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch HTTP probe: {str(e)}"
        )
