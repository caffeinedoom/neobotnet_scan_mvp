# AssetService Refactoring - November 10, 2025

## Overview
Refactored `AssetService` to follow the **Single Responsibility Principle** by removing all scan coordination logic and keeping only CRUD operations and queries.

---

## What Changed

### ✅ **Kept (16 methods)**

#### Asset CRUD Operations
- `create_asset()` - Create new asset
- `get_assets()` - List user's assets with stats
- `get_asset()` - Get single asset
- `get_asset_with_stats()` - Get asset with calculated statistics
- `update_asset()` - Update asset details
- `delete_asset()` - Delete asset (cascade deletes domains/subdomains)

#### Apex Domain CRUD Operations
- `create_apex_domain()` - Add domain to asset
- `get_apex_domains()` - List domains for asset with stats
- `update_apex_domain()` - Update domain details
- `delete_apex_domain()` - Delete domain

#### Subdomain Query Methods (Read-Only)
- `get_asset_subdomains()` - Get subdomains for an asset
- `get_all_user_subdomains()` - Get all user's subdomains
- `get_paginated_user_subdomains()` - Paginated subdomain listing

#### User Statistics & Summaries
- `get_user_summary()` - Aggregate user statistics
- `get_paginated_asset_domains()` - Paginated asset domain view
- `get_comprehensive_filter_options()` - Get filter options for UI

---

### ❌ **Removed (11 methods)**

All scan coordination responsibilities moved to `ScanOrchestrator`:

#### Scan Initiation Methods
- `start_asset_scan()` → **Use `ScanOrchestrator.execute_scan()`**
- `_execute_batch_processing()` → **Internal to ScanOrchestrator**
- `start_multi_asset_optimization()` → **Use `ScanOrchestrator.execute_scan()`**
- `_create_multi_asset_scan_record()` → **Internal to ScanOrchestrator**

#### Scan Status Methods
- `list_asset_scans()` → **Use new `/api/v1/scans` endpoint**
- `get_asset_scan_status()` → **Use `GET /api/v1/scans/{scan_id}`**

#### Scan Progress Management
- `update_scan_job_progress()` → **Managed by ScanOrchestrator**
- `complete_scan_job()` → **Managed by ScanOrchestrator**
- `fail_scan_job()` → **Managed by ScanOrchestrator**
- `get_scan_job_status()` → **Use `GET /api/v1/scans/{scan_id}`**
- `_get_current_metadata()` → **Internal helper removed**

---

### 🗑️ **Removed Imports**

Scan-related dependencies no longer needed:
```python
# REMOVED:
from ..schemas.batch import BatchOptimizationRequest, ResourceProfile
from .batch_workflow_orchestrator import batch_workflow_orchestrator
from .scan_pipeline import ScanPipeline
from .resource_calculator import resource_calculator
from .websocket_manager import batch_progress_notifier
```

---

## Impact Analysis

### File Size Reduction
- **Before**: 2,184 lines
- **After**: 1,139 lines
- **Removed**: 1,045 lines (47.8% reduction)

### Breaking Changes

#### ⚠️ Old API Endpoints (Will be removed in Phase 4)
These endpoints **still reference the removed methods** and will fail:
- `POST /api/v1/assets/{asset_id}/scan` (in `assets.py`)
- `POST /api/v1/batch/multi-asset/scan` (in `batch_processing.py`)

**Migration Path**:
- Use new unified endpoint: `POST /api/v1/scans`
- See `backend/app/api/v1/scans.py` for new API

---

## Benefits

### 1. **Single Responsibility Principle**
`AssetService` now has one clear purpose: **Asset and Domain CRUD operations**

### 2. **Improved Maintainability**
- Easier to understand and modify
- Clearer separation of concerns
- Reduced coupling between services

### 3. **Better Testability**
- Simpler test cases (no scan logic to mock)
- Faster unit tests
- Clearer test boundaries

### 4. **Consistent Architecture**
- `ScanOrchestrator` → Scan coordination
- `AssetService` → Asset/Domain CRUD
- `ScanPipeline` → Module execution
- Each service has a single, well-defined purpose

---

## Migration Guide

### For Developers

#### Before (OLD - DON'T USE):
```python
# OLD: Asset scan via AssetService
from app.services.asset_service import asset_service

result = await asset_service.start_asset_scan(
    asset_id="...",
    scan_request=EnhancedAssetScanRequest(...),
    user_id="..."
)
```

#### After (NEW - USE THIS):
```python
# NEW: Asset scan via ScanOrchestrator
from app.services.scan_orchestrator import scan_orchestrator

result = await scan_orchestrator.execute_scan(
    asset_configs={
        asset_id: EnhancedAssetScanRequest(...)
    },
    user_id="..."
)
```

### For API Consumers

#### Before (OLD - DON'T USE):
```bash
# OLD: Single asset scan
POST /api/v1/assets/{asset_id}/scan
{
  "modules": ["subfinder", "dnsx"],
  "active_domains_only": true
}
```

#### After (NEW - USE THIS):
```bash
# NEW: Unified scan endpoint (supports single or multi-asset)
POST /api/v1/scans
{
  "asset_configs": {
    "{asset_id}": {
      "modules": ["subfinder", "dnsx"],
      "active_domains_only": true
    }
  }
}

# Response: 202 Accepted
{
  "scan_id": "...",
  "status": "pending",
  "assets_count": 1,
  ...
}

# Then poll for status:
GET /api/v1/scans/{scan_id}
```

---

## Related Changes

### Completed
- ✅ Task 1.1: Created `ScanOrchestrator` service
- ✅ Task 1.2: Created new `/api/v1/scans` endpoints
- ✅ Task 1.3: Updated database schema (added `scans` table)
- ✅ Task 1.4: Refactored `AssetService` (THIS FILE)

### Pending
- ⏳ Task 1.5: Add comprehensive logging
- ⏳ Phase 2: Frontend migration to new API
- ⏳ Phase 3: Integration testing
- ⏳ Phase 4: Remove old endpoints (`assets.py`, `batch_processing.py`)

---

## Rollback Plan

If needed, restore the old version:
```bash
# Backup location (during development)
backend/app/services/asset_service.py.backup

# Or from Git:
git checkout <previous-commit> -- backend/app/services/asset_service.py
```

**Note**: After Phase 4 completion, old endpoints will be removed and rollback will require more extensive changes.

---

## Questions?

See:
- `docs/refactoring/unified_scan_refactoring_2025_11_10.md` - Full refactoring plan
- `backend/app/services/scan_orchestrator.py` - New scan coordination service
- `backend/app/api/v1/scans.py` - New unified scan API
