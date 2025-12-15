"""
Unified Scans API

This module provides a single, unified REST API endpoint for scanning operations.
It replaces the previous duplicate endpoints and provides consistent behavior for
single and multi-asset scans.

Endpoints:
- POST   /api/v1/scans            - Start scan (1-N assets)
- GET    /api/v1/scans/{scan_id}  - Get scan status
- GET    /api/v1/scans            - List user's scans

Replaces:
- POST /api/v1/assets/{asset_id}/scan
- POST /api/v1/batch/multi-asset/scan

Author: Development Team
Date: 2025-11-10
"""

import logging
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from ...core.dependencies import get_current_user
from ...schemas.auth import UserResponse
from ...schemas.assets import EnhancedAssetScanRequest
from ...services.scan_orchestrator import scan_orchestrator


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scans", tags=["scans"])


# ============================================================
# Request/Response Models
# ============================================================

class UnifiedScanRequest(BaseModel):
    """
    Unified scan request for one or more assets.
    
    Example (Single Asset):
    {
        "assets": {
            "asset-uuid-1": {
                "modules": ["subfinder", "dnsx"],
                "active_domains_only": true
            }
        }
    }
    
    Example (Multi-Asset):
    {
        "assets": {
            "asset-uuid-1": {"modules": ["subfinder", "dnsx"]},
            "asset-uuid-2": {"modules": ["httpx"]},
            "asset-uuid-3": {"modules": ["subfinder", "dnsx"]}
        }
    }
    """
    assets: Dict[str, EnhancedAssetScanRequest] = Field(
        ...,
        description="Dictionary mapping asset IDs to scan configurations",
        min_items=1
    )


class ScanResponse(BaseModel):
    """Response for scan initiation."""
    scan_id: str = Field(..., description="Unique scan identifier for polling")
    status: str = Field(..., description="Scan status: pending, running, completed, failed")
    assets_count: int = Field(..., description="Number of assets being scanned")
    total_domains: int = Field(..., description="Total domains across all assets")
    execution_mode: str = Field(..., description="Pipeline execution mode: streaming (default)")
    polling_url: str = Field(..., description="URL to poll for scan status")
    estimated_duration_minutes: int = Field(..., description="Estimated scan duration")
    created_at: str = Field(..., description="Scan creation timestamp (ISO 8601)")


class ScanStatusResponse(BaseModel):
    """Response for scan status query."""
    id: str
    user_id: str
    status: str
    assets_count: int
    total_domains: int
    completed_assets: int
    failed_assets: int
    completed_domains: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    config: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ScanListResponse(BaseModel):
    """Response for scan list query."""
    scans: List[ScanStatusResponse]
    total: int
    limit: int
    offset: int


# ============================================================
# Endpoints
# ============================================================

