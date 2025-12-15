"""
HTTP Probe Schemas for API responses and validation.

This module defines Pydantic models for HTTP probe data from the httpx module,
enabling type-safe API interactions and database serialization.

Author: Pluckware Development Team
Date: November 17, 2025
Phase: HTTPx Frontend Implementation - Phase 1
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HTTPProbeBase(BaseModel):
    """
    Base HTTP probe model with all fields from http_probes table.
    
    Represents a single HTTP probe result from the httpx module.
    Handles nullable fields and JSONB arrays based on real production data.
    """
    # Core URL fields (always present)
    url: str = Field(..., description="Full URL probed (e.g., https://autodiscover.greatlakescheese.com)")
    subdomain: str = Field(..., description="Fully qualified subdomain")
    parent_domain: str = Field(..., description="Parent/apex domain")
    scheme: str = Field(..., description="URL scheme: http or https")
    port: int = Field(..., description="Port number (443, 80, 8080, etc.)")
    
    # HTTP Response fields (nullable based on real data)
    status_code: Optional[int] = Field(None, description="HTTP status code (200, 404, 500, etc.)")
    title: Optional[str] = Field(None, description="HTML page title (can be null)")
    webserver: Optional[str] = Field(None, description="Server header value (e.g., 'Apache', 'Microsoft-IIS/10.0')")
    content_length: Optional[int] = Field(None, description="Response content length in bytes (can be null)")
    content_type: Optional[str] = Field(None, description="Content-Type header (e.g., 'text/html')")
    final_url: Optional[str] = Field(None, description="Final URL after following redirects")
    ip: Optional[str] = Field(None, description="Server IP address")
    
    # Technology detection (JSONB arrays - can be empty)
    technologies: List[str] = Field(
        default_factory=list, 
        description="Detected technologies with versions (e.g., ['IIS:10.0', 'Microsoft ASP.NET', 'Windows Server'])"
    )
    cdn_name: Optional[str] = Field(None, description="CDN provider name (e.g., 'Cloudflare', 'Akamai')")
    asn: Optional[str] = Field(None, description="Autonomous System Number")
    
    # Metadata fields
    chain_status_codes: List[int] = Field(
        default_factory=list,
        description="HTTP status codes from redirect chain (e.g., [302, 302, 200] or empty [])"
    )
    location: Optional[str] = Field(None, description="Location header from redirects")
    favicon_md5: Optional[str] = Field(None, description="MD5 hash of favicon (for clustering similar sites)")
    
    # Timestamp
    created_at: datetime = Field(..., description="Timestamp when probe was performed")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "url": "https://autodiscover.greatlakescheese.com",
                "subdomain": "autodiscover.greatlakescheese.com",
                "parent_domain": "greatlakescheese.com",
                "scheme": "https",
                "port": 443,
                "status_code": 200,
                "title": "Outlook",
                "webserver": "Microsoft-IIS/10.0 Microsoft-HTTPAPI/2.0",
                "content_length": 58725,
                "content_type": "text/html",
                "final_url": "https://autodiscover.greatlakescheese.com/owa/auth/logon.aspx",
                "ip": "40.136.126.11",
                "technologies": ["IIS:10.0", "Microsoft ASP.NET", "Microsoft HTTPAPI:2.0", "Windows Server"],
                "cdn_name": None,
                "asn": None,
                "chain_status_codes": [302, 302, 200],
                "location": None,
                "favicon_md5": None,
                "created_at": "2025-11-16T17:33:03Z"
            }
        }


class HTTPProbeResponse(HTTPProbeBase):
    """
    HTTP probe response model for API responses.
    
    Extends HTTPProbeBase with identifier fields.
    Used when returning individual probe records via API endpoints.
    """
    id: str = Field(..., description="UUID of the HTTP probe record")
    scan_job_id: str = Field(..., description="Associated scan job UUID")
    asset_id: str = Field(..., description="Associated asset UUID")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "0462222e-963f-4936-adb2-1a75d53d8a9b",
                "scan_job_id": "302ef2b9-9bb5-4c06-a187-473b37904458",
                "asset_id": "17e70cea-9abd-4d4d-a71b-daa183e9b2de",
                "url": "https://autodiscover.greatlakescheese.com",
                "subdomain": "autodiscover.greatlakescheese.com",
                "parent_domain": "greatlakescheese.com",
                "scheme": "https",
                "port": 443,
                "status_code": 200,
                "title": "Outlook",
                "webserver": "Microsoft-IIS/10.0",
                "content_length": 58725,
                "content_type": "text/html",
                "final_url": "https://autodiscover.greatlakescheese.com/owa/auth/logon.aspx",
                "ip": "40.136.126.11",
                "technologies": ["IIS:10.0", "Microsoft ASP.NET", "Windows Server"],
                "cdn_name": None,
                "asn": None,
                "chain_status_codes": [302, 302, 200],
                "location": None,
                "favicon_md5": None,
                "created_at": "2025-11-16T17:33:03Z"
            }
        }


class HTTPProbeStatsResponse(BaseModel):
    """
    Aggregate statistics for HTTP probe results.
    
    Provides summary metrics for dashboard cards and analytics.
    Used by the /http-probes/stats endpoint.
    """
    total_probes: int = Field(..., description="Total number of HTTP probes")
    status_code_distribution: Dict[int, int] = Field(
        ..., 
        description="Count of probes by status code (e.g., {200: 45, 404: 10, 500: 2})"
    )
    top_technologies: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most common technologies with counts (e.g., [{'name': 'IIS:10.0', 'count': 15}])"
    )
    top_servers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most common web servers with counts (e.g., [{'name': 'Apache', 'count': 20}])"
    )
    cdn_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="CDN providers with counts (e.g., {'Cloudflare': 30, 'Akamai': 10})"
    )
    redirect_chains_count: int = Field(
        ..., 
        description="Number of probes that had redirect chains (chain_status_codes not empty)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_probes": 80,
                "status_code_distribution": {
                    "200": 65,
                    "404": 10,
                    "500": 5
                },
                "top_technologies": [
                    {"name": "IIS:10.0", "count": 25},
                    {"name": "Microsoft ASP.NET", "count": 20},
                    {"name": "Apache", "count": 15}
                ],
                "top_servers": [
                    {"name": "Microsoft-IIS/10.0", "count": 30},
                    {"name": "Apache", "count": 25},
                    {"name": "nginx", "count": 20}
                ],
                "cdn_usage": {
                    "Cloudflare": 15,
                    "Akamai": 5
                },
                "redirect_chains_count": 12
            }
        }
