"""
Public Showcase API Endpoints

Provides unauthenticated access to sample reconnaissance data for the landing page.
Rate limited and cached to prevent abuse.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...core.supabase_client import supabase_client
from ...schemas.public import (
    ShowcaseResponse,
    ShowcaseSubdomain,
    ShowcaseDNSRecord,
    ShowcaseWebServer,
    ShowcaseStats,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiter: 10 requests per minute per IP
limiter = Limiter(key_func=get_remote_address)

# Simple in-memory cache
_cache: dict = {
    "data": None,
    "expires_at": None,
}
CACHE_TTL_MINUTES = 5


def get_cached_response() -> Optional[ShowcaseResponse]:
    """Get cached response if still valid."""
    if _cache["data"] and _cache["expires_at"]:
        if datetime.utcnow() < _cache["expires_at"]:
            return _cache["data"]
    return None


def set_cached_response(data: ShowcaseResponse) -> None:
    """Cache the response for TTL minutes."""
    _cache["data"] = data
    _cache["expires_at"] = datetime.utcnow() + timedelta(minutes=CACHE_TTL_MINUTES)


@router.get("/showcase", response_model=ShowcaseResponse)
@limiter.limit("10/minute")
async def get_showcase(request: Request):
    """
    Get sample reconnaissance data for the landing page.
    
    Returns a random selection of subdomains, DNS records, and web servers
    from across all programs. This endpoint is publicly accessible without
    authentication but is rate limited to prevent abuse.
    
    **Rate Limit**: 10 requests per minute per IP
    **Cache**: Response is cached for 5 minutes
    
    Returns:
        ShowcaseResponse: Sample data with statistics
    """
    # Check cache first
    cached = get_cached_response()
    if cached:
        logger.debug("Returning cached showcase data")
        return cached
    
    try:
        client = supabase_client.service_client
        
        # ====================================================================
        # Get all programs (assets) for name lookup
        # ====================================================================
        programs_result = client.table("assets").select("id, name").execute()
        programs = {p["id"]: p["name"] for p in (programs_result.data or [])}
        program_ids = list(programs.keys())
        
        if not program_ids:
            # No programs, return empty response
            return ShowcaseResponse(
                subdomains=[],
                dns_records=[],
                web_servers=[],
                stats=ShowcaseStats(
                    total_subdomains=0,
                    total_dns_records=0,
                    total_web_servers=0,
                    total_urls=0,
                    total_programs=0,
                ),
            )
        
        # ====================================================================
        # Get random subdomains (5 records)
        # ====================================================================
        subdomains_data = []
        # Get a larger sample and pick randomly
        subs_result = client.table("subdomains")\
            .select("subdomain, parent_domain, asset_id")\
            .limit(100)\
            .execute()
        
        if subs_result.data:
            # Shuffle and pick 5
            sampled = random.sample(subs_result.data, min(5, len(subs_result.data)))
            for s in sampled:
                program_name = programs.get(s.get("asset_id"), "Unknown")
                subdomains_data.append(ShowcaseSubdomain(
                    subdomain=s["subdomain"],
                    parent_domain=s.get("parent_domain", ""),
                    program_name=program_name,
                ))
        
        # ====================================================================
        # Get random DNS records (5 records)
        # ====================================================================
        dns_data = []
        dns_result = client.table("dns_records")\
            .select("subdomain, record_type, value, ttl, asset_id")\
            .limit(100)\
            .execute()
        
        if dns_result.data:
            sampled = random.sample(dns_result.data, min(5, len(dns_result.data)))
            for d in sampled:
                program_name = programs.get(d.get("asset_id"), "Unknown")
                dns_data.append(ShowcaseDNSRecord(
                    subdomain=d["subdomain"],
                    record_type=d["record_type"],
                    value=d.get("value", ""),
                    ttl=d.get("ttl"),
                    program_name=program_name,
                ))
        
        # ====================================================================
        # Get random web servers / HTTP probes (5 records)
        # ====================================================================
        servers_data = []
        probes_result = client.table("http_probes")\
            .select("url, status_code, title, webserver, content_length, technologies, asset_id")\
            .limit(100)\
            .execute()
        
        if probes_result.data:
            sampled = random.sample(probes_result.data, min(5, len(probes_result.data)))
            for p in sampled:
                program_name = programs.get(p.get("asset_id"), "Unknown")
                servers_data.append(ShowcaseWebServer(
                    url=p["url"],
                    status_code=p["status_code"],
                    title=p.get("title"),
                    webserver=p.get("webserver"),
                    content_length=p.get("content_length"),
                    technologies=p.get("technologies") or [],
                    program_name=program_name,
                ))
        
        # ====================================================================
        # Get total counts for stats
        # ====================================================================
        total_subdomains = 0
        total_dns = 0
        total_probes = 0
        total_urls = 0
        
        # Count subdomains
        subs_count = client.table("subdomains").select("id", count="exact").execute()
        total_subdomains = subs_count.count or 0
        
        # Count DNS records
        dns_count = client.table("dns_records").select("id", count="exact").execute()
        total_dns = dns_count.count or 0
        
        # Count HTTP probes
        probes_count = client.table("http_probes").select("id", count="exact").execute()
        total_probes = probes_count.count or 0
        
        # Count URLs
        urls_count = client.table("urls").select("id", count="exact").execute()
        total_urls = urls_count.count or 0
        
        # ====================================================================
        # Build response
        # ====================================================================
        response = ShowcaseResponse(
            subdomains=subdomains_data,
            dns_records=dns_data,
            web_servers=servers_data,
            stats=ShowcaseStats(
                total_subdomains=total_subdomains,
                total_dns_records=total_dns,
                total_web_servers=total_probes,
                total_urls=total_urls,
                total_programs=len(program_ids),
            ),
        )
        
        # Cache the response
        set_cached_response(response)
        logger.info(f"Generated fresh showcase data: {len(subdomains_data)} subs, {len(dns_data)} dns, {len(servers_data)} servers")
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating showcase data: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate showcase data")
