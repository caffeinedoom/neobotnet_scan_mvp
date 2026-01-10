"""
Data Export API Endpoints.

Provides streaming CSV/JSON exports for reconnaissance data.
URLs export requires PRO subscription, other exports are free.

Author: Pluckware Development Team
Date: January 2026
"""

import csv
import io
import json
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ...schemas.auth import UserResponse
from ...core.dependencies import get_current_user
from ...core.supabase_client import supabase_client
from ...dependencies.tier_check import get_user_tier

router = APIRouter()

# Batch size for streaming exports
EXPORT_BATCH_SIZE = 1000


async def check_pro_required(user_id: str) -> bool:
    """Check if user has PRO tier access."""
    plan_type = await get_user_tier(user_id)
    return plan_type in ['paid', 'pro', 'enterprise']


def format_csv_row(row: list) -> str:
    """Format a row as CSV, properly escaping values."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(row)
    return output.getvalue()


# =============================================================================
# URLs Export (PRO ONLY)
# =============================================================================

async def stream_urls_csv(
    asset_id: Optional[str] = None,
    is_alive: Optional[bool] = None,
    status_code: Optional[int] = None,
    has_params: Optional[bool] = None,
) -> AsyncGenerator[str, None]:
    """Stream URLs as CSV."""
    supabase = supabase_client.service_client
    
    # CSV Header
    yield format_csv_row([
        "url", "domain", "path", "status_code", "is_alive", 
        "content_type", "title", "has_params", "first_discovered_at"
    ])
    
    offset = 0
    while True:
        # Build query
        query = supabase.table("urls").select(
            "url, domain, path, status_code, is_alive, content_type, title, has_params, first_discovered_at"
        )
        
        # Apply filters
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if is_alive is not None:
            query = query.eq("is_alive", is_alive)
        if status_code:
            query = query.eq("status_code", status_code)
        if has_params is not None:
            query = query.eq("has_params", has_params)
        
        # Pagination
        query = query.order("first_discovered_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            yield format_csv_row([
                row.get("url", ""),
                row.get("domain", ""),
                row.get("path", ""),
                row.get("status_code", ""),
                row.get("is_alive", ""),
                row.get("content_type", ""),
                row.get("title", ""),
                row.get("has_params", ""),
                row.get("first_discovered_at", ""),
            ])
        
        offset += EXPORT_BATCH_SIZE
        
        # Safety check - if batch is smaller than limit, we're done
        if len(batch) < EXPORT_BATCH_SIZE:
            break


async def stream_urls_json(
    asset_id: Optional[str] = None,
    is_alive: Optional[bool] = None,
    status_code: Optional[int] = None,
    has_params: Optional[bool] = None,
) -> AsyncGenerator[str, None]:
    """Stream URLs as JSON array."""
    supabase = supabase_client.service_client
    
    yield "["
    first = True
    offset = 0
    
    while True:
        # Build query
        query = supabase.table("urls").select(
            "url, domain, path, status_code, is_alive, content_type, title, has_params, first_discovered_at"
        )
        
        # Apply filters
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if is_alive is not None:
            query = query.eq("is_alive", is_alive)
        if status_code:
            query = query.eq("status_code", status_code)
        if has_params is not None:
            query = query.eq("has_params", has_params)
        
        # Pagination
        query = query.order("first_discovered_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            if not first:
                yield ","
            yield json.dumps(row)
            first = False
        
        offset += EXPORT_BATCH_SIZE
        
        if len(batch) < EXPORT_BATCH_SIZE:
            break
    
    yield "]"


@router.get("/urls")
async def export_urls(
    format: str = Query("csv", regex="^(csv|json)$", description="Export format"),
    asset_id: Optional[str] = Query(None, description="Filter by asset/program ID"),
    is_alive: Optional[bool] = Query(None, description="Filter by alive status"),
    status_code: Optional[int] = Query(None, description="Filter by status code"),
    has_params: Optional[bool] = Query(None, description="Filter by has parameters"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Export URLs as CSV or JSON.
    
    **Requires PRO subscription.**
    
    Streams the full dataset matching your filters.
    """
    # Get user ID
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get("id") or current_user.get("sub")
    
    # Check PRO status
    is_pro = await check_pro_required(user_id)
    if not is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="URL export requires a Pro subscription. Upgrade to export all URLs."
        )
    
    if format == "csv":
        return StreamingResponse(
            stream_urls_csv(asset_id, is_alive, status_code, has_params),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=urls-export.csv"}
        )
    else:
        return StreamingResponse(
            stream_urls_json(asset_id, is_alive, status_code, has_params),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=urls-export.json"}
        )