@router.post("", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(
    request: UnifiedScanRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Start a scan for one or more assets.
    
    This unified endpoint replaces the previous separate endpoints for single
    and multi-asset scans. It provides consistent behavior and automatic
    optimization regardless of the number of assets.
    
    Features:
    - Handles 1 to N assets in a single request
    - Auto-detects streaming capability per asset
    - Launches pipelines in parallel for maximum performance
    - Returns immediately (< 1 second) to prevent timeouts
    - Provides polling URL for status updates
    
    Single Asset Example:
    ```json
    {
        "assets": {
            "asset-uuid": {
                "modules": ["subfinder", "dnsx"],
                "active_domains_only": true
            }
        }
    }
    ```
    
    Multi-Asset Example:
    ```json
    {
        "assets": {
            "asset-1": {"modules": ["subfinder", "dnsx"]},
            "asset-2": {"modules": ["httpx"]},
            "asset-3": {"modules": ["subfinder", "dnsx"]}
        }
    }
    ```
    
    Args:
        request: Unified scan request with asset configurations
        current_user: Authenticated user (from JWT token)
        
    Returns:
        ScanResponse with scan_id and polling information
        
    Raises:
        400: Invalid request (no assets, invalid modules)
        401: Unauthorized (invalid/missing token)
        404: Asset not found or access denied
        500: Internal server error
    """
    try:
        # ============================================================
        # Redis Health Check (Streaming Architecture Requirement)
        # ============================================================
        try:
            import redis.asyncio as redis
            from app.core.config import settings
            
            redis_client = redis.from_url(settings.redis_url, socket_timeout=5)
            await redis_client.ping()
            await redis_client.close()
        except Exception as e:
            logger.error(f"Redis unavailable: {e}")
            raise HTTPException(
                status_code=503,
                detail="Scan engine temporarily unavailable. Redis connection required for streaming architecture. Please try again in a moment."
            )
        
        # Log incoming request with user context
        logger.info(
            f"📥 API REQUEST | endpoint=POST /api/v1/scans | "
            f"user={str(current_user.id)[:8]}... | "
            f"assets={len(request.assets)} | "
            f"action=scan_initiation"
        )
        
        # Delegate to orchestrator
        result = await scan_orchestrator.execute_scan(
            asset_configs=request.assets,
            user_id=current_user.id
        )
        
        # Extract correlation ID for consistent logging
        correlation_id = str(result['scan_id'])[:8]
        
        logger.info(
            f"[{correlation_id}] ✅ API RESPONSE | "
            f"scan_id={result['scan_id']} | "
            f"assets={result['assets_count']} | "
            f"domains={result['total_domains']} | "
            f"status={result['status']} | "
            f"http_status=202"
        )
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions from orchestrator
        raise
    except Exception as e:
        logger.error(
            f"❌ API ERROR | endpoint=POST /api/v1/scans | "
            f"user={str(current_user.id)[:8]}... | "
            f"error={str(e)} | "
            f"http_status=500",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate scan: {str(e)}"
        )


@router.get("/{scan_id}", response_model=ScanStatusResponse)
async def get_scan_status(
    scan_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get scan status and progress.
    
    Poll this endpoint to monitor scan progress. The scan goes through these states:
    - pending: Scan created, not yet started
    - running: Scan in progress
    - completed: Scan finished successfully
    - partial_failure: Some assets failed, some succeeded
    - failed: Scan failed completely
    
    Example Response:
    ```json
    {
        "id": "scan-uuid",
        "status": "running",
        "assets_count": 3,
        "completed_assets": 1,
        "failed_assets": 0,
        "total_domains": 150,
        "completed_domains": 50,
        "created_at": "2025-11-10T12:00:00Z",
        "started_at": "2025-11-10T12:00:01Z"
    }
    ```
    
    Args:
        scan_id: Scan UUID to query
        current_user: Authenticated user (from JWT token)
        
    Returns:
        ScanStatusResponse with current scan state
        
    Raises:
        401: Unauthorized
        404: Scan not found or access denied
        500: Internal server error
    """
    try:
        result = await scan_orchestrator.get_scan_status(
            scan_id=scan_id,
            user_id=current_user.id
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        correlation_id = str(scan_id)[:8]
        logger.error(
            f"[{correlation_id}] ❌ API ERROR | endpoint=GET /api/v1/scans/{{scan_id}} | "
            f"scan_id={scan_id} | "
            f"user={str(current_user.id)[:8]}... | "
            f"error={str(e)} | "
            f"http_status=500"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scan status: {str(e)}"
        )


@router.get("", response_model=ScanListResponse)
async def list_scans(
    status_filter: Optional[str] = Query(
        None,
        description="Filter by status: pending, running, completed, failed"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum scans to return"),
    offset: int = Query(0, ge=0, description="Number of scans to skip"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    List user's scans with filtering and pagination.
    
    Returns a paginated list of scans for the authenticated user. Useful for
    displaying scan history in the UI.
    
    Query Parameters:
    - status: Filter by status (optional)
    - limit: Max results (1-100, default 50)
    - offset: Skip N results (default 0)
    
    Example:
    ```
    GET /api/v1/scans?status=running&limit=20&offset=0
    ```
    
    Args:
        status_filter: Optional status filter
        limit: Maximum scans to return (1-100)
        offset: Number of scans to skip for pagination
        current_user: Authenticated user (from JWT token)
        
    Returns:
        ScanListResponse with paginated scan list
        
    Raises:
        401: Unauthorized
        500: Internal server error
    """
    try:
        from ...core.supabase_client import supabase_client
        supabase = supabase_client.service_client
        
        # Build query
        query = supabase.table("scans").select(
            "*", count="exact"
        ).eq("user_id", current_user.id).order("created_at", desc=True)
        
        # Apply status filter if provided
        if status_filter:
            query = query.eq("status", status_filter)
        
        # Get total count
        count_response = supabase.table("scans").select(
            "id", count="exact"
        ).eq("user_id", current_user.id)
        
        if status_filter:
            count_response = count_response.eq("status", status_filter)
        
        count_result = count_response.execute()
        total_count = count_result.count or 0
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        
        scans = response.data or []
        
        logger.info(
            f"📋 API REQUEST | endpoint=GET /api/v1/scans | "
            f"user={str(current_user.id)[:8]}... | "
            f"results={len(scans)} | "
            f"total={total_count} | "
            f"limit={limit} | "
            f"offset={offset} | "
            f"http_status=200"
        )
        
        return {
            "scans": scans,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(
            f"❌ API ERROR | endpoint=GET /api/v1/scans | "
            f"user={str(current_user.id)[:8]}... | "
            f"error={str(e)} | "
            f"http_status=500"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scans: {str(e)}"
        )
