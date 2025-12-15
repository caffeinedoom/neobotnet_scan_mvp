"""
Reconnaissance API endpoints for subdomain enumeration and other recon tasks.

⚠️  DEPRECATED: All endpoints in this module are deprecated
    Use /api/v1/assets/{asset_id}/scan instead
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from ...core.dependencies import get_current_user
from ...core.environment import (
    get_current_environment,
    get_environment_capabilities,
    route_operation,
    OperationType
)
from ...schemas.auth import UserResponse
from ...schemas.recon import SubdomainScanRequest, ScanJobResponse
from ...services.recon_service import recon_service  # DIRECT import - no wrapper

# ⚠️ DEPRECATION LOGGING
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recon", 
    tags=["Reconnaissance (DEPRECATED)"],
    deprecated=True
)

@router.post("/subdomain/scan", response_model=Dict[str, Any], deprecated=True)
async def start_subdomain_scan(
    request: SubdomainScanRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    ⚠️  DEPRECATED: Individual domain scanning - UNIFIED ARCHITECTURE MIGRATION REQUIRED
    
    🚨 DEPRECATION NOTICE: This endpoint will be removed on June 1, 2025
    
    ARCHITECTURAL CHANGE: This endpoint is deprecated due to our migration to unified 
    asset-level orchestration, which eliminates the dual job tracking system and 
    provides superior reliability and performance.
    
    🏗️ UNIFIED ARCHITECTURE BENEFITS:
    • Eliminates FK constraint issues and dual job tracking complexity
    • Provides unified asset-level orchestration for better reliability
    • Enables template-based scanning for advanced automation
    • Offers up to 40% cost savings with intelligent batch processing
    • Delivers real-time WebSocket progress notifications
    • Supports advanced optimization features (cost, speed, balanced)
    
    🚀 MIGRATION PATH (Simple 3-Step Process):
    
    1. CREATE ASSET: POST /api/v1/assets
       {
         "name": "Target Asset",
         "description": "Migration from individual domain scanning"
       }
    
    2. ADD DOMAIN: POST /api/v1/assets/{asset_id}/domains  
       {
         "domain": "your-domain.com"
       }
    
    3. START UNIFIED SCAN: POST /api/v1/assets/{asset_id}/scan
       {
         "modules": ["subfinder"],
         "enable_batch_optimization": true,
         "optimization_preference": "balanced"
       }
    
    🎯 MIGRATION BENEFITS:
    • Single API call for complex multi-domain scans
    • Unified progress tracking and result aggregation
    • Template system compatibility (coming soon)
    • Improved error handling and reliability
    
    📚 MIGRATION GUIDE: See /docs/migration/individual-to-asset-level.md
    - Cross-asset optimization
    - Maximum cost savings through intelligent batching
    - Portfolio-level reconnaissance management
    
    This endpoint continues to work for backward compatibility
    but lacks advanced features and optimizations.
    """
    # 📊 DETAILED LOGGING: Track who's using this deprecated endpoint
    logger.warning(
        "⚠️  DEPRECATED ENDPOINT CALLED: /recon/subdomain/scan | "
        f"timestamp={datetime.utcnow().isoformat()} | "
        f"user_id={current_user.id} | "
        f"user_email={current_user.email} | "
        f"domain={request.domain} | "
        f"modules={[m.value for m in request.modules]} | "
        "action=DEPRECATED_SCAN_REQUEST | "
        "message=Migrate to POST /api/v1/assets/{asset_id}/scan"
    )
    
    # Add deprecation headers for API consumers
    from starlette.responses import JSONResponse
    import warnings
    
    warnings.warn(
        f"Deprecated endpoint /recon/subdomain/scan used by user {current_user.email}. "
        "Migrate to asset-based scanning for enhanced features.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Execute the scan but return with deprecation metadata
    scan_result = await recon_service.start_subdomain_scan(
        domain=request.domain,
        modules=request.modules,
        user_id=current_user.id
    )
    
    # Enhanced response with unified architecture migration guidance
    return {
        **scan_result,
        "deprecation_notice": {
            "deprecated": True,
            "removal_date": "2025-06-01",
            "migration_required": True,
            "reason": "unified_architecture_migration",
            "architecture_change": "Migrated from dual job tracking to unified asset-level orchestration",
            "modern_endpoint": "/api/v1/assets/{asset_id}/scan",
            "benefits": [
                "Eliminates FK constraint issues and dual job complexity",
                "Unified asset-level orchestration for better reliability", 
                "Template-based scanning system compatibility",
                "Up to 40% cost savings with intelligent optimization",
                "Real-time WebSocket progress notifications",
                "Advanced optimization features (cost, speed, balanced)"
            ]
        },
        "migration_guide": {
            "overview": "Simple 3-step migration to unified asset-level scanning",
            "step_1": {
                "action": "Create asset",
                "endpoint": "POST /api/v1/assets",
                "payload": {
                    "name": "Target Asset",
                    "description": "Migrated from individual domain scanning"
                }
            },
            "step_2": {
                "action": "Add domain to asset",
                "endpoint": "POST /api/v1/assets/{asset_id}/domains",
                "payload": {
                    "domain": request.domain
                }
            },
            "step_3": {
                "action": "Start unified scan",
                "endpoint": "POST /api/v1/assets/{asset_id}/scan", 
                "payload": {
                    "modules": request.modules,
                    "enable_batch_optimization": True,
                    "optimization_preference": "balanced"
                }
            },
            "documentation": "/docs/migration/individual-to-asset-level.md",
            "support": "Contact support for migration assistance"
        }
    }

@router.get("/job/{job_id}/status", deprecated=True)
async def get_job_status(
    job_id: str, 
    current_user: UserResponse = Depends(get_current_user)
):
    """
    ⚠️  DEPRECATED: Individual job status tracking - UNIFIED ARCHITECTURE MIGRATION REQUIRED
    
    🚨 This endpoint will be removed on June 1, 2025
    
    MIGRATION: Use unified asset-level tracking instead:
    GET /api/v1/assets/{asset_id}/scan/{scan_id}
    
    📚 Migration Guide: /docs/migration/individual-to-asset-level.md
    """
    # Add deprecation warning
    import warnings
    warnings.warn(
        f"Individual job status endpoint used by user {current_user.email}. "
        "Migrate to unified asset-level status tracking.",
        DeprecationWarning,
        stacklevel=2
    )
    
    result = await recon_service.get_job_status(job_id, current_user.id)
    
    # Add deprecation metadata to response
    if isinstance(result, dict):
        result["deprecation_notice"] = {
            "deprecated": True,
            "removal_date": "2025-06-01",
            "replacement": "GET /api/v1/assets/{asset_id}/scan/{scan_id}",
            "reason": "unified_architecture_migration"
        }
    
    return result

@router.get("/job/{job_id}/subdomains", deprecated=True)
async def get_enhanced_subdomains(
    job_id: str, 
    current_user: UserResponse = Depends(get_current_user)
):
    """
    ⚠️  DEPRECATED: Individual job results - UNIFIED ARCHITECTURE MIGRATION REQUIRED
    
    🚨 This endpoint will be removed on June 1, 2025
    
    MIGRATION: Use unified asset-level results instead:
    GET /api/v1/assets/{asset_id}/subdomains
    
    📚 Migration Guide: /docs/migration/individual-to-asset-level.md
    """
    # Add deprecation warning
    import warnings
    warnings.warn(
        f"Individual job results endpoint used by user {current_user.email}. "
        "Migrate to unified asset-level subdomain retrieval.",
        DeprecationWarning,
        stacklevel=2
    )
    
    result = await recon_service.get_enhanced_subdomains(job_id, current_user.id)
    
    # Add deprecation metadata to response
    if isinstance(result, list) and result:
        return {
            "subdomains": result,
            "deprecation_notice": {
                "deprecated": True,
                "removal_date": "2025-06-01",
                "replacement": "GET /api/v1/assets/{asset_id}/subdomains",
                "reason": "unified_architecture_migration"
            }
        }
    elif isinstance(result, dict):
        result["deprecation_notice"] = {
            "deprecated": True,
            "removal_date": "2025-06-01",
            "replacement": "GET /api/v1/assets/{asset_id}/subdomains",
            "reason": "unified_architecture_migration"
        }
    
    return result

@router.get("/job/{job_id}/progress", deprecated=True)
async def get_job_progress(
    job_id: str, 
    current_user: UserResponse = Depends(get_current_user)
):
    """
    ⚠️  DEPRECATED: Individual job progress - UNIFIED ARCHITECTURE MIGRATION REQUIRED
    🚨 Removed June 1, 2025 | Use: GET /api/v1/assets/{asset_id}/scan/{scan_id}
    """
    import warnings
    warnings.warn("Individual job progress endpoint deprecated. Use unified asset-level tracking.", DeprecationWarning)
    
    result = await recon_service.get_job_progress(job_id, current_user.id)
    if isinstance(result, dict):
        result["deprecation_notice"] = {"deprecated": True, "removal_date": "2025-06-01", "replacement": "GET /api/v1/assets/{asset_id}/scan/{scan_id}"}
    return result

@router.get("/job/{job_id}/errors", deprecated=True)
async def get_job_errors(
    job_id: str, 
    current_user: UserResponse = Depends(get_current_user)
):
    """
    ⚠️  DEPRECATED: Individual job errors - UNIFIED ARCHITECTURE MIGRATION REQUIRED
    🚨 Removed June 1, 2025 | Use: GET /api/v1/assets/{asset_id}/scan/{scan_id}
    """
    import warnings
    warnings.warn("Individual job errors endpoint deprecated. Use unified asset-level error tracking.", DeprecationWarning)
    
    result = await recon_service.get_job_errors(job_id, current_user.id)
    if isinstance(result, dict):
        result["deprecation_notice"] = {"deprecated": True, "removal_date": "2025-06-01", "replacement": "GET /api/v1/assets/{asset_id}/scan/{scan_id}"}
    return result

@router.get("/job/{job_id}/stream", deprecated=True)
async def stream_job_progress(
    job_id: str, 
    current_user: UserResponse = Depends(get_current_user)
):
    """
    ⚠️  DEPRECATED: Individual job streaming - UNIFIED ARCHITECTURE MIGRATION REQUIRED  
    🚨 Removed June 1, 2025 | Use: WebSocket /api/v1/ws/batch-progress for real-time updates
    """
    import warnings
    warnings.warn("Individual job streaming deprecated. Use unified WebSocket notifications.", DeprecationWarning)
    
    return await recon_service.stream_job_progress(job_id, current_user.id)

@router.get("/jobs", deprecated=True)
async def list_jobs(
    current_user: UserResponse = Depends(get_current_user),
    limit: int = 10
):
    """
    ⚠️  DEPRECATED: Individual job listing - UNIFIED ARCHITECTURE MIGRATION REQUIRED
    🚨 Removed June 1, 2025 | Use: GET /api/v1/assets to list asset-level scans  
    """
    import warnings  
    warnings.warn("Individual jobs listing deprecated. Use unified asset-level scan listing.", DeprecationWarning)
    
    result = await recon_service.list_jobs(current_user.id, limit)
    if isinstance(result, list):
        return {
            "jobs": result,
            "deprecation_notice": {
                "deprecated": True,
                "removal_date": "2025-06-01", 
                "replacement": "GET /api/v1/assets",
                "reason": "unified_architecture_migration"
            }
        }
    return result

# ============================================================================
# CLEANUP NOTE (2025-10-06): Removed deprecated cloud_ssl sync endpoint
# ============================================================================
# Removed: POST /job/{job_id}/sync - sync_redis_to_database()
# This endpoint was deprecated and called the removed cloud_ssl sync methods.
# Subfinder uses direct-to-database writes from Go containers (no sync needed).
# ============================================================================

# ================================================================
# Environment Diagnostics and Monitoring Endpoints
# ================================================================

@router.get("/environment", response_model=Dict[str, Any])
async def get_environment_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current environment information and capabilities.
    Useful for debugging and understanding routing decisions.
    """
    environment = await get_current_environment()
    capabilities = await get_environment_capabilities()
    
    return {
        "environment": environment,
        "capabilities": {
            "has_ecs": capabilities.has_ecs,
            "has_local_containers": capabilities.has_local_containers,
            "has_redis": capabilities.has_redis,
            "has_database": capabilities.has_database,
            "can_scan": capabilities.can_scan,
            "preferred_for_scans": capabilities.preferred_for_scans,
        },
        "user_id": current_user.id,
        "timestamp": "now"
    }

@router.get("/environment/routing/{operation_type}", response_model=Dict[str, Any])
async def get_operation_routing(
    operation_type: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get routing configuration for a specific operation type.
    Useful for understanding how operations will be executed.
    """
    try:
        # Convert string to enum
        operation_enum = OperationType(operation_type)
        routing_config = await route_operation(operation_enum)
        
        return {
            "operation_type": operation_type,
            "routing_config": routing_config,
            "user_id": current_user.id,
            "timestamp": "now"
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operation type. Valid types: {[op.value for op in OperationType]}"
        )

@router.get("/environment/scan-routing", response_model=Dict[str, Any])
async def get_scan_routing_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get detailed scan routing information.
    Shows exactly how scan operations will be executed in current environment.
    """
    routing_config = await route_operation(OperationType.SCAN_OPERATION)
    
    # Add additional scan-specific information
    scan_info = {
        "routing_config": routing_config,
        "execution_options": {
            "cloud_ecs": {
                "available": routing_config["capabilities"].has_ecs,
                "preferred": routing_config["execution_strategy"] == "cloud_ecs",
                "description": "AWS ECS Fargate containers for production scanning"
            },
            "local_containers": {
                "available": routing_config["capabilities"].has_local_containers,
                "preferred": routing_config["execution_strategy"] == "local_containers",
                "description": "Local Docker containers for development scanning"
            },
            "mock": {
                "available": True,
                "preferred": routing_config["execution_strategy"] == "mock",
                "description": "Mock data for development when no scan infrastructure available"
            }
        },
        "notifications": routing_config.get("notifications", []),
        "recommendations": []
    }
    
    # Add recommendations based on current setup
    if not routing_config["capabilities"].has_ecs and not routing_config["capabilities"].has_local_containers:
        scan_info["recommendations"].append(
            "No scan infrastructure detected. Consider setting up local containers for development."
        )
    elif routing_config["capabilities"].has_local_containers and not routing_config["capabilities"].has_ecs:
        scan_info["recommendations"].append(
            "Local container scanning available. Deploy to cloud for production-grade scanning."
        )
    elif routing_config["capabilities"].has_ecs:
        scan_info["recommendations"].append(
            "Cloud ECS scanning available. Optimal setup for production workloads."
        )
    
    return scan_info

@router.get("/health")
async def health_check():
    """Health check for reconnaissance service with environment capabilities."""
    environment = await get_current_environment()
    capabilities = await get_environment_capabilities()
    
    # Determine overall health based on capabilities
    if capabilities.can_scan:
        health_status = "healthy"
        message = f"Reconnaissance service operational in {environment} environment"
    elif capabilities.has_redis and capabilities.has_database:
        health_status = "degraded"
        message = f"Service operational but no scan capability in {environment} environment"
    else:
        health_status = "unhealthy"
        message = f"Service issues detected in {environment} environment"
    
    return {
        "status": health_status,
        "service": "reconnaissance",
        "environment": environment,
        "message": message,
        "capabilities": {
            "scan_available": capabilities.can_scan,
            "redis_available": capabilities.has_redis,
            "database_available": capabilities.has_database,
            "ecs_available": capabilities.has_ecs,
            "local_containers_available": capabilities.has_local_containers,
        },
        "scan_preference": "cloud_ecs" if capabilities.preferred_for_scans and capabilities.has_ecs else 
                          "local_containers" if capabilities.has_local_containers else "mock"
    } 