# =============================================================================
# Subdomains Export (FREE)
# =============================================================================

async def stream_subdomains_csv(
    asset_id: Optional[str] = None,
    parent_domain: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream subdomains as CSV."""
    supabase = supabase_client.service_client
    
    # CSV Header (source_module excluded)
    yield format_csv_row([
        "subdomain", "parent_domain", "discovered_at"
    ])
    
    offset = 0
    while True:
        query = supabase.table("subdomains").select(
            "subdomain, parent_domain, discovered_at"
        )
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if parent_domain:
            query = query.eq("parent_domain", parent_domain)
        
        query = query.order("discovered_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            yield format_csv_row([
                row.get("subdomain", ""),
                row.get("parent_domain", ""),
                row.get("discovered_at", ""),
            ])
        
        offset += EXPORT_BATCH_SIZE
        if len(batch) < EXPORT_BATCH_SIZE:
            break


async def stream_subdomains_json(
    asset_id: Optional[str] = None,
    parent_domain: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream subdomains as JSON array (source_module excluded)."""
    supabase = supabase_client.service_client
    
    yield "["
    first = True
    offset = 0
    
    while True:
        query = supabase.table("subdomains").select(
            "subdomain, parent_domain, discovered_at"
        )
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if parent_domain:
            query = query.eq("parent_domain", parent_domain)
        
        query = query.order("discovered_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            if not first:
                yield ","
            yield json.dumps(row)
            first = False
        
        offset += EXPORT_BATCH_SIZE
        if len(batch) < EXPORT_BATCH_SIZE:
            break
    
    yield "]"


@router.get("/subdomains")
async def export_subdomains(
    format: str = Query("csv", regex="^(csv|json)$", description="Export format"),
    asset_id: Optional[str] = Query(None, description="Filter by asset/program ID"),
    parent_domain: Optional[str] = Query(None, description="Filter by parent domain"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Export subdomains as CSV or JSON.
    
    **Free for all users.**
    
    Streams the full dataset matching your filters.
    """
    if format == "csv":
        return StreamingResponse(
            stream_subdomains_csv(asset_id, parent_domain),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=subdomains-export.csv"}
        )
    else:
        return StreamingResponse(
            stream_subdomains_json(asset_id, parent_domain),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=subdomains-export.json"}
        )


# =============================================================================
# DNS Records Export (FREE)
# =============================================================================

async def stream_dns_csv(
    asset_id: Optional[str] = None,
    record_type: Optional[str] = None,
    subdomain: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream DNS records as CSV."""
    supabase = supabase_client.service_client
    
    yield format_csv_row([
        "subdomain", "parent_domain", "record_type", "record_value", "ttl", "resolved_at"
    ])
    
    offset = 0
    while True:
        query = supabase.table("dns_records").select(
            "subdomain, parent_domain, record_type, record_value, ttl, resolved_at"
        )
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if record_type:
            query = query.eq("record_type", record_type)
        if subdomain:
            query = query.ilike("subdomain", f"%{subdomain}%")
        
        query = query.order("resolved_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            yield format_csv_row([
                row.get("subdomain", ""),
                row.get("parent_domain", ""),
                row.get("record_type", ""),
                row.get("record_value", ""),
                row.get("ttl", ""),
                row.get("resolved_at", ""),
            ])
        
        offset += EXPORT_BATCH_SIZE
        if len(batch) < EXPORT_BATCH_SIZE:
            break


async def stream_dns_json(
    asset_id: Optional[str] = None,
    record_type: Optional[str] = None,
    subdomain: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream DNS records as JSON array."""
    supabase = supabase_client.service_client
    
    yield "["
    first = True
    offset = 0
    
    while True:
        query = supabase.table("dns_records").select(
            "subdomain, parent_domain, record_type, record_value, ttl, resolved_at"
        )
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if record_type:
            query = query.eq("record_type", record_type)
        if subdomain:
            query = query.ilike("subdomain", f"%{subdomain}%")
        
        query = query.order("resolved_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            if not first:
                yield ","
            yield json.dumps(row)
            first = False
        
        offset += EXPORT_BATCH_SIZE
        if len(batch) < EXPORT_BATCH_SIZE:
            break
    
    yield "]"


@router.get("/dns")
async def export_dns_records(
    format: str = Query("csv", regex="^(csv|json)$", description="Export format"),
    asset_id: Optional[str] = Query(None, description="Filter by asset/program ID"),
    record_type: Optional[str] = Query(None, description="Filter by record type (A, AAAA, CNAME, MX, TXT)"),
    subdomain: Optional[str] = Query(None, description="Search by subdomain (partial match)"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Export DNS records as CSV or JSON.
    
    **Free for all users.**
    
    Streams the full dataset matching your filters.
    """
    if format == "csv":
        return StreamingResponse(
            stream_dns_csv(asset_id, record_type, subdomain),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=dns-records-export.csv"}
        )
    else:
        return StreamingResponse(
            stream_dns_json(asset_id, record_type, subdomain),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=dns-records-export.json"}
        )


# =============================================================================
# HTTP Probes Export (FREE)
# =============================================================================

async def stream_probes_csv(
    asset_id: Optional[str] = None,
    status_code: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Stream HTTP probes as CSV."""
    supabase = supabase_client.service_client
    
    yield format_csv_row([
        "url", "subdomain", "status_code", "title", "webserver", 
        "content_type", "ip", "created_at"
    ])
    
    offset = 0
    while True:
        query = supabase.table("http_probes").select(
            "url, subdomain, status_code, title, webserver, content_type, ip, created_at"
        )
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if status_code:
            query = query.eq("status_code", status_code)
        
        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            yield format_csv_row([
                row.get("url", ""),
                row.get("subdomain", ""),
                row.get("status_code", ""),
                row.get("title", ""),
                row.get("webserver", ""),
                row.get("content_type", ""),
                row.get("ip", ""),
                row.get("created_at", ""),
            ])
        
        offset += EXPORT_BATCH_SIZE
        if len(batch) < EXPORT_BATCH_SIZE:
            break


async def stream_probes_json(
    asset_id: Optional[str] = None,
    status_code: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Stream HTTP probes as JSON array."""
    supabase = supabase_client.service_client
    
    yield "["
    first = True
    offset = 0
    
    while True:
        query = supabase.table("http_probes").select(
            "url, subdomain, status_code, title, webserver, content_type, ip, created_at"
        )
        
        if asset_id:
            query = query.eq("asset_id", asset_id)
        if status_code:
            query = query.eq("status_code", status_code)
        
        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + EXPORT_BATCH_SIZE - 1)
        
        result = query.execute()
        batch = result.data or []
        
        if not batch:
            break
        
        for row in batch:
            if not first:
                yield ","
            yield json.dumps(row)
            first = False
        
        offset += EXPORT_BATCH_SIZE
        if len(batch) < EXPORT_BATCH_SIZE:
            break
    
    yield "]"


@router.get("/probes")
async def export_http_probes(
    format: str = Query("csv", regex="^(csv|json)$", description="Export format"),
    asset_id: Optional[str] = Query(None, description="Filter by asset/program ID"),
    status_code: Optional[int] = Query(None, description="Filter by status code"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Export HTTP probes as CSV or JSON.
    
    **Free for all users.**
    
    Streams the full dataset matching your filters.
    """
    if format == "csv":
        return StreamingResponse(
            stream_probes_csv(asset_id, status_code),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=http-probes-export.csv"}
        )
    else:
        return StreamingResponse(
            stream_probes_json(asset_id, status_code),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=http-probes-export.json"}
        )
