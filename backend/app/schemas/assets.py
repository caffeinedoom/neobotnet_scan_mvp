"""
Pydantic schemas for multi-tenant asset management.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict, UUID4
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid

# Import ReconModule from recon schemas
from .recon import ReconModule

class AssetPriority(int, Enum):
    """Asset priority levels."""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    MINIMAL = 1

class Asset(BaseModel):
    """Base asset model."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    bug_bounty_url: Optional[str] = None
    is_active: bool = True
    priority: AssetPriority = AssetPriority.MEDIUM
    tags: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        """Convert None to empty list for backward compatibility with legacy data."""
        if v is None:
            return []
        return v

class AssetCreate(BaseModel):
    """Schema for creating a new asset."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    bug_bounty_url: Optional[str] = None
    priority: AssetPriority = AssetPriority.MEDIUM
    tags: List[str] = Field(default_factory=list)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags."""
        if v is None:
            return []
        # Remove duplicates and limit to 10 tags
        return list(set(v))[:10]

class AssetUpdate(BaseModel):
    """Schema for updating an asset."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    bug_bounty_url: Optional[str] = None
    priority: Optional[AssetPriority] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags."""
        if v is None:
            return None
        # Remove duplicates and limit to 10 tags
        return list(set(v))[:10]

class AssetWithStats(Asset):
    """Asset with statistics."""
    apex_domain_count: int = 0
    total_subdomains: int = 0
    active_domains: int = 0
    last_scan_date: Optional[datetime] = None
    total_scans: int = 0
    completed_scans: int = 0
    failed_scans: int = 0

    @field_validator('apex_domain_count', mode='before')
    @classmethod
    def validate_apex_domain_count(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('total_subdomains', mode='before')
    @classmethod
    def validate_total_subdomains(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('active_domains', mode='before')
    @classmethod
    def validate_active_domains(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('total_scans', mode='before')
    @classmethod
    def validate_total_scans(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('completed_scans', mode='before')
    @classmethod
    def validate_completed_scans(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('failed_scans', mode='before')
    @classmethod
    def validate_failed_scans(cls, v):
        if v is None:
            return 0
        return v

class ApexDomain(BaseModel):
    """Base apex domain model."""
    id: uuid.UUID
    asset_id: uuid.UUID
    domain: str
    description: Optional[str] = None
    is_active: bool = True
    last_scanned_at: Optional[datetime] = None
    registrar: Optional[str] = None
    dns_servers: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('dns_servers', mode='before')
    @classmethod
    def validate_dns_servers(cls, v):
        """Convert None to empty list for backward compatibility with legacy data."""
        if v is None:
            return []
        return v
    
    @field_validator('metadata', mode='before')
    @classmethod
    def validate_metadata(cls, v):
        """Convert None to empty dict for backward compatibility with legacy data."""
        if v is None:
            return {}
        return v

class ApexDomainCreate(BaseModel):
    """Schema for creating a new apex domain."""
    asset_id: Optional[uuid.UUID] = None  # Set from URL path
    domain: str
    description: Optional[str] = None
    is_active: bool = True

class ApexDomainUpdate(BaseModel):
    """Schema for updating an apex domain."""
    domain: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    registrar: Optional[str] = None
    dns_servers: Optional[List[str]] = None

class ApexDomainWithStats(ApexDomain):
    """Apex domain with statistics."""
    total_scans: int = 0
    completed_scans: int = 0
    failed_scans: int = 0
    total_subdomains: int = 0

    @field_validator('total_scans', mode='before')
    @classmethod
    def validate_total_scans(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('completed_scans', mode='before')
    @classmethod
    def validate_completed_scans(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('failed_scans', mode='before')
    @classmethod
    def validate_failed_scans(cls, v):
        if v is None:
            return 0
        return v
    
    @field_validator('total_subdomains', mode='before')
    @classmethod
    def validate_total_subdomains(cls, v):
        if v is None:
            return 0
        return v

class AssetWithDomains(BaseModel):
    """Schema for creating an asset with multiple domains."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    bug_bounty_url: Optional[str] = None
    priority: AssetPriority = AssetPriority.MEDIUM
    domains: List[str] = Field(..., min_items=1)

class UserAssetSummary(BaseModel):
    """User's asset summary statistics."""
    total_assets: int = 0
    active_assets: int = 0
    total_apex_domains: int = 0
    total_subdomains: int = 0

# ================================================================
# Asset Scan Job Schemas (NEW - for asset-level scan tracking)
# ================================================================

class AssetScanStatus(str, Enum):
    """Status options for asset scan jobs."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AssetScanJobCreate(BaseModel):
    """Schema for creating a new asset scan job."""
    asset_id: UUID4
    modules: List[ReconModule] = Field(default=[ReconModule.SUBFINDER])
    active_domains_only: bool = Field(default=True, description="Only scan active apex domains")

class AssetScanJobBase(BaseModel):
    """Base schema for asset scan jobs."""
    id: UUID4
    user_id: UUID4
    asset_id: UUID4
    modules: List[str]
    status: AssetScanStatus
    total_domains: int = Field(ge=0)
    completed_domains: int = Field(ge=0)
    active_domains_only: bool
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AssetScanJob(AssetScanJobBase):
    """Complete asset scan job schema."""
    pass

class AssetScanJobWithAsset(AssetScanJobBase):
    """Asset scan job with asset information."""
    asset_name: str
    progress_percentage: float = Field(ge=0, le=100)
    individual_scan_count: int = Field(ge=0) 
    total_subdomains_found: int = Field(ge=0)

class AssetScanJobUpdate(BaseModel):
    """Schema for updating asset scan job status."""
    status: Optional[AssetScanStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_domains: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# ================================================================
# Asset Scan Request/Response (NEW - simplified for asset-level)
# ================================================================

class AssetScanRequest(BaseModel):
    """Request schema for starting asset scans."""
    # BUG #9 FIX: Include DNSx by default to enable streaming pipeline
    # Streaming requires both producer (subfinder) and consumer (dnsx)
    modules: List[ReconModule] = Field(
        default=[ReconModule.SUBFINDER, ReconModule.DNSX],
        description="Reconnaissance modules to execute. Default: subdomain discovery + DNS resolution for full reconnaissance."
    )
    active_domains_only: bool = Field(default=True, description="Only scan active apex domains")

class AssetScanResponse(BaseModel):
    """Response schema for asset scan initiation."""
    asset_scan_id: UUID4 = Field(description="Asset-level scan job ID")
    asset_id: UUID4
    asset_name: str
    total_domains: int
    active_domains: int
    modules: List[str]
    status: AssetScanStatus
    created_at: str
    estimated_completion: Optional[str] = None
    
    class Config:
        json_encoders = {
            UUID4: str,
            uuid.UUID: str,
            datetime: lambda v: v.isoformat()
        }
        
        # Use enhanced JSON encoder for nested UUID handling
        # This ensures template modules work seamlessly
        @staticmethod
        def json_dumps(obj, **kwargs):
            from ..utils.json_encoder import safe_json_dumps
            return safe_json_dumps(obj, **kwargs)

# ================================================================
# Enhanced Schemas for Consolidation (NEW)
# ================================================================

class EnhancedAssetScanRequest(AssetScanRequest):
    """Enhanced request schema for consolidated asset scanning with optimization features."""
    
    # Core scanning config inherited from AssetScanRequest:
    # - modules: List[ReconModule] = Field(default=[ReconModule.SUBFINDER]) 
    # - active_domains_only: bool = Field(default=True)
    
    # NEW: Optimization features
    enable_batch_optimization: bool = Field(
        default=True, 
        description="Enable intelligent batch processing optimization"
    )
    optimization_preference: str = Field(
        default="balanced", 
        pattern="^(speed|cost|balanced)$",
        description="Optimization preference: speed, cost, or balanced"
    )
    
    # NEW: Notification preferences
    enable_real_time_notifications: bool = Field(
        default=True,
        description="Enable WebSocket real-time progress notifications"
    )
    notification_webhooks: Optional[List[str]] = Field(
        default=None,
        description="Optional webhook URLs for scan completion notifications"
    )
    
    # NEW: Advanced configuration
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Scan priority level (1=highest, 5=lowest)"
    )
    max_concurrent_domains: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of domains to scan concurrently"
    )

class EnhancedAssetScanResponse(AssetScanResponse):
    """Enhanced response schema for consolidated asset scanning with optimization details."""
    
    # All existing fields inherited from AssetScanResponse:
    # - asset_scan_id, asset_id, asset_name, total_domains, etc.
    
    # NEW: Optimization information
    optimization_strategy: str = Field(
        description="Chosen optimization strategy: 'individual_processing' or 'batch_processing'"
    )
    optimization_analysis: Dict[str, Any] = Field(
        description="Detailed analysis of optimization decision and reasoning"
    )
    
    # NEW: Cost analysis
    cost_analysis: Dict[str, Any] = Field(
        description="Estimated cost, time, and resource analysis"
    )
    estimated_cost_savings_percent: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Estimated cost savings percentage vs individual processing"
    )
    estimated_duration_minutes: int = Field(
        ge=1,
        description="Estimated scan duration in minutes"
    )
    
    # NEW: Real-time tracking
    real_time_tracking: Dict[str, Any] = Field(
        description="WebSocket and progress tracking configuration"
    )
    batch_id: Optional[UUID4] = Field(
        default=None,
        description="Batch ID for tracking if batch processing is used"
    )
    
    # NEW: Performance metrics
    performance_metrics: Dict[str, Any] = Field(
        description="Execution metrics, timing, and resource utilization data"
    )

class BulkAssetOperation(BaseModel):
    """Schema for bulk asset operations."""
    operation: str = Field(..., pattern="^(scan|delete)$")
    asset_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=50)

# ================================================================
# Subdomain Pagination Schemas (NEW - for efficient data loading)
# ================================================================

class SubdomainWithAssetInfo(BaseModel):
    """
    Subdomain with asset and scan job information (post-migration cleanup).
    
    MIGRATION NOTE (2025-10-06):
    - Removed 20 fields that don't belong to subfinder module
    - These fields will be added to future module-specific tables:
      * ip_addresses → dns_records table (DNS module)
      * status_code, response_size, technologies → http_probes table (HTTPX module)
      * ssl_* fields → ssl_certificates table (SSL scanner module)
      * cloud_provider, source_ip_range → dns_records table (DNS/cloud module)
    - Only subfinder-populated fields remain
    """
    # Core subdomain fields (from subdomains table)
    id: str
    subdomain: str
    parent_domain: str
    scan_job_id: str
    source_module: str = "subfinder"
    discovered_at: datetime
    last_checked: Optional[datetime] = None
    
    # Enhanced metadata (from joins with asset_scan_jobs and assets)
    asset_id: str
    asset_name: str
    scan_job_domain: str
    scan_job_type: str
    scan_job_status: str
    scan_job_created_at: datetime

class PaginationInfo(BaseModel):
    """Pagination metadata for efficient data loading."""
    total: int = Field(ge=0, description="Total number of records")
    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=1000, description="Records per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages")
    has_prev: bool = Field(description="Whether there are previous pages")

class SubdomainFilters(BaseModel):
    """Available filters for subdomain queries."""
    asset_id: Optional[str] = Field(None, description="Filter by specific asset")
    parent_domain: Optional[str] = Field(None, description="Filter by apex domain")
    source_module: Optional[str] = Field(None, description="Filter by discovery module")
    search: Optional[str] = Field(None, description="Search in subdomain names")

class PaginatedSubdomainResponse(BaseModel):
    """Paginated response for subdomain queries."""
    subdomains: List[SubdomainWithAssetInfo]
    pagination: PaginationInfo
    filters: SubdomainFilters
    stats: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics")

# ================================================================
# Apex Domain Pagination Schemas (NEW - for asset detail domain management)
# ================================================================

class PaginatedApexDomainResponse(BaseModel):
    """Paginated response for apex domains with metadata."""
    domains: List[ApexDomainWithStats]
    pagination: PaginationInfo
    filters: Dict[str, Optional[str]] = Field(default_factory=dict)
    stats: Dict[str, Any] = Field(default_factory=dict)

class ApexDomainFilters(BaseModel):
    """Filter options for apex domains."""
    is_active: Optional[bool] = None
    search: Optional[str] = None
