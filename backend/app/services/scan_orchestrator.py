"""
Unified Scan Orchestrator

This module provides a single, unified interface for coordinating scans across
one or more assets. It replaces the duplicated scan coordination logic that
previously existed in asset_service.py.

Architecture:
- Accepts 1-N assets in a single request
- Auto-detects streaming capability per asset
- Launches pipelines in parallel for maximum performance
- Runs in background to prevent API timeouts
- Provides comprehensive logging with correlation IDs

Replaces:
- asset_service.start_asset_scan()
- asset_service.start_multi_asset_optimization()

Author: Development Team
Date: 2025-11-10
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import HTTPException, status

from ..schemas.assets import EnhancedAssetScanRequest
from ..core.supabase_client import supabase_client
from .scan_pipeline import scan_pipeline


logger = logging.getLogger(__name__)


class ScanOrchestrator:
    """
    Unified scan orchestration for single and multi-asset scans.
    
    This orchestrator provides a single source of truth for all scan coordination,
    ensuring consistent behavior whether scanning 1 or 100 assets.
    
    Features:
    - Automatic streaming detection per asset
    - Parallel pipeline execution
    - Background execution (non-blocking)
    - Comprehensive correlation ID logging
    - Progress tracking
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supabase = supabase_client.service_client
    
    async def execute_scan(
        self,
        asset_configs: Dict[str, EnhancedAssetScanRequest],
        user_id: str,
        scan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute scan for one or more assets with automatic optimization.
        
        This is the main entry point for ALL scan operations. It handles:
        - Single asset scans (1 asset)
        - Multi-asset scans (2+ assets)
        - Streaming detection per asset
        - Parallel pipeline execution
        - Background execution
        
        Args:
            asset_configs: Dict mapping asset_id to EnhancedAssetScanRequest
                Example: {
                    "asset-uuid-1": {
                        "modules": ["subfinder", "dnsx"],
                        "active_domains_only": True
                    },
                    "asset-uuid-2": {
                        "modules": ["httpx"]
                    }
                }
            user_id: User UUID for authentication
            scan_id: Optional scan ID (auto-generated if not provided)
            
        Returns:
            Dict with scan information:
            {
                "scan_id": "uuid",
                "status": "pending",
                "assets_count": 2,
                "total_domains": 150,
                "polling_url": "/api/v1/scans/{scan_id}",
                "estimated_duration_minutes": 6,
                "created_at": "2025-11-10T12:00:00Z"
            }
            
        Raises:
            HTTPException: 404 if asset not found
            HTTPException: 403 if user doesn't have access
            HTTPException: 400 if invalid configuration
        """
        # Generate scan ID if not provided
        if not scan_id:
            scan_id = str(uuid.uuid4())
        
        correlation_id = scan_id[:8]
        assets_count = len(asset_configs)
        
        # Entry logging
        self.logger.info(f"[{correlation_id}] 🎬 SCAN START")
        self.logger.info(f"[{correlation_id}] └─ Assets: {assets_count}")
        self.logger.info(f"[{correlation_id}] └─ User: {user_id}")
        self.logger.info(f"[{correlation_id}] └─ Timestamp: {datetime.utcnow().isoformat()}")
        
        start_time = datetime.utcnow()
        
        try:
            # ============================================================
            # PHASE 1: Validate and Prepare Assets
            # ============================================================
            self.logger.info(f"[{correlation_id}] 📦 PHASE 1: Validation & Preparation")
            
            prepared_assets = await self._validate_and_prepare_assets(
                asset_configs=asset_configs,
                user_id=user_id,
                correlation_id=correlation_id
            )
            
            total_domains = sum(asset["domains_count"] for asset in prepared_assets.values())
            
            self.logger.info(f"[{correlation_id}] └─ Validated {assets_count} assets")
            self.logger.info(f"[{correlation_id}] └─ Total domains: {total_domains}")
            
            # ============================================================
            # PHASE 2: Create Scan Record
            # ============================================================
            self.logger.info(f"[{correlation_id}] 📝 PHASE 2: Creating scan record")
            
            scan_record = await self._create_scan_record(
                scan_id=scan_id,
                user_id=user_id,
                asset_configs=asset_configs,
                prepared_assets=prepared_assets,
                total_domains=total_domains
            )
            
            self.logger.info(f"[{correlation_id}] └─ Scan record created: {scan_id}")
            
            # ============================================================
            # PHASE 3: Launch Background Execution
            # ============================================================
            self.logger.info(f"[{correlation_id}] 🚀 PHASE 3: Launching background execution")
            
            # Launch background task (non-blocking)
            asyncio.create_task(
                self._execute_scan_background(
                    scan_id=scan_id,
                    prepared_assets=prepared_assets,
                    user_id=user_id,
                    correlation_id=correlation_id
                )
            )
            
            self.logger.info(f"[{correlation_id}] └─ Background task launched")
            
            # ============================================================
            # PHASE 4: Return Immediately
            # ============================================================
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.logger.info(f"[{correlation_id}] ✅ SCAN INITIATED: {duration_ms:.0f}ms")
            self.logger.info(f"[{correlation_id}] └─ Returning to client immediately")
            
            # Calculate estimated duration
            # Streaming-only architecture: ~3 minutes per asset (parallel execution)
            estimated_minutes = assets_count * 3
            
            return {
                "scan_id": scan_id,
                "status": "pending",
                "assets_count": assets_count,
                "total_domains": total_domains,
                "execution_mode": "streaming",
                "polling_url": f"/api/v1/scans/{scan_id}",
                "estimated_duration_minutes": estimated_minutes,
                "created_at": scan_record["created_at"]
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            self.logger.error(
                f"[{correlation_id}] ❌ SCAN INITIATION FAILED: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate scan: {str(e)}"
            )
    
    async def _validate_and_prepare_assets(
        self,
        asset_configs: Dict[str, EnhancedAssetScanRequest],
        user_id: str,
        correlation_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Validate all assets and prepare scan configuration.
        
        Args:
            asset_configs: Asset scan configurations
            user_id: User UUID
            correlation_id: Logging correlation ID
            
        Returns:
            Dict mapping asset_id to prepared configuration:
            {
                "asset-uuid-1": {
                    "asset_id": "asset-uuid-1",
                    "asset_name": "EpicGames",
                    "modules": ["subfinder", "dnsx"],
                    "domains": ["epicgames.com", "unrealengine.com"],
                    "domains_count": 2,
                    "is_streaming": True,
                    "config": EnhancedAssetScanRequest(...)
                }
            }
            
        Raises:
            HTTPException: If asset not found or user has no access
        """
        prepared = {}
        
        for asset_id, config in asset_configs.items():
            self.logger.info(f"[{correlation_id}] 🔍 Validating asset: {asset_id}")
            
            # Fetch asset from database
            asset_response = self.supabase.table("assets").select(
                "id, name, user_id"
            ).eq("id", asset_id).eq("user_id", user_id).execute()
            
            if not asset_response.data:
                self.logger.error(f"[{correlation_id}] ❌ Asset not found: {asset_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Asset {asset_id} not found or access denied"
                )
            
            asset = asset_response.data[0]
            asset_name = asset["name"]
            
            # Fetch domains for asset
            domains_query = self.supabase.table("apex_domains").select(
                "id, domain, is_active"
            ).eq("asset_id", asset_id)
            
            # Filter by active status if requested
            if config.active_domains_only:
                domains_query = domains_query.eq("is_active", True)
            
            domains_response = domains_query.execute()
            
            if not domains_response.data:
                self.logger.warning(
                    f"[{correlation_id}] ⚠️  Asset {asset_name} has no domains, skipping"
                )
                continue
            
            domains = [d["domain"] for d in domains_response.data]
            domains_count = len(domains)
            
            # Prepare modules (streaming-only architecture)
            modules = [m.value if hasattr(m, 'value') else m for m in config.modules]
            
            self.logger.info(f"[{correlation_id}] └─ {asset_name}: {domains_count} domains")
            self.logger.info(f"[{correlation_id}] └─ Modules: {modules}")
            self.logger.info(f"[{correlation_id}] └─ Mode: 🌊 Streaming (parallel execution)")
            
            prepared[asset_id] = {
                "asset_id": asset_id,
                "asset_name": asset_name,
                "modules": modules,
                "domains": domains,
                "domains_count": domains_count,
                "config": config
            }
        
        if not prepared:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid domains found across specified assets"
            )
        
        return prepared
    
    async def _create_scan_record(
        self,
        scan_id: str,
        user_id: str,
        asset_configs: Dict[str, EnhancedAssetScanRequest],
        prepared_assets: Dict[str, Dict[str, Any]],
        total_domains: int
    ) -> Dict[str, Any]:
        """
        Create scan record in database.
        
        Args:
            scan_id: Scan UUID
            user_id: User UUID
            asset_configs: Original asset configurations
            prepared_assets: Prepared asset data
            total_domains: Total domain count across all assets
            
        Returns:
            Created scan record
        """
        scan_record = {
            "id": scan_id,
            "user_id": user_id,
            "status": "pending",
            "assets_count": len(prepared_assets),
            "total_domains": total_domains,
            "completed_assets": 0,
            "failed_assets": 0,
            "completed_domains": 0,
            "config": {
                "assets": {
                    asset_id: {
                        "modules": config.modules if hasattr(config.modules[0], 'value') else config.modules,
                        "active_domains_only": config.active_domains_only,
                        "priority": config.priority if hasattr(config, 'priority') else 3
                    }
                    for asset_id, config in asset_configs.items()
                }
            },
            "metadata": {
                "execution_mode": "streaming",
                "parallel_execution": True,
                "asset_names": [a["asset_name"] for a in prepared_assets.values()]
            }
        }
        
        response = self.supabase.table("scans").insert(scan_record).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create scan record"
            )
        
        return response.data[0]
    
    async def _execute_scan_background(
        self,
        scan_id: str,
        prepared_assets: Dict[str, Dict[str, Any]],
        user_id: str,
        correlation_id: str
    ):
        """
        Execute scan in background (runs asynchronously).
        
        This method launches pipelines for all assets in parallel and monitors
        their completion. It updates the scan record with progress and results.
        
        Args:
            scan_id: Scan UUID
            prepared_assets: Prepared asset configurations
            user_id: User UUID
            correlation_id: Logging correlation ID
        """
        self.logger.info(f"[{correlation_id}] 🔄 BACKGROUND EXECUTION START")
        
        start_time = datetime.utcnow()
        
        try:
            # Update status to running
            await self._update_scan_status(scan_id, "running", {
                "started_at": start_time.isoformat()
            })
            
            # ============================================================
            # Launch Parallel Pipelines
            # ============================================================
            self.logger.info(
                f"[{correlation_id}] ⚡ Launching {len(prepared_assets)} parallel pipelines"
            )
            
            pipeline_tasks = []
            for asset_id, asset_data in prepared_assets.items():
                modules = asset_data["modules"]
                config = asset_data["config"]
                
                self.logger.info(
                    f"[{correlation_id}] 🚀 Asset {asset_data['asset_name']}: "
                    f"Streaming pipeline (parallel execution)"
                )
                
                # Execute streaming pipeline (single execution path)
                task = scan_pipeline.execute_pipeline(
                    asset_id=asset_id,
                    modules=modules,
                    scan_request=config,
                    user_id=user_id,
                    scan_job_id=scan_id
                )
                
                pipeline_tasks.append((asset_id, asset_data["asset_name"], task))
            
            # Execute all pipelines in parallel
            self.logger.info(f"[{correlation_id}] ⏳ Waiting for pipelines to complete...")
            
            results = await asyncio.gather(
                *[task for _, _, task in pipeline_tasks],
                return_exceptions=True
            )
            
            # ============================================================
            # Process Results
            # ============================================================
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            successful_assets = 0
            failed_assets = 0
            total_subdomains = 0
            
            for (asset_id, asset_name, _), result in zip(pipeline_tasks, results):
                if isinstance(result, Exception):
                    self.logger.error(
                        f"[{correlation_id}] ❌ Asset {asset_name} failed: {str(result)}"
                    )
                    failed_assets += 1
                else:
                    self.logger.info(
                        f"[{correlation_id}] ✅ Asset {asset_name} completed: "
                        f"{result.get('successful_modules', 0)}/{result.get('total_modules', 0)} modules"
                    )
                    successful_assets += 1
                    
                    # Count subdomains (if available in result metadata)
                    if "stream_length" in result:
                        total_subdomains += result["stream_length"]
            
            # ============================================================
            # Update Final Status
            # ============================================================
            final_status = "completed" if failed_assets == 0 else "partial_failure"
            
            await self._update_scan_status(scan_id, final_status, {
                "completed_at": datetime.utcnow().isoformat(),
                "completed_assets": successful_assets,
                "failed_assets": failed_assets,
                "results": {
                    "successful_assets": successful_assets,
                    "failed_assets": failed_assets,
                    "total_subdomains": total_subdomains,
                    "duration_seconds": duration
                }
            })
            
            self.logger.info(f"[{correlation_id}] ✅ BACKGROUND EXECUTION COMPLETE")
            self.logger.info(f"[{correlation_id}] └─ Duration: {duration:.1f}s")
            self.logger.info(
                f"[{correlation_id}] └─ Success: {successful_assets}/{len(prepared_assets)} assets"
            )
            self.logger.info(f"[{correlation_id}] └─ Subdomains: {total_subdomains}")
            
        except Exception as e:
            self.logger.error(
                f"[{correlation_id}] ❌ BACKGROUND EXECUTION FAILED: {str(e)}",
                exc_info=True
            )
            
            # Mark scan as failed
            await self._update_scan_status(scan_id, "failed", {
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e)
            })
    
    async def _update_scan_status(
        self,
        scan_id: str,
        status: str,
        additional_data: Dict[str, Any]
    ):
        """
        Update scan record status.
        
        Args:
            scan_id: Scan UUID
            status: New status (pending, running, completed, failed)
            additional_data: Additional fields to update
        """
        update_data = {"status": status, **additional_data}
        
        try:
            self.supabase.table("scans").update(update_data).eq("id", scan_id).execute()
        except Exception as e:
            self.logger.error(f"Failed to update scan status {scan_id}: {e}")
    
    async def get_scan_status(self, scan_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get scan status and progress.
        
        Args:
            scan_id: Scan UUID
            user_id: User UUID (for authorization)
            
        Returns:
            Scan status with progress information
            
        Raises:
            HTTPException: 404 if scan not found or access denied
        """
        response = self.supabase.table("scans").select("*").eq(
            "id", scan_id
        ).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan {scan_id} not found or access denied"
            )
        
        return response.data[0]


# Singleton instance
scan_orchestrator = ScanOrchestrator()
