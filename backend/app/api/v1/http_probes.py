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
    parent_domain: Optional[str] = Query(None, description="Filter by parent/apex domain (exact match)"),
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
    - Parent Domain: Filter by apex domain (exact match, e.g., "epicgames.com")
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
        
        if parent_domain:
            query = query.eq("parent_domain", parent_domain)
        
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
    
    OPTIMIZED: Uses http_probe_stats VIEW for pre-computed aggregates.
    Previously: Fetched all 22K+ rows in batches (~4.4 seconds)
    Now: 3-4 optimized queries (~0.5 seconds)
    
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
        
        # Check if filters are applied
        has_filters = asset_id is not None or scan_job_id is not None
        
        if not has_filters:
            # ================================================================
            # OPTIMIZED PATH: Use http_probe_stats VIEW for global stats
            # Single query replaces fetching all 22K+ rows
            # ================================================================
            stats_result = supabase.table("http_probe_stats").select("*").execute()
            stats = stats_result.data[0] if stats_result.data else {}
            
            total_probes = stats.get("total_probes", 0)
            redirect_chains_count = stats.get("with_redirects", 0)
            
            # Build status distribution from pre-computed counts
            status_code_dist = {}
            if stats.get("status_2xx", 0) > 0:
                status_code_dist[200] = stats.get("status_2xx", 0)
            if stats.get("status_3xx", 0) > 0:
                status_code_dist[301] = stats.get("status_3xx", 0)
            if stats.get("status_4xx", 0) > 0:
                status_code_dist[404] = stats.get("status_4xx", 0)
            if stats.get("status_5xx", 0) > 0:
                status_code_dist[500] = stats.get("status_5xx", 0)
            
            # Get top webservers from VIEW
            servers_result = supabase.table("http_probe_webserver_counts").select("*").limit(10).execute()
            top_servers = [
                {"name": s.get("webserver", "Unknown"), "count": s.get("count", 0)}
                for s in (servers_result.data or [])
            ]
            
            # For technologies, we still need to sample (JSONB arrays require expansion)
            # Fetch a representative sample of 500 probes with technologies
            tech_sample = supabase.table("http_probes").select(
                "technologies"
            ).not_.is_("technologies", "null").limit(500).execute()
            
            tech_counts = {}
            for probe in (tech_sample.data or []):
                technologies = probe.get("technologies", [])
                if isinstance(technologies, list):
                    for tech in technologies:
                        tech_counts[tech] = tech_counts.get(tech, 0) + 1
            
            top_technologies = [
                {"name": tech, "count": count}
                for tech, count in sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # CDN counts from sample
            cdn_sample = supabase.table("http_probes").select(
                "cdn_name"
            ).not_.is_("cdn_name", "null").limit(500).execute()
            
            cdn_counts = {}
            for probe in (cdn_sample.data or []):
                cdn = probe.get("cdn_name")
                if cdn:
                    cdn_counts[cdn] = cdn_counts.get(cdn, 0) + 1
            
        else:
            # ================================================================
            # FILTERED PATH: Use count queries with filters
            # Still optimized but cannot use pre-computed views
            # ================================================================
            count_query = supabase.table("http_probes").select("id", count="exact")
            if asset_id:
                count_query = count_query.eq("asset_id", asset_id)
            if scan_job_id:
                count_query = count_query.eq("scan_job_id", scan_job_id)
            count_result = count_query.limit(1).execute()
            total_probes = count_result.count or 0
            
            # For filtered queries, fetch a sample for distributions
            sample_query = supabase.table("http_probes").select(
                "status_code, webserver, technologies, cdn_name, chain_status_codes"
            )
            if asset_id:
                sample_query = sample_query.eq("asset_id", asset_id)
            if scan_job_id:
                sample_query = sample_query.eq("scan_job_id", scan_job_id)
            
            # Fetch up to 1000 for distribution calculations
            sample_result = sample_query.limit(1000).execute()
            probes = sample_result.data or []
            
            # Calculate distributions from sample
            status_code_dist = {}
            for probe in probes:
                code = probe.get("status_code")
                if code:
                    status_code_dist[code] = status_code_dist.get(code, 0) + 1
            
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
            
            server_counts = {}
            for probe in probes:
                server = probe.get("webserver")
                if server:
                    server_counts[server] = server_counts.get(server, 0) + 1
            
            top_servers = [
                {"name": server, "count": count}
                for server, count in sorted(server_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            cdn_counts = {}
            for probe in probes:
                cdn = probe.get("cdn_name")
                if cdn:
                    cdn_counts[cdn] = cdn_counts.get(cdn, 0) + 1
            
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
