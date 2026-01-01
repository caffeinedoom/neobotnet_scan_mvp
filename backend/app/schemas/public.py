"""
Public Showcase Schemas

Pydantic models for the public showcase endpoint that displays
sample data from the database without authentication.
"""
from typing import List, Optional
from pydantic import BaseModel


# ============================================================================
# Subdomain Showcase
# ============================================================================

class ShowcaseSubdomain(BaseModel):
    """A subdomain for public display."""
    subdomain: str
    parent_domain: str
    program_name: str


# ============================================================================
# DNS Record Showcase
# ============================================================================

class ShowcaseDNSRecord(BaseModel):
    """A DNS record for public display."""
    subdomain: str
    record_type: str
    value: str
    ttl: Optional[int] = None
    program_name: str


# ============================================================================
# Web Server (HTTP Probe) Showcase
# ============================================================================

class ShowcaseWebServer(BaseModel):
    """A web server/HTTP probe for public display."""
    url: str
    status_code: int
    title: Optional[str] = None
    webserver: Optional[str] = None
    content_length: Optional[int] = None
    technologies: List[str] = []
    program_name: str


# ============================================================================
# Stats Summary
# ============================================================================

class ShowcaseProgram(BaseModel):
    """A program for public display with basic stats."""
    id: str
    name: str
    subdomain_count: int
    server_count: int


class ShowcaseStats(BaseModel):
    """Aggregate statistics for all data types."""
    total_subdomains: int
    total_dns_records: int
    total_web_servers: int
    total_urls: int
    total_programs: int


# ============================================================================
# Combined Showcase Response
# ============================================================================

class ShowcaseResponse(BaseModel):
    """Complete showcase response with sample data and stats."""
    subdomains: List[ShowcaseSubdomain]
    dns_records: List[ShowcaseDNSRecord]
    web_servers: List[ShowcaseWebServer]
    programs: List[ShowcaseProgram]
    stats: ShowcaseStats
