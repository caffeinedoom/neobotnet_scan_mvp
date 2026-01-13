"""
LEAN Programs API - Public Read Access for Bug Bounty Programs

This API provides read-only access to reconnaissance data for all authenticated users.
In the LEAN model:
- All authenticated users can read ALL program data
- No user-specific filtering (data is public within the platform)
- API keys or JWT tokens are required for authentication

NOTE: Internal tool names (subfinder, dnsx, httpx, etc.) are NOT exposed to users.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

from ...core.dependencies import get_current_user
from ...schemas.auth import UserResponse
from ...core.supabase_client import supabase_client

router = APIRouter(prefix="/programs", tags=["programs"])
logger = logging.getLogger(__name__)


# ================================================================
# Programs (Bug Bounty Assets) - Public Read Access
# ================================================================

@router.get("", response_model=Dict[str, Any])
async def list_programs(
    include_stats: bool = Query(True, description="Include statistics"),
    search: Optional[str] = Query(None, description="Search by program name"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(25, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    List all bug bounty programs with reconnaissance statistics.
    
    All authenticated users have access to all programs.
    This is the LEAN public data model.
    
    Returns:
        Paginated response with:
        - programs: Array of program objects
        - pagination: Pagination metadata (total, page, per_page, etc.)
    """
    try:
        # Use service client for public data access
        client = supabase_client.service_client
        
        # Build query with count for pagination
        query = client.table("assets").select(
            "id, name, description, is_active, priority, tags, created_at, updated_at",
            count="exact"
        )
        
        # Apply search filter
        if search:
            query = query.ilike("name", f"%{search}%")
        
        # Apply pagination (convert page/per_page to offset)
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)
        query = query.order("created_at", desc=True)
        
        result = query.execute()
        programs = result.data or []
        total = result.count or 0
        
        # Enrich with statistics if requested
        if include_stats and programs:
            programs = await _enrich_programs_with_stats(client, programs)
        
        # Calculate pagination metadata
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        logger.info(f"Returning {len(programs)} programs (page {page}/{total_pages}) for user {current_user.id}")
        
        return {
            "programs": programs,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing programs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list programs"
        )


# ================================================================
# Global Endpoints - MUST be defined BEFORE /{program_id} routes
# to prevent route matching conflicts
# ================================================================

@router.get("/all/subdomains", response_model=Dict[str, Any])
async def get_all_subdomains(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=1000, description="Items per page"),
    search: Optional[str] = Query(None, description="Search subdomain names"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get all subdomains across all programs with pagination.
    
    Returns:
        Paginated list of all subdomains
    """
    try:
        client = supabase_client.service_client
        
        # Build subdomains query - NOTE: source_module NOT exposed to users
        query = client.table("subdomains").select(
            "id, subdomain, parent_domain, discovered_at, scan_job_id",
            count="exact"
        )
        
        # Apply search filter
        if search:
            query = query.ilike("subdomain", f"%{search}%")
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)
        query = query.order("discovered_at", desc=True)
        
        result = query.execute()
        total = result.count or 0
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        logger.info(f"Returning {len(result.data or [])} subdomains (all programs)")
        
        return {
            "subdomains": result.data or [],
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting all subdomains: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subdomains"
        )


# ================================================================
# Single Program Endpoint
# ================================================================

@router.get("/{program_id}", response_model=Dict[str, Any])
async def get_program(
    program_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get detailed information about a specific program.
    
    Returns:
        Program details with full statistics
    """
    # Validate UUID format
    try:
        UUID(program_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid program ID format. Must be a valid UUID."
        )
    
    try:
        client = supabase_client.service_client
        
        result = client.table("assets").select(
            "id, name, description, is_active, priority, tags, created_at, updated_at"
        ).eq("id", program_id).maybe_single().execute()
        
        # maybe_single() returns None when no record found
        if result is None or not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Program not found"
            )
        
        program = result.data
        
        # Get detailed stats
        enriched = await _enrich_programs_with_stats(client, [program])
        
        logger.info(f"Returning program {program_id} for user {current_user.id}")
        return enriched[0] if enriched else program
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting program {program_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get program"
        )


# ================================================================
# Subdomains - Public Read Access
# ================================================================

