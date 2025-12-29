"""
URL Schemas for API responses.

Defines Pydantic models for URL data from the urls table.
URLs are discovered by Katana, Waymore, GAU, etc. and probed by url-resolver.

Author: Pluckware Development Team
Date: December 2025
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel
from datetime import datetime


class URLResponse(BaseModel):
    """Response model for a single URL record."""
    id: str
    asset_id: str
    scan_job_id: Optional[str] = None
    
    # Core URL data
    url: str
    url_hash: str
    domain: str
    path: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    
    # Discovery tracking
    sources: List[str] = []
    first_discovered_by: Optional[str] = None
    first_discovered_at: Optional[datetime] = None
    
    # Resolution metadata
    resolved_at: Optional[datetime] = None
    is_alive: Optional[bool] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    response_time_ms: Optional[int] = None
    
    # Enrichment data
    title: Optional[str] = None
    final_url: Optional[str] = None
    redirect_chain: Optional[List[Any]] = None  # Can be status codes (int) or URLs (str)
    webserver: Optional[str] = None
    technologies: Optional[List[str]] = None
    
    # Classification
    has_params: bool = False
    file_extension: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class URLStatsResponse(BaseModel):
    """Response model for URL statistics."""
    total_urls: int = 0
    alive_urls: int = 0
    dead_urls: int = 0
    pending_urls: int = 0
    urls_with_params: int = 0
    unique_domains: int = 0
    top_sources: List[Dict[str, Any]] = []
    top_status_codes: List[Dict[str, Any]] = []
    top_technologies: List[Dict[str, Any]] = []
    top_file_extensions: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True


class PaginatedURLResponse(BaseModel):
    """Response model for paginated URL results."""
    urls: List[URLResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

    class Config:
        from_attributes = True

