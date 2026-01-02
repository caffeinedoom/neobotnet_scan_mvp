"""
URLs API Endpoints.

Provides REST API endpoints for querying URL data discovered by
Katana, Waymore, GAU, and other URL discovery tools.
Supports filtering, pagination, and aggregate statistics.

Author: Pluckware Development Team
Date: December 2025
"""

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from ...schemas.urls import URLResponse, URLStatsResponse, PaginatedURLResponse
from ...schemas.auth import UserResponse
from ...core.dependencies import get_current_user
from ...core.supabase_client import supabase_client
from ...dependencies.tier_check import (
    get_user_tier,
    get_user_urls_viewed,
    increment_urls_viewed,
    get_remaining_url_quota,
)
from ...core.tier_limits import get_tier_limits


router = APIRouter()


@router.get("")
async def get_urls(
    response: Response,
    asset_id: Optional[str] = Query(None, description="Filter by asset/program ID"),
    scan_job_id: Optional[str] = Query(None, description="Filter by scan job ID"),
    is_alive: Optional[bool] = Query(None, description="Filter by alive status"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    has_params: Optional[bool] = Query(None, description="Filter by whether URL has query parameters"),
    file_extension: Optional[str] = Query(None, description="Filter by file extension"),
    domain: Optional[str] = Query(None, description="Filter by domain (partial match)"),
    search: Optional[str] = Query(None, description="Search in URL, domain, or title"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of URLs to return"),
    offset: int = Query(0, ge=0, description="Number of URLs to skip (pagination)"),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get URLs with optional filtering and pagination.
    
    Returns URL records discovered by scanning tools. Supports filtering by:
    - Asset ID: Get URLs for a specific program
    - Scan Job ID: Get URLs from a specific scan
    - Alive Status: Filter by whether URL is alive (true/false)
    - Status Code: Filter by HTTP response code (200, 404, 500, etc.)
    - Source: Filter by discovery tool (katana, waymore, gau)
    - Has Params: Filter by whether URL has query parameters
    - File Extension: Filter by file extension (js, php, etc.)
    - Domain: Search by domain name (partial match)
    - Search: Search across URL, domain, and title
    
    Pagination: Use `limit` and `offset` parameters (default: 100 items per page).
    
    **Free tier limit:** 250 total URLs. Upgrade to see all URLs.
    
    LEAN Architecture: All authenticated users see ALL data.
    """
    try:
        # Get user ID
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("id") or current_user.get("sub")
        
        # Get user tier and URL quota
        urls_viewed, urls_limit = await get_remaining_url_quota(user_id)
        plan_type = await get_user_tier(user_id)
        
        # Calculate remaining quota
        is_limited = urls_limit is not None
        urls_remaining = None
        if is_limited:
            urls_remaining = max(0, urls_limit - urls_viewed)
        
        # Add quota headers
        if is_limited:
            response.headers["X-URLs-Limit"] = str(urls_limit)
            response.headers["X-URLs-Viewed"] = str(urls_viewed)
            response.headers["X-URLs-Remaining"] = str(urls_remaining)
        response.headers["X-Plan-Type"] = plan_type
        
        # Check if user has exhausted their free quota
        if is_limited and urls_remaining <= 0:
            return {
                "urls": [],
                "quota": {
                    "plan_type": plan_type,
                    "urls_limit": urls_limit,
                    "urls_viewed": urls_viewed,
                    "urls_remaining": 0,
                    "is_limited": True,
                    "upgrade_required": True,
                },
                "message": "You've reached your free tier limit of 250 URLs. Upgrade for unlimited access."
            }
        
        # Use service_client to bypass RLS - LEAN architecture allows all authenticated users
        supabase = supabase_client.service_client
        
        # Start building the query with count (sources excluded from API response)
        # Using count="exact" in select to get count in same query - more efficient
        query = supabase.table("urls").select(
            "id, asset_id, scan_job_id, url, url_hash, domain, path, query_params, "
            "first_discovered_at, "
            "resolved_at, is_alive, status_code, content_type, content_length, response_time_ms, "
            "title, final_url, redirect_chain, webserver, technologies, "
            "has_params, file_extension, created_at, updated_at",
            count="exact"
        )
        
        # Apply filters
        if asset_id:
            query = query.eq("asset_id", asset_id)
        
        if scan_job_id:
            query = query.eq("scan_job_id", scan_job_id)
        
        if is_alive is not None:
            query = query.eq("is_alive", is_alive)
        
        if status_code:
            query = query.eq("status_code", status_code)
        
        if has_params is not None:
            query = query.eq("has_params", has_params)
        
        if file_extension:
            query = query.eq("file_extension", file_extension)
        
        if domain:
            # Use ilike for case-insensitive partial match
            query = query.ilike("domain", f"%{domain}%")
        
        if search:
            # Search across multiple fields
            query = query.or_(
                f"url.ilike.%{search}%,domain.ilike.%{search}%,title.ilike.%{search}%"
            )
        
        # Order by first_discovered_at descending (most recent first)
        query = query.order("first_discovered_at", desc=True)
        
        # For free tier: limit results based on remaining quota
        effective_limit = limit
        effective_offset = offset
        
        if is_limited:
            # Don't let user paginate beyond their limit
            if offset >= urls_remaining:
                return {
                    "urls": [],
                    "quota": {
                        "plan_type": plan_type,
                        "urls_limit": urls_limit,
                        "urls_viewed": urls_viewed,
                        "urls_remaining": urls_remaining,
                        "is_limited": True,
                        "upgrade_required": True,
                    },
                    "message": "You've reached your free tier limit of 250 URLs. Upgrade for unlimited access."
                }
            
            # Cap the results to remaining quota
            max_can_return = urls_remaining - offset
            effective_limit = min(limit, max_can_return)
        
        # Apply pagination
        query = query.range(effective_offset, effective_offset + effective_limit - 1)
        
        # Execute query (count is included via count="exact" in select)
        result = query.execute()
        
        urls_data = result.data or []
        urls_count = len(urls_data)
        
        # Total count from the same query (more efficient than separate query)
        total_count = result.count if result.count is not None else len(urls_data)
        
        # For free tier: track URLs viewed
        if is_limited and urls_count > 0:
            await increment_urls_viewed(user_id, urls_count)
            urls_viewed += urls_count
            urls_remaining = max(0, urls_limit - urls_viewed)
        
        # Return with quota info and total count
        return {
            "urls": urls_data,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "quota": {
                "plan_type": plan_type,
                "urls_limit": urls_limit,
                "urls_viewed": urls_viewed,
                "urls_remaining": urls_remaining,
                "is_limited": is_limited,
                "upgrade_required": is_limited and urls_remaining <= 0,
            },
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch URLs: {str(e)}"
        )


# NOTE: Static routes like /stats MUST be defined BEFORE dynamic routes like /{url_id}
@router.get("/stats", response_model=URLStatsResponse)
async def get_url_stats(
    asset_id: Optional[str] = Query(None, description="Filter stats by asset ID"),
    scan_job_id: Optional[str] = Query(None, description="Filter stats by scan job ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get aggregate statistics for URLs.
    
    Returns summary metrics including:
    - Total URL count
    - Alive/dead/pending counts
    - URLs with parameters count
    - Unique domains count
    - Top discovery sources
    - Top status codes
    - Top technologies
    - Top file extensions
    
    Can be filtered by asset_id or scan_job_id to get statistics for specific scans.
    """
    try:
        # Use service_client to bypass RLS
        supabase = supabase_client.service_client
        
        # Build base query with filters
        def apply_filters(q):
            if asset_id:
                q = q.eq("asset_id", asset_id)
            if scan_job_id:
                q = q.eq("scan_job_id", scan_job_id)
            return q
        
        # Get total count
        total_query = apply_filters(
            supabase.table("urls").select("id", count="exact")
        )
        total_result = total_query.execute()
        total_urls = total_result.count or 0
        
        # Get alive count
        alive_query = apply_filters(
            supabase.table("urls").select("id", count="exact").eq("is_alive", True)
        )
        alive_result = alive_query.execute()
        alive_urls = alive_result.count or 0
        
        # Get dead count
        dead_query = apply_filters(
            supabase.table("urls").select("id", count="exact").eq("is_alive", False)
        )
        dead_result = dead_query.execute()
        dead_urls = dead_result.count or 0
        
        # Get pending count (not yet resolved)
        pending_query = apply_filters(
            supabase.table("urls").select("id", count="exact").is_("resolved_at", "null")
        )
        pending_result = pending_query.execute()
        pending_urls = pending_result.count or 0
        
        # Get URLs with params count
        params_query = apply_filters(
            supabase.table("urls").select("id", count="exact").eq("has_params", True)
        )
        params_result = params_query.execute()
        urls_with_params = params_result.count or 0
        
        # Get unique domains - fetch domains and count unique
        domains_query = apply_filters(
            supabase.table("urls").select("domain")
        )
        domains_result = domains_query.execute()
        unique_domains = len(set(d.get("domain") for d in (domains_result.data or []) if d.get("domain")))
        
        # For aggregations (top sources, status codes, etc.), we need to fetch some data
        # In production, this would be done via database aggregation
        sample_query = apply_filters(
            supabase.table("urls").select("sources, status_code, technologies, file_extension").limit(5000)
        )
        sample_result = sample_query.execute()
        sample_data = sample_result.data or []
        
        # Calculate top sources
        source_counts = {}
        for row in sample_data:
            sources = row.get("sources", [])
            if isinstance(sources, list):
                for source in sources:
                    source_counts[source] = source_counts.get(source, 0) + 1
        top_sources = [
            {"source": s, "count": c}
            for s, c in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        # Calculate top status codes
        status_counts = {}
        for row in sample_data:
            code = row.get("status_code")
            if code:
                status_counts[code] = status_counts.get(code, 0) + 1
        top_status_codes = [
            {"status_code": s, "count": c}
            for s, c in sorted(status_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        # Calculate top technologies
        tech_counts = {}
        for row in sample_data:
            techs = row.get("technologies", [])
            if isinstance(techs, list):
                for tech in techs:
                    tech_counts[tech] = tech_counts.get(tech, 0) + 1
        top_technologies = [
            {"name": t, "count": c}
            for t, c in sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Calculate top file extensions
        ext_counts = {}
        for row in sample_data:
            ext = row.get("file_extension")
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
        top_file_extensions = [
            {"extension": e, "count": c}
            for e, c in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return URLStatsResponse(
            total_urls=total_urls,
            alive_urls=alive_urls,
            dead_urls=dead_urls,
            pending_urls=pending_urls,
            urls_with_params=urls_with_params,
            unique_domains=unique_domains,
            top_sources=top_sources,
            top_status_codes=top_status_codes,
            top_technologies=top_technologies,
            top_file_extensions=top_file_extensions
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate URL statistics: {str(e)}"
        )


# Dynamic route MUST be after static routes
@router.get("/{url_id}", response_model=URLResponse)
async def get_url_by_id(
    url_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a specific URL by ID.
    
    Returns detailed information for a single URL record.
    
    Args:
        url_id: UUID of the URL record
        
    Returns:
        URLResponse: Full URL details
        
    Raises:
        404: If URL not found
    """
    try:
        # Use service_client to bypass RLS
        supabase = supabase_client.service_client
        
        # Get the URL
        response = supabase.table("urls").select("*").eq("id", url_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="URL not found"
            )
        
        url = response.data[0]
        
        # LEAN Architecture: All authenticated users see ALL data
        return url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch URL: {str(e)}"
        )