@router.get("/{program_id}/subdomains", response_model=Dict[str, Any])
async def get_program_subdomains(
    program_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=1000, description="Items per page"),
    search: Optional[str] = Query(None, description="Search subdomain names"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get subdomains for a specific program with pagination.
    
    Returns:
        Paginated list of subdomains with metadata
        
    Note: source_module filter removed - internal tool names not exposed.
    """
    try:
        client = supabase_client.service_client
        
        # Verify program exists
        program_check = client.table("assets").select("id").eq("id", program_id).execute()
        if not program_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Program {program_id} not found"
            )
        
        # Get asset_scan_job IDs for this program
        scan_jobs = client.table("asset_scan_jobs").select("id").eq("asset_id", program_id).execute()
        scan_job_ids = [job["id"] for job in (scan_jobs.data or [])]
        
        if not scan_job_ids:
            return {
                "subdomains": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }
        
        # Build subdomains query - NOTE: source_module NOT exposed to users
        query = client.table("subdomains").select(
            "id, subdomain, parent_domain, discovered_at, scan_job_id",
            count="exact"
        ).in_("scan_job_id", scan_job_ids)
        
        # Apply search filter only
        if search:
            query = query.ilike("subdomain", f"%{search}%")
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)
        query = query.order("discovered_at", desc=True)
        
        result = query.execute()
        total = result.count or 0
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        logger.info(f"Returning {len(result.data or [])} subdomains for program {program_id}")
        
        return {
            "subdomains": result.data or [],
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subdomains for program {program_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subdomains"
        )


# ================================================================
# DNS Records - Public Read Access
# ================================================================

@router.get("/{program_id}/dns", response_model=Dict[str, Any])
async def get_program_dns_records(
    program_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=1000, description="Items per page"),
    record_type: Optional[str] = Query(None, description="Filter by record type (A, AAAA, CNAME, MX, TXT)"),
    subdomain: Optional[str] = Query(None, description="Filter by subdomain"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get DNS records for a specific program with pagination.
    
    Returns:
        Paginated list of DNS records
    """
    try:
        client = supabase_client.service_client
        
        # Verify program exists
        program_check = client.table("assets").select("id").eq("id", program_id).execute()
        if not program_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Program {program_id} not found"
            )
        
        # Build DNS records query - FIXED: use correct column names
        query = client.table("dns_records").select(
            "id, subdomain, parent_domain, record_type, record_value, ttl, resolved_at, cloud_provider, cdn_provider",
            count="exact"
        ).eq("asset_id", program_id)
        
        # Apply filters
        if record_type:
            query = query.eq("record_type", record_type.upper())
        if subdomain:
            query = query.ilike("subdomain", f"%{subdomain}%")
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)
        query = query.order("resolved_at", desc=True)
        
        result = query.execute()
        total = result.count or 0
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        logger.info(f"Returning {len(result.data or [])} DNS records for program {program_id}")
        
        return {
            "dns_records": result.data or [],
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting DNS records for program {program_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get DNS records"
        )


# ================================================================
# HTTP Probes - Public Read Access
# ================================================================

@router.get("/{program_id}/probes", response_model=Dict[str, Any])
async def get_program_http_probes(
    program_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=1000, description="Items per page"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    technology: Optional[str] = Query(None, description="Filter by detected technology"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get HTTP probe results for a specific program with pagination.
    
    Returns:
        Paginated list of HTTP probe results
    """
    try:
        client = supabase_client.service_client
        
        # Verify program exists
        program_check = client.table("assets").select("id").eq("id", program_id).execute()
        if not program_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Program {program_id} not found"
            )
        
        # Build HTTP probes query - FIXED: use correct column names (cdn_name, created_at)
        query = client.table("http_probes").select(
            "id, url, status_code, title, content_length, content_type, technologies, webserver, cdn_name, created_at",
            count="exact"
        ).eq("asset_id", program_id)
        
        # Apply filters
        if status_code:
            query = query.eq("status_code", status_code)
        if technology:
            # Technologies is stored as array, use contains
            query = query.contains("technologies", [technology])
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)
        query = query.order("created_at", desc=True)
        
        result = query.execute()
        total = result.count or 0
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        logger.info(f"Returning {len(result.data or [])} HTTP probes for program {program_id}")
        
        return {
            "probes": result.data or [],
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HTTP probes for program {program_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get HTTP probes"
        )


# ================================================================
# Helper Functions
# ================================================================

async def _enrich_programs_with_stats(client, programs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrich programs with statistics using BATCH queries (optimized).
    
    PERFORMANCE FIX: Instead of N+1 queries (4 per program = 148 for 37 programs),
    now uses just 2 batch queries regardless of program count.
    
    Uses the asset_overview materialized view for domain/subdomain counts.
    """
    if not programs:
        return []
    
    program_ids = [p["id"] for p in programs]
    
    # ================================================================
    # BATCH QUERY 1: Get all stats from asset_overview view (1 query)
    # This replaces 3 queries per program
    # ================================================================
    try:
        overview_result = client.table("asset_overview").select(
            "id, domain_count, subdomain_count"
        ).in_("id", program_ids).execute()
        
        # Build lookup dictionary
        stats_by_id = {}
        for row in (overview_result.data or []):
            stats_by_id[row["id"]] = {
                "domain_count": row.get("domain_count", 0),
                "subdomain_count": row.get("subdomain_count", 0)
            }
    except Exception as e:
        logger.warning(f"Could not fetch from asset_overview view: {e}. Falling back to zeros.")
        stats_by_id = {}
    
    # ================================================================
    # BATCH QUERY 2: Get last scan dates for all programs (1 query)
    # Uses DISTINCT ON to get most recent scan per asset
    # ================================================================
    try:
        # Get the most recent scan for each asset in one query
        scans_result = client.table("asset_scan_jobs").select(
            "asset_id, created_at"
        ).in_("asset_id", program_ids).order(
            "created_at", desc=True
        ).execute()
        
        # Build lookup - first occurrence is most recent due to ordering
        last_scan_by_id = {}
        for row in (scans_result.data or []):
            aid = row["asset_id"]
            if aid not in last_scan_by_id:  # First one is most recent
                last_scan_by_id[aid] = row["created_at"]
    except Exception as e:
        logger.warning(f"Could not fetch scan dates: {e}")
        last_scan_by_id = {}
    
    # ================================================================
    # Merge stats into programs
    # ================================================================
    enriched = []
    for program in programs:
        pid = program["id"]
        stats = stats_by_id.get(pid, {"domain_count": 0, "subdomain_count": 0})
        
        enriched.append({
            **program,
            "domain_count": stats["domain_count"],
            "subdomain_count": stats["subdomain_count"],
            "last_scan_date": last_scan_by_id.get(pid)
        })
    
    return enriched
