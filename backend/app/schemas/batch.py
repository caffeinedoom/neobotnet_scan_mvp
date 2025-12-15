"""
Batch Processing Schemas for Reconnaissance Scans
================================================

Data structures for intelligent batch processing, resource allocation,
and cross-asset scan optimization.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid

class BatchType(str, Enum):
    """Type of batch processing."""
    MULTI_ASSET = "multi_asset"  # Domains from multiple assets
    SINGLE_ASSET = "single_asset"  # Domains from single asset

class BatchStatus(str, Enum):
    """Status of batch scan job."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DomainAssignmentStatus(str, Enum):
    """Status of individual domain within a batch."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class BatchErrorType(str, Enum):
    """Types of batch processing errors for better classification."""
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    ECS_FAILURE = "ecs_failure"
    NETWORK_ERROR = "network_error"
    INVALID_CONFIGURATION = "invalid_configuration"

class BatchExecutionError(BaseModel):
    """Enhanced error information for batch operations."""
    error_type: BatchErrorType
    error_message: str
    batch_id: uuid.UUID
    recoverable: bool = False
    retry_suggested: bool = False
    estimated_fix_time: Optional[int] = None  # minutes
    
    class Config:
        use_enum_values = True

# ================================================================
# Resource Allocation Schemas
# ================================================================

class ResourceProfile(BaseModel):
    """Resource allocation profile for a batch."""
    cpu: int = Field(..., ge=256, le=4096, description="CPU units (256 = 0.25 vCPU)")
    memory: int = Field(..., ge=512, le=8192, description="Memory in MB")
    estimated_duration_minutes: int = Field(..., gt=0, description="Estimated completion time")
    description: str = Field(..., description="Resource allocation reasoning")
    domain_count: int = Field(..., gt=0, description="Number of domains in batch")
    module_name: str = Field(..., description="Scan module name")

class ResourceRange(BaseModel):
    """Resource range definition for module scaling."""
    min_domains: int = Field(..., ge=1)
    max_domains: int = Field(..., ge=1) 
    cpu: int = Field(..., ge=256, le=4096)
    memory: int = Field(..., ge=512, le=8192)
    description: str

    @validator('max_domains')
    def max_greater_than_min(cls, v, values):
        if 'min_domains' in values and v < values['min_domains']:
            raise ValueError('max_domains must be >= min_domains')
        return v

class ModuleResourceScaling(BaseModel):
    """Complete resource scaling configuration for a module."""
    domain_count_ranges: List[ResourceRange]
    scaling_notes: str

class ModuleProfile(BaseModel):
    """Complete module profile with capabilities and scaling."""
    id: uuid.UUID
    module_name: str
    version: str = "1.0"
    supports_batching: bool = False
    max_batch_size: int = Field(default=1, ge=1)
    resource_scaling: ModuleResourceScaling
    estimated_duration_per_domain: int = Field(..., gt=0, description="Seconds per domain")
    task_definition_template: str
    container_name: str
    optimization_hints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Module-specific optimization configuration (memory multipliers, role ARNs, etc.)"
    )
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

# ================================================================
# Batch Job Schemas  
# ================================================================

class BatchDomainAssignment(BaseModel):
    """Individual domain assignment within a batch."""
    id: uuid.UUID
    batch_scan_id: uuid.UUID
    domain: str = Field(..., min_length=3, max_length=253)
    asset_scan_id: uuid.UUID  # Links back to original asset scan
    apex_domain_id: Optional[uuid.UUID] = None
    status: DomainAssignmentStatus = DomainAssignmentStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    subdomains_found: int = Field(default=0, ge=0)
    error_message: Optional[str] = None

class BatchScanJob(BaseModel):
    """Batch scan job containing multiple domains."""
    id: uuid.UUID
    user_id: uuid.UUID
    batch_type: BatchType = BatchType.MULTI_ASSET
    module: str = Field(..., description="Single module per batch")
    status: BatchStatus = BatchStatus.PENDING
    
    # Domain and Asset Tracking
    total_domains: int = Field(default=0, ge=0)
    completed_domains: int = Field(default=0, ge=0)
    failed_domains: int = Field(default=0, ge=0)
    batch_domains: List[str] = Field(default_factory=list)
    asset_scan_mapping: Dict[str, str] = Field(default_factory=dict, description="domain -> asset_scan_id")
    
    # Resource Allocation
    allocated_cpu: int = Field(default=256, ge=256, le=4096)
    allocated_memory: int = Field(default=512, ge=512, le=8192)
    estimated_duration_minutes: int = Field(default=5, gt=0)
    resource_profile: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    # Error Handling and Metadata
    error_message: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=2, ge=0)
    ecs_task_arn: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('completed_domains', 'failed_domains')
    def validate_domain_counts(cls, v, values):
        if 'total_domains' in values:
            total = values['total_domains']
            if v > total:
                raise ValueError('completed/failed domains cannot exceed total')
        return v

    @validator('retry_count')
    def validate_retry_count(cls, v, values):
        if 'max_retries' in values and v > values['max_retries']:
            raise ValueError('retry_count cannot exceed max_retries')
        return v

# ================================================================
# Batch Creation Requests
# ================================================================

class BatchOptimizationRequest(BaseModel):
    """Request for batch optimization across multiple asset scans."""
    asset_scan_requests: List[Dict[str, Any]] = Field(..., min_items=1, description="List of asset scan requests")
    modules: List[str] = Field(..., min_items=1, description="Modules to run")
    priority: int = Field(default=1, ge=1, le=5, description="Priority level (1=highest)")
    user_id: uuid.UUID
    
    class Config:
        schema_extra = {
            "example": {
                "asset_scan_requests": [
                    {
                        "asset_id": "123e4567-e89b-12d3-a456-426614174000",
                        "domains": ["example.com", "test.com"],
                        "asset_scan_id": "123e4567-e89b-12d3-a456-426614174001"
                    }
                ],
                "modules": ["subfinder"],
                "priority": 1,
                "user_id": "123e4567-e89b-12d3-a456-426614174002"
            }
        }

class BatchOptimizationResult(BaseModel):
    """Result of batch optimization process."""
    total_domains: int
    total_batches: int
    estimated_cost_savings_percent: float = Field(..., description="Estimated cost savings vs individual scans")
    estimated_duration_minutes: int
    batch_jobs: List[BatchScanJob]
    optimization_strategy: str = Field(..., description="Description of optimization strategy used")
    
    class Config:
        schema_extra = {
            "example": {
                "total_domains": 600,
                "total_batches": 3,
                "estimated_cost_savings_percent": 45.5,
                "estimated_duration_minutes": 25,
                "batch_jobs": [],
                "optimization_strategy": "Cross-asset batching with 200 domains per batch for optimal resource utilization"
            }
        }

# ================================================================
# Response Schemas
# ================================================================

class BatchScanResponse(BaseModel):
    """Response for batch scan creation."""
    batch_id: uuid.UUID
    total_domains: int
    estimated_duration_minutes: int
    allocated_resources: ResourceProfile
    status: BatchStatus
    created_at: datetime

class BatchProgressResponse(BaseModel):
    """Progress response for batch scan."""
    batch_id: uuid.UUID
    status: BatchStatus
    progress_percentage: float = Field(..., ge=0.0, le=100.0)
    completed_domains: int
    failed_domains: int
    total_domains: int
    estimated_completion: Optional[datetime] = None
    current_phase: str = Field(default="scanning", description="Current processing phase")
    ecs_task_arn: Optional[str] = None
