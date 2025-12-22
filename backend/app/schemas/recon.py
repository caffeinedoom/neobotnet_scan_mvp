"""
Pydantic schemas for reconnaissance operations.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class ReconModule(str, Enum):
    """
    Available reconnaissance modules.
    
    CLEANUP NOTE (2025-10-06):
    - Removed CLOUD_SSL (not implemented, won't be for a while)
    - Future modules commented out until implemented
    
    UPDATE (2025-10-28):
    - Added DNSX for DNS resolution (Phase 3 of DNS module implementation)
    
    UPDATE (2025-11-14):
    - Added HTTPX for HTTP probing of discovered subdomains
    
    UPDATE (2025-12-17):
    - Added KATANA for web crawling discovered HTTP endpoints
    
    UPDATE (2025-12-22):
    - Added URL_RESOLVER for probing and enriching discovered URLs
    """
    SUBFINDER = "subfinder"
    DNSX = "dnsx"  # DNS resolution for discovered subdomains
    HTTPX = "httpx"  # HTTP probing for discovered subdomains
    KATANA = "katana"  # Web crawling for discovered HTTP endpoints
    URL_RESOLVER = "url-resolver"  # URL probing and enrichment
    
    # Future modules (uncomment when implemented):
    # DNS_BRUTEFORCE = "dns_bruteforce"
    # PORT_SCAN = "port_scan"

class SubdomainScanRequest(BaseModel):
    """Enhanced request supporting multiple reconnaissance modules."""
    domain: str = Field(..., description="Domain to scan for subdomains")
    modules: List[ReconModule] = Field(
        default=[ReconModule.SUBFINDER], 
        description="Reconnaissance modules to execute"
    )
    
    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Domain cannot be empty')
        if len(v) > 253:
            raise ValueError('Domain too long')
        # Basic domain validation
        import re
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        if not re.match(pattern, v.strip()):
            raise ValueError('Invalid domain format')
        return v.strip().lower()

    @field_validator('modules')
    @classmethod
    def validate_modules(cls, v):
        if not v or len(v) == 0:
            return [ReconModule.SUBFINDER]  # Default to subfinder
        if len(v) > 5:  # Prevent resource exhaustion
            raise ValueError('Maximum 5 modules per scan')
        return list(set(v))  # Remove duplicates

class ScanJobResponse(BaseModel):
    """Enhanced response with multi-module support."""
    job_id: str = Field(..., description="Unique job identifier")
    domain: str = Field(..., description="Domain being scanned")
    modules: Optional[List[str]] = Field(default=[], description="Requested reconnaissance modules")
    status: str = Field(..., description="Job status (pending, running, completed, failed)")
    created_at: str = Field(..., description="Job creation timestamp")
    total_subdomains: int = Field(default=0, description="Number of unique subdomains found")
    subdomains: Optional[List[str]] = Field(default=[], description="List of discovered subdomains")
    module_status: Optional[Dict[str, str]] = Field(default={}, description="Status of each module")
    module_results: Optional[Dict[str, Dict[str, Any]]] = Field(default={}, description="Results by module")
    message: Optional[str] = Field(None, description="Status message")
    
    @field_validator('modules', mode='before')
    @classmethod
    def validate_modules(cls, v):
        """Convert None to empty list for backward compatibility with legacy data."""
        if v is None:
            return []
        return v
    
    @field_validator('subdomains', mode='before')
    @classmethod
    def validate_subdomains(cls, v):
        """Convert None to empty list for backward compatibility with legacy data."""
        if v is None:
            return []
        return v
    
    @field_validator('module_status', mode='before')
    @classmethod
    def validate_module_status(cls, v):
        """Convert None to empty dict for backward compatibility with legacy data."""
        if v is None:
            return {}
        return v
    
    @field_validator('module_results', mode='before')
    @classmethod
    def validate_module_results(cls, v):
        """Convert None to empty dict for backward compatibility with legacy data."""
        if v is None:
            return {}
        return v

class SubdomainResult(BaseModel):
    """
    Subdomain result from scan workflow.
    
    NOTE: This is an intermediate result model used by scan containers.
    The ip_addresses field is kept for backward compatibility with existing
    scan containers but will be empty for subfinder (passive enumeration).
    Future DNS modules will populate this field when resolving IPs.
    """
    subdomain: str = Field(..., description="Discovered subdomain")
    ip_addresses: Optional[List[str]] = Field(
        default=[], 
        description="Associated IP addresses (empty for subfinder, populated by DNS module)"
    )
    source_module: str = Field(..., description="Module that discovered this subdomain")
    discovered_at: str = Field(..., description="Discovery timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")

class WorkflowStatus(BaseModel):
    """Workflow orchestration status."""
    job_id: str = Field(..., description="Job identifier")
    domain: str = Field(..., description="Target domain")
    total_modules: int = Field(..., description="Total number of modules")
    completed_modules: int = Field(default=0, description="Number of completed modules")
    running_modules: List[str] = Field(default=[], description="Currently running modules")
    failed_modules: List[str] = Field(default=[], description="Failed modules")
    overall_status: str = Field(..., description="Overall workflow status")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time") 