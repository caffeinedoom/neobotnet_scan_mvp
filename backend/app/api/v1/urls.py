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
    parent_domain: Optional[str] = Query(None, description="Filter by parent/apex domain (exact match)"),
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
    - Parent Domain: Filter by apex domain (exact match, e.g., "epicgames.com")
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
        
        # Check if any filters are applied
        # If no filters, we can use the url_stats MV for total count (fast!)
        # If filters, we need count="exact" but filtered queries are usually fast
        has_filters = any([
            asset_id, scan_job_id, parent_domain, is_alive is not None,
            status_code, has_params is not None, file_extension, domain, search
        ])
        
        # Build the select fields (sources excluded from API response)
        select_fields = (
            "id, asset_id, scan_job_id, url, url_hash, domain, path, query_params, "
            "first_discovered_at, "
            "resolved_at, is_alive, status_code, content_type, content_length, response_time_ms, "
            "title, final_url, redirect_chain, webserver, technologies, "
            "has_params, file_extension, created_at, updated_at"
        )
        
        # For unfiltered queries: skip count="exact" (causes 8+ second timeouts on 362K rows)
        # For filtered queries: use count="exact" (filtered queries are faster)
        if has_filters:
            query = supabase.table("urls").select(select_fields, count="exact")
        else:
            query = supabase.table("urls").select(select_fields)
        
        # Apply filters
        if asset_id:
            query = query.eq("asset_id", asset_id)
        
        if scan_job_id:
            query = query.eq("scan_job_id", scan_job_id)
        
        if parent_domain:
            # Match domains that end with the apex domain (e.g., parent_domain=atlassian.com 
            # matches: atlassian.com, api.atlassian.com, jira.atlassian.com, etc.)
            # Use ilike with pattern to match apex domain and all subdomains
            query = query.or_(
                f"domain.eq.{parent_domain},domain.ilike.%.{parent_domain}"
            )
        
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
        
        # Execute query
        result = query.execute()
        
        urls_data = result.data or []
        urls_count = len(urls_data)
        
        # Get total count:
        # - Filtered queries: use count from query (count="exact" was used)
        # - Unfiltered queries: use url_stats MV (pre-computed, instant)
        if has_filters:
            total_count = result.count if result.count is not None else len(urls_data)
        else:
            # Use the url_stats materialized view for fast total count
            try:
                stats_result = supabase.table("url_stats").select("total_urls").execute()
                if stats_result.data and len(stats_result.data) > 0:
                    total_count = stats_result.data[0].get("total_urls", len(urls_data))
                else:
                    total_count = len(urls_data)
            except Exception:
                # Fallback if MV doesn't exist
                total_count = len(urls_data)
        
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
    
    OPTIMIZED: Uses materialized views for unfiltered queries.
    Previously: 6+ sequential queries on 362K rows (~4 seconds)
    Now: 3-4 queries on pre-computed MVs (~100ms)
    
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
        
        # Check if filters are applied
        has_filters = asset_id is not None or scan_job_id is not None
        
        if not has_filters:
            # ================================================================
            # OPTIMIZED PATH: Use materialized views for global stats
            # Single query replaces 6+ queries on 362K rows
            # ================================================================
            
            # Get pre-computed stats from url_stats MV
            stats_result = supabase.table("url_stats").select("*").execute()
            stats = stats_result.data[0] if stats_result.data else {}
            
            total_urls = stats.get("total_urls", 0)
            alive_urls = stats.get("alive_urls", 0)
            dead_urls = stats.get("dead_urls", 0)
            pending_urls = stats.get("pending_urls", 0)
            urls_with_params = stats.get("urls_with_params", 0)
            unique_domains = stats.get("unique_domains", 0)
            
            # Get top sources from MV
            sources_result = supabase.table("url_top_sources").select("*").limit(5).execute()
            top_sources = [
                {"source": s.get("source"), "count": s.get("count", 0)}
                for s in (sources_result.data or [])
            ]
            
            # Get top status codes from MV
            status_result = supabase.table("url_top_status_codes").select("*").limit(5).execute()
            top_status_codes = [
                {"status_code": s.get("status_code"), "count": s.get("count", 0)}
                for s in (status_result.data or [])
            ]
            
            # Get top file extensions from MV
            ext_result = supabase.table("url_top_extensions").select("*").limit(10).execute()
            top_file_extensions = [
                {"extension": e.get("file_extension"), "count": e.get("count", 0)}
                for e in (ext_result.data or [])
            ]
            
            # For technologies, we still need to sample (JSONB arrays require expansion)
            # Fetch a representative sample of 500 URLs with technologies
            tech_sample = supabase.table("urls").select(
                "technologies"
            ).not_.is_("technologies", "null").limit(500).execute()
            
            tech_counts = {}
            for url_row in (tech_sample.data or []):
                technologies = url_row.get("technologies", [])
                if isinstance(technologies, list):
                    for tech in technologies:
                        tech_counts[tech] = tech_counts.get(tech, 0) + 1
            
            top_technologies = [
                {"name": tech, "count": count}
                for tech, count in sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
        else:
            # ================================================================
            # FILTERED PATH: Use count queries with filters
            # Still optimized with indexed columns
            # ================================================================
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
            total_result = total_query.limit(1).execute()
            total_urls = total_result.count or 0
            
            # Get alive count
            alive_query = apply_filters(
                supabase.table("urls").select("id", count="exact").eq("is_alive", True)
            )
            alive_result = alive_query.limit(1).execute()
            alive_urls = alive_result.count or 0
            
            # Get dead count
            dead_query = apply_filters(
                supabase.table("urls").select("id", count="exact").eq("is_alive", False)
            )
            dead_result = dead_query.limit(1).execute()
            dead_urls = dead_result.count or 0
            
            # Get pending count (not yet resolved)
            pending_query = apply_filters(
                supabase.table("urls").select("id", count="exact").is_("resolved_at", "null")
            )
            pending_result = pending_query.limit(1).execute()
            pending_urls = pending_result.count or 0
            
            # Get URLs with params count
            params_query = apply_filters(
                supabase.table("urls").select("id", count="exact").eq("has_params", True)
            )
            params_result = params_query.limit(1).execute()
            urls_with_params = params_result.count or 0
            
            # Get unique domains count (using sample for filtered queries)
            domains_query = apply_filters(
                supabase.table("urls").select("domain").limit(10000)
            )
            domains_result = domains_query.execute()
            unique_domains = len(set(d.get("domain") for d in (domains_result.data or []) if d.get("domain")))
            
            # For aggregations, fetch a sample with filters applied
            sample_query = apply_filters(
                supabase.table("urls").select("sources, status_code, technologies, file_extension").limit(1000)
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
@router.get("/{url_id}")
async def get_url_by_id(
    url_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a specific URL by ID.
    
    Returns detailed information for a single URL record.
    
    **Free tier limit:** Counts against the 250 URL limit.
    
    Args:
        url_id: UUID of the URL record
        
    Returns:
        URLResponse: Full URL details (or quota exhausted message)
        
    Raises:
        404: If URL not found
    """
    try:
        # Get user ID
        user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("id") or current_user.get("sub")
        
        # Check quota before allowing access
        urls_viewed, urls_limit = await get_remaining_url_quota(user_id)
        plan_type = await get_user_tier(user_id)
        
        is_limited = urls_limit is not None
        if is_limited:
            urls_remaining = max(0, urls_limit - urls_viewed)
            
            # Block if quota exhausted
            if urls_remaining <= 0:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "message": "You've reached your free tier limit of 250 URLs. Upgrade for unlimited access.",
                        "quota": {
                            "plan_type": plan_type,
                            "urls_limit": urls_limit,
                            "urls_viewed": urls_viewed,
                            "urls_remaining": 0,
                            "upgrade_required": True
                        }
                    }
                )
        
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
        
        # Track this URL view for free tier
        if is_limited:
            await increment_urls_viewed(user_id, 1)
        
        # LEAN Architecture: All authenticated users see ALL data
        return url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch URL: {str(e)}"
        )

