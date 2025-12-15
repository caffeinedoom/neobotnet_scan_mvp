"""
DNS Record Schemas for API responses and validation.

This module defines Pydantic models for DNS resolution data,
enabling type-safe API interactions and database serialization.

Author: Pluckware Development Team
Date: October 28, 2025
Phase: 3 - Backend Integration & Module Registration
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class DNSRecordType(str, Enum):
    """
    Valid DNS record types supported by DNSX module.
    
    Supports the 5 most common DNS record types for reconnaissance:
    - A: IPv4 address resolution
    - AAAA: IPv6 address resolution
    - CNAME: Canonical name (alias) records
    - MX: Mail exchange servers
    - TXT: Text records (SPF, DKIM, domain verification)
    """
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"


class DNSRecord(BaseModel):
    """
    DNS record response model.
    
    Represents a single DNS resolution result from the dns_records table.
    Used for API responses when fetching individual DNS records.
    """
    id: str = Field(..., description="UUID of the DNS record")
    subdomain: str = Field(..., description="Fully qualified subdomain (e.g., api.example.com)")
    parent_domain: str = Field(..., description="Parent domain (e.g., example.com)")
    record_type: DNSRecordType = Field(..., description="Type of DNS record")
    record_value: str = Field(..., description="Resolved value (IP, hostname, or text)")
    ttl: Optional[int] = Field(None, description="Time to live in seconds")
    priority: Optional[int] = Field(None, description="MX record priority (null for other types)")
    resolved_at: datetime = Field(..., description="Timestamp when record was resolved")
    cloud_provider: Optional[str] = Field(None, description="Detected cloud provider (aws, gcp, azure, etc.)")
    scan_job_id: Optional[str] = Field(None, description="Associated scan job UUID")
    batch_scan_id: Optional[str] = Field(None, description="Associated batch scan UUID")
    asset_id: Optional[str] = Field(None, description="Associated asset UUID")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "subdomain": "api.example.com",
                "parent_domain": "example.com",
                "record_type": "A",
                "record_value": "192.168.1.1",
                "ttl": 300,
                "priority": None,
                "resolved_at": "2025-10-28T12:00:00Z",
                "cloud_provider": "aws",
                "scan_job_id": "123e4567-e89b-12d3-a456-426614174000",
                "batch_scan_id": None,
                "asset_id": "789e0123-e89b-12d3-a456-426614174000",
                "created_at": "2025-10-28T12:00:00Z",
                "updated_at": "2025-10-28T12:00:00Z"
            }
        }


class DNSRecordCreate(BaseModel):
    """
    Internal model for creating DNS records.
    
    Used by the DNSX Go container when inserting records via
    the bulk_insert_dns_records PostgreSQL function.
    """
    subdomain: str
    parent_domain: str
    record_type: DNSRecordType
    record_value: str
    ttl: Optional[int] = None
    priority: Optional[int] = None
    resolved_at: datetime
    scan_job_id: Optional[str] = None
    batch_scan_id: Optional[str] = None
    asset_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "subdomain": "mail.example.com",
                "parent_domain": "example.com",
                "record_type": "MX",
                "record_value": "mail.google.com",
                "ttl": 3600,
                "priority": 10,
                "resolved_at": "2025-10-28T12:00:00Z",
                "scan_job_id": "123e4567-e89b-12d3-a456-426614174000",
                "batch_scan_id": "456e7890-e89b-12d3-a456-426614174000",
                "asset_id": "789e0123-e89b-12d3-a456-426614174000"
            }
        }


class SubdomainDNSSummary(BaseModel):
    """
    Aggregated DNS summary for a single subdomain.
    
    Matches the subdomain_current_dns view structure.
    Provides a consolidated view of all DNS records for a subdomain,
    grouped by record type.
    """
    subdomain: str = Field(..., description="Subdomain name")
    parent_domain: str = Field(..., description="Parent domain")
    ipv4_addresses: List[str] = Field(default_factory=list, description="A record IPs")
    ipv6_addresses: List[str] = Field(default_factory=list, description="AAAA record IPs")
    cname_records: List[str] = Field(default_factory=list, description="CNAME targets")
    mx_records: List[Dict[str, Any]] = Field(default_factory=list, description="MX records with priority")
    txt_records: List[str] = Field(default_factory=list, description="TXT record values")
    last_resolved_at: Optional[datetime] = Field(None, description="Most recent resolution timestamp")
    latest_scan_job_id: Optional[str] = Field(None, description="Most recent scan job UUID")
    asset_id: Optional[str] = Field(None, description="Associated asset UUID")
    total_records: int = Field(..., description="Total DNS records for this subdomain")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "subdomain": "api.example.com",
                "parent_domain": "example.com",
                "ipv4_addresses": ["192.168.1.1", "192.168.1.2"],
                "ipv6_addresses": ["2001:db8::1"],
                "cname_records": [],
                "mx_records": [{"host": "mail.example.com", "priority": 10}],
                "txt_records": ["v=spf1 include:_spf.example.com ~all"],
                "last_resolved_at": "2025-10-28T12:00:00Z",
                "latest_scan_job_id": "123e4567-e89b-12d3-a456-426614174000",
                "asset_id": "789e0123-e89b-12d3-a456-426614174000",
                "total_records": 5
            }
        }


class DNSResolutionStats(BaseModel):
    """
    Statistics for DNS resolution operations.
    
    Provides aggregate metrics about DNS resolution results,
    useful for scan summaries and reporting.
    """
    total_records: int = Field(..., description="Total DNS records resolved")
    unique_subdomains: int = Field(..., description="Number of unique subdomains resolved")
    record_type_breakdown: Dict[str, int] = Field(..., description="Count by record type")
    cloud_provider_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count by cloud provider")
    resolution_duration_seconds: Optional[float] = Field(None, description="Total resolution time")

    class Config:
        json_schema_extra = {
            "example": {
                "total_records": 150,
                "unique_subdomains": 50,
                "record_type_breakdown": {
                    "A": 75,
                    "AAAA": 25,
                    "CNAME": 20,
                    "MX": 15,
                    "TXT": 15
                },
                "cloud_provider_breakdown": {
                    "aws": 40,
                    "gcp": 10,
                    "unknown": 25
                },
                "resolution_duration_seconds": 125.5
            }
        }


class DNSQueryRequest(BaseModel):
    """
    Request model for DNS queries (future use).
    
    Used when manually triggering DNS resolution for specific subdomains
    via API endpoints (to be implemented in Phase 5).
    """
    subdomains: List[str] = Field(
        ..., 
        description="List of subdomains to resolve", 
        min_length=1, 
        max_length=200
    )
    record_types: Optional[List[DNSRecordType]] = Field(
        None, 
        description="Specific record types to query (defaults to all)"
    )
    include_cloud_detection: bool = Field(
        True, 
        description="Enable cloud provider detection (future feature)"
    )

    @validator('subdomains')
    def validate_subdomains(cls, v):
        """Ensure subdomain count is within limits."""
        if len(v) > 200:
            raise ValueError('Maximum 200 subdomains per request')
        
        # Remove duplicates
        unique_subdomains = list(set(v))
        if len(unique_subdomains) != len(v):
            raise ValueError('Duplicate subdomains detected')
        return unique_subdomains

    @validator('record_types')
    def validate_record_types(cls, v):
        """Ensure no duplicate record types."""
        if v is not None and len(v) != len(set(v)):
            return list(set(v))
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "subdomains": ["api.example.com", "cdn.example.com"],
                "record_types": ["A", "AAAA"],
                "include_cloud_detection": True
            }
        }


# ================================================================
# API Response Models
# ================================================================

class DNSRecordWithAssetInfo(DNSRecord):
    """
    DNS record extended with asset information for user-level queries.
    
    Extends the base DNSRecord with asset_name for display purposes.
    Used by the user-level paginated DNS endpoint.
    """
    asset_name: str = Field(..., description="Human-readable asset name")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "subdomain": "api.epicgames.com",
                "parent_domain": "epicgames.com",
                "record_type": "A",
                "record_value": "104.16.1.10",
                "ttl": 300,
                "priority": None,
                "resolved_at": "2025-11-02T12:00:00Z",
                "cloud_provider": "cloudflare",
                "scan_job_id": "123e4567-e89b-12d3-a456-426614174000",
                "batch_scan_id": None,
                "asset_id": "c1806931-57d0-4f91-9398-e0978d89fb2f",
                "created_at": "2025-11-02T12:00:00Z",
                "updated_at": "2025-11-02T12:00:00Z",
                "asset_name": "EpicGames"
            }
        }


class DNSRecordListResponse(BaseModel):
    """
    Paginated response model for DNS records API endpoint.
    
    This model wraps a list of DNS records with pagination metadata,
    following the same pattern as other paginated endpoints in the API.
    Used by GET /api/v1/assets/{asset_id}/dns-records endpoint.
    """
    dns_records: List[DNSRecord] = Field(
        ..., 
        description="List of DNS records for the current page"
    )
    total_count: int = Field(
        ..., 
        description="Total number of DNS records matching the query",
        ge=0
    )
    limit: int = Field(
        ..., 
        description="Number of records per page (applied limit)",
        ge=1,
        le=1000
    )
    offset: int = Field(
        ..., 
        description="Pagination offset (starting position)",
        ge=0
    )
    warning: Optional[str] = Field(
        None,
        description="Warning message for large result sets or performance tips"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "dns_records": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "subdomain": "api.epicgames.com",
                        "parent_domain": "epicgames.com",
                        "record_type": "A",
                        "record_value": "104.16.1.10",
                        "ttl": 300,
                        "priority": None,
                        "resolved_at": "2025-11-02T12:00:00Z",
                        "cloud_provider": "cloudflare",
                        "scan_job_id": "123e4567-e89b-12d3-a456-426614174000",
                        "batch_scan_id": None,
                        "asset_id": "c1806931-57d0-4f91-9398-e0978d89fb2f",
                        "created_at": "2025-11-02T12:00:00Z",
                        "updated_at": "2025-11-02T12:00:00Z"
                    }
                ],
                "total_count": 1020,
                "limit": 50,
                "offset": 0,
                "warning": None
            }
        }


class PaginatedDNSResponse(BaseModel):
    """
    User-level paginated response for DNS records.
    
    Similar to PaginatedSubdomainResponse, this provides a complete
    pagination structure for user-level DNS record queries with asset
    information included.
    Used by GET /api/v1/assets/dns-records/paginated endpoint.
    """
    dns_records: List[DNSRecordWithAssetInfo] = Field(
        ...,
        description="List of DNS records with asset information"
    )
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata (total, page, per_page, total_pages, has_next, has_prev)"
    )
    filters: Dict[str, Any] = Field(
        ...,
        description="Applied filters for the query"
    )
    stats: Dict[str, Any] = Field(
        ...,
        description="Statistics about DNS records (total_assets, filtered_count, record_type_breakdown)"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "dns_records": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "subdomain": "api.epicgames.com",
                        "parent_domain": "epicgames.com",
                        "record_type": "A",
                        "record_value": "104.16.1.10",
                        "ttl": 300,
                        "priority": None,
                        "resolved_at": "2025-11-02T12:00:00Z",
                        "cloud_provider": "cloudflare",
                        "scan_job_id": "123e4567-e89b-12d3-a456-426614174000",
                        "batch_scan_id": None,
                        "asset_id": "c1806931-57d0-4f91-9398-e0978d89fb2f",
                        "created_at": "2025-11-02T12:00:00Z",
                        "updated_at": "2025-11-02T12:00:00Z",
                        "asset_name": "EpicGames"
                    }
                ],
                "pagination": {
                    "total": 2892,
                    "page": 1,
                    "per_page": 50,
                    "total_pages": 58,
                    "has_next": True,
                    "has_prev": False
                },
                "filters": {
                    "asset_id": None,
                    "parent_domain": None,
                    "record_type": None,
                    "search": None
                },
                "stats": {
                    "total_assets": 3,
                    "filtered_count": 2892,
                    "record_type_breakdown": {
                        "A": 1500,
                        "AAAA": 800,
                        "CNAME": 400,
                        "MX": 100,
                        "TXT": 92
                    }
                }
            }
        }


# ================================================================
# Grouped DNS Records (for enhanced UI display)
# ================================================================

class DNSRecordDetail(BaseModel):
    """
    Individual DNS record detail within a grouped view.
    
    Contains essential information for displaying a single DNS record
    within a subdomain group. Lighter weight than full DNSRecord.
    """
    id: str = Field(..., description="UUID of the DNS record")
    record_value: str = Field(..., description="Resolved value (IP, hostname, or text)")
    ttl: Optional[int] = Field(None, description="Time to live in seconds")
    priority: Optional[int] = Field(None, description="MX record priority (null for other types)")
    resolved_at: datetime = Field(..., description="Timestamp when record was resolved")
    cloud_provider: Optional[str] = Field(None, description="Detected cloud provider")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "record_value": "104.16.1.10",
                "ttl": 300,
                "priority": None,
                "resolved_at": "2025-11-06T12:00:00Z",
                "cloud_provider": "cloudflare"
            }
        }


class DNSRecordsByType(BaseModel):
    """
    DNS records grouped by record type.
    
    Organizes all DNS records for a subdomain by their type (A, AAAA, etc.)
    for elegant display in the UI.
    """
    A: List[DNSRecordDetail] = Field(default_factory=list, description="A records (IPv4)")
    AAAA: List[DNSRecordDetail] = Field(default_factory=list, description="AAAA records (IPv6)")
    CNAME: List[DNSRecordDetail] = Field(default_factory=list, description="CNAME records (aliases)")
    MX: List[DNSRecordDetail] = Field(default_factory=list, description="MX records (mail servers)")
    TXT: List[DNSRecordDetail] = Field(default_factory=list, description="TXT records (text data)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "A": [
                    {"id": "...", "record_value": "104.16.1.10", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"},
                    {"id": "...", "record_value": "104.16.2.10", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"}
                ],
                "AAAA": [
                    {"id": "...", "record_value": "2606:4700::6810:110a", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"}
                ],
                "CNAME": [],
                "MX": [],
                "TXT": []
            }
        }


class GroupedDNSRecord(BaseModel):
    """
    Subdomain with all its DNS records grouped by type.
    
    This model represents a single subdomain with all its DNS records
    organized by record type for elegant UI display. Designed for the
    grouped DNS records view where users want to see all DNS information
    for a subdomain at once.
    """
    subdomain: str = Field(..., description="Fully qualified subdomain")
    parent_domain: str = Field(..., description="Parent domain")
    asset_name: str = Field(..., description="Asset name for display")
    asset_id: str = Field(..., description="Asset UUID")
    total_records: int = Field(..., description="Total DNS records for this subdomain")
    last_resolved: datetime = Field(..., description="Most recent resolution timestamp")
    records_by_type: DNSRecordsByType = Field(..., description="DNS records organized by type")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "subdomain": "api.epicgames.com",
                "parent_domain": "epicgames.com",
                "asset_name": "EpicGames",
                "asset_id": "c1806931-57d0-4f91-9398-e0978d89fb2f",
                "total_records": 8,
                "last_resolved": "2025-11-06T12:00:00Z",
                "records_by_type": {
                    "A": [
                        {"id": "...", "record_value": "104.16.1.10", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"},
                        {"id": "...", "record_value": "104.16.2.10", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"}
                    ],
                    "AAAA": [
                        {"id": "...", "record_value": "2606:4700::6810:110a", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"}
                    ],
                    "CNAME": [
                        {"id": "...", "record_value": "cdn.epicgames.com", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": None}
                    ],
                    "MX": [
                        {"id": "...", "record_value": "mail1.epic.com", "ttl": 3600, "priority": 10, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": None},
                        {"id": "...", "record_value": "mail2.epic.com", "ttl": 3600, "priority": 20, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": None}
                    ],
                    "TXT": [
                        {"id": "...", "record_value": "v=spf1 include:_spf.google.com ~all", "ttl": 3600, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": None}
                    ]
                }
            }
        }


class PaginatedGroupedDNSResponse(BaseModel):
    """
    Paginated response for grouped DNS records.
    
    Returns DNS records grouped by subdomain with pagination applied
    to the subdomain count (not individual record count). This provides
    a more intuitive view where users see one card per subdomain with
    all its DNS records organized by type.
    
    Used by GET /api/v1/assets/dns-records/paginated?grouped=true
    """
    grouped_records: List[GroupedDNSRecord] = Field(
        ...,
        description="List of subdomains with their DNS records grouped by type"
    )
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata (total = unique subdomains, not record count)"
    )
    filters: Dict[str, Any] = Field(
        ...,
        description="Applied filters for the query"
    )
    stats: Dict[str, Any] = Field(
        ...,
        description="Statistics (total_subdomains, total_dns_records, record_type_breakdown)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "grouped_records": [
                    {
                        "subdomain": "api.epicgames.com",
                        "parent_domain": "epicgames.com",
                        "asset_name": "EpicGames",
                        "asset_id": "c1806931-57d0-4f91-9398-e0978d89fb2f",
                        "total_records": 8,
                        "last_resolved": "2025-11-06T12:00:00Z",
                        "records_by_type": {
                            "A": [{"id": "...", "record_value": "104.16.1.10", "ttl": 300, "priority": None, "resolved_at": "2025-11-06T12:00:00Z", "cloud_provider": "cloudflare"}],
                            "AAAA": [],
                            "CNAME": [],
                            "MX": [],
                            "TXT": []
                        }
                    }
                ],
                "pagination": {
                    "total": 150,
                    "page": 1,
                    "per_page": 50,
                    "total_pages": 3,
                    "has_next": True,
                    "has_prev": False
                },
                "filters": {
                    "asset_id": None,
                    "parent_domain": None,
                    "record_type": None,
                    "search": None
                },
                "stats": {
                    "total_subdomains": 150,
                    "total_dns_records": 2892,
                    "total_assets": 3,
                    "record_type_breakdown": {
                        "A": 1500,
                        "AAAA": 800,
                        "CNAME": 400,
                        "MX": 100,
                        "TXT": 92
                    }
                }
            }
        }
