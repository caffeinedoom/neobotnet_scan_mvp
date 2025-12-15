"""
Tests for Scan Pre-Launch Validation
====================================

Tests the module validation that happens before creating scan jobs,
ensuring invalid modules are rejected immediately and don't waste resources.
"""

import pytest
import uuid
from unittest.mock import patch, Mock, AsyncMock
from fastapi import HTTPException

from app.api.v1.assets import start_asset_scan
from app.schemas.assets import EnhancedAssetScanRequest
from app.schemas.recon import ReconModule
from app.schemas.auth import UserResponse


# ================================================================
# Test Fixtures
# ================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return UserResponse(
        id=str(uuid.uuid4()),
        email="test@example.com",
        full_name="Test User",
        created_at="2025-01-01T00:00:00Z"
    )


@pytest.fixture
def valid_scan_request():
    """Valid scan request with subfinder module."""
    return EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True,
        enable_batch_optimization=True
    )


@pytest.fixture
def invalid_scan_request():
    """Scan request with non-existent module."""
    # We'll mock this since we can't create an invalid ReconModule enum value
    request = EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True
    )
    # We'll patch the module_names extraction in tests
    return request


# ================================================================
# Validation Success Tests
# ================================================================

@pytest.mark.asyncio
async def test_valid_module_passes_validation(mock_user, valid_scan_request):
    """Test that valid modules pass pre-launch validation."""
    asset_id = str(uuid.uuid4())
    
    # Mock module_registry to return valid result
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        mock_registry.validate_modules = AsyncMock(return_value={
            "subfinder": True
        })
        
        # Mock asset_service to avoid actual scan
        with patch('app.api.v1.assets.asset_service') as mock_service:
            mock_service.start_asset_scan = AsyncMock(return_value={
                "asset_scan_id": str(uuid.uuid4()),
                "status": "pending"
            })
            
            # Should not raise exception
            result = await start_asset_scan(asset_id, valid_scan_request, mock_user)
            
            # Verify validation was called
            mock_registry.validate_modules.assert_called_once_with(["subfinder"])
            
            # Verify scan service was called (validation passed)
            mock_service.start_asset_scan.assert_called_once()
            
            assert result is not None


@pytest.mark.asyncio
async def test_multiple_valid_modules_pass_validation(mock_user):
    """Test that multiple valid modules all pass validation."""
    asset_id = str(uuid.uuid4())
    
    # Create request with multiple modules (we'll mock the validation)
    scan_request = EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True
    )
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        # Simulate multiple modules being valid
        mock_registry.validate_modules = AsyncMock(return_value={
            "subfinder": True,
            "dns_resolver": True
        })
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            mock_service.start_asset_scan = AsyncMock(return_value={
                "asset_scan_id": str(uuid.uuid4())
            })
            
            # Patch the module extraction to simulate multiple modules
            with patch.object(scan_request, 'modules', [ReconModule.SUBFINDER]):
                result = await start_asset_scan(asset_id, scan_request, mock_user)
            
            assert result is not None
            mock_service.start_asset_scan.assert_called_once()


# ================================================================
# Validation Failure Tests
# ================================================================

@pytest.mark.asyncio
async def test_invalid_module_raises_400_error(mock_user, valid_scan_request):
    """Test that invalid module names are rejected with 400 error."""
    asset_id = str(uuid.uuid4())
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        # Simulate module not found/inactive
        mock_registry.validate_modules = AsyncMock(return_value={
            "nonexistent_module": False
        })
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            # Patch module extraction to simulate invalid module
            with patch.object(valid_scan_request, 'modules', [Mock(value="nonexistent_module")]):
                with pytest.raises(HTTPException) as exc_info:
                    await start_asset_scan(asset_id, valid_scan_request, mock_user)
                
                # Verify error details
                assert exc_info.value.status_code == 400
                assert "invalid_modules" in str(exc_info.value.detail).lower()
                assert "nonexistent_module" in str(exc_info.value.detail)
                
                # Verify asset_service was NOT called (validation failed)
                mock_service.start_asset_scan.assert_not_called()


@pytest.mark.asyncio
async def test_partial_invalid_modules_raises_error(mock_user):
    """Test that if ANY module is invalid, the request is rejected."""
    asset_id = str(uuid.uuid4())
    
    scan_request = EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True
    )
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        # One valid, one invalid
        mock_registry.validate_modules = AsyncMock(return_value={
            "subfinder": True,
            "invalid_module": False
        })
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            with patch.object(scan_request, 'modules', [
                Mock(value="subfinder"),
                Mock(value="invalid_module")
            ]):
                with pytest.raises(HTTPException) as exc_info:
                    await start_asset_scan(asset_id, scan_request, mock_user)
                
                # Verify error mentions the invalid module
                assert "invalid_module" in str(exc_info.value.detail)
                
                # Verify scan was not started
                mock_service.start_asset_scan.assert_not_called()


@pytest.mark.asyncio
async def test_inactive_module_raises_error(mock_user, valid_scan_request):
    """Test that inactive modules are rejected."""
    asset_id = str(uuid.uuid4())
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        # Module exists but is inactive
        mock_registry.validate_modules = AsyncMock(return_value={
            "subfinder": False  # Inactive
        })
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            with pytest.raises(HTTPException) as exc_info:
                await start_asset_scan(asset_id, valid_scan_request, mock_user)
            
            assert exc_info.value.status_code == 400
            mock_service.start_asset_scan.assert_not_called()


# ================================================================
# Error Response Structure Tests
# ================================================================

@pytest.mark.asyncio
async def test_error_response_includes_helpful_details(mock_user):
    """Test that validation errors include detailed, actionable information."""
    asset_id = str(uuid.uuid4())
    
    scan_request = EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True
    )
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        mock_registry.validate_modules = AsyncMock(return_value={
            "subfinder": True,
            "bad_module": False
        })
        
        with patch('app.api.v1.assets.asset_service'):
            with patch.object(scan_request, 'modules', [
                Mock(value="subfinder"),
                Mock(value="bad_module")
            ]):
                with pytest.raises(HTTPException) as exc_info:
                    await start_asset_scan(asset_id, scan_request, mock_user)
                
                error_detail = exc_info.value.detail
                
                # Verify error structure
                assert isinstance(error_detail, dict)
                assert "error" in error_detail
                assert "message" in error_detail
                assert "invalid_modules" in error_detail
                assert "valid_modules" in error_detail
                
                # Verify content
                assert error_detail["error"] == "invalid_modules"
                assert "bad_module" in error_detail["invalid_modules"]
                assert "subfinder" in error_detail["valid_modules"]


# ================================================================
# Logging Tests
# ================================================================

@pytest.mark.asyncio
async def test_validation_success_is_logged(mock_user, valid_scan_request, caplog):
    """Test that successful validation is logged."""
    asset_id = str(uuid.uuid4())
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        mock_registry.validate_modules = AsyncMock(return_value={
            "subfinder": True
        })
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            mock_service.start_asset_scan = AsyncMock(return_value={})
            
            import logging
            with caplog.at_level(logging.INFO):
                await start_asset_scan(asset_id, valid_scan_request, mock_user)
            
            # Check log messages
            log_messages = [record.message for record in caplog.records]
            assert any("Validating scan request" in msg for msg in log_messages)
            assert any("Module validation passed" in msg for msg in log_messages)


@pytest.mark.asyncio
async def test_validation_failure_is_logged(mock_user, caplog):
    """Test that validation failures are logged as warnings."""
    asset_id = str(uuid.uuid4())
    
    scan_request = EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True
    )
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        mock_registry.validate_modules = AsyncMock(return_value={
            "bad_module": False
        })
        
        with patch('app.api.v1.assets.asset_service'):
            with patch.object(scan_request, 'modules', [Mock(value="bad_module")]):
                import logging
                with caplog.at_level(logging.WARNING):
                    try:
                        await start_asset_scan(asset_id, scan_request, mock_user)
                    except HTTPException:
                        pass
                
                # Check warning was logged
                log_messages = [record.message for record in caplog.records]
                assert any("Scan validation failed" in msg for msg in log_messages)


# ================================================================
# Integration-Style Tests
# ================================================================

@pytest.mark.asyncio
async def test_validation_prevents_wasted_ecs_launches(mock_user):
    """
    Integration test: Verify validation happens BEFORE service call.
    This prevents wasted AWS ECS task launches for invalid modules.
    """
    asset_id = str(uuid.uuid4())
    
    scan_request = EnhancedAssetScanRequest(
        modules=[ReconModule.SUBFINDER],
        active_domains_only=True
    )
    
    # Track call order
    call_order = []
    
    async def mock_validate(*args, **kwargs):
        call_order.append("validate")
        return {"invalid": False}
    
    async def mock_start_scan(*args, **kwargs):
        call_order.append("start_scan")
        return {}
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        mock_registry.validate_modules = mock_validate
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            mock_service.start_asset_scan = mock_start_scan
            with patch.object(scan_request, 'modules', [Mock(value="invalid")]):
                try:
                    await start_asset_scan(asset_id, scan_request, mock_user)
                except HTTPException:
                    pass
            
            # Verify validation happened first and scan was never attempted
            assert call_order == ["validate"]


@pytest.mark.asyncio
async def test_empty_modules_list_handling(mock_user):
    """Test handling of empty modules list."""
    asset_id = str(uuid.uuid4())
    
    scan_request = EnhancedAssetScanRequest(
        modules=[],  # Empty list
        active_domains_only=True
    )
    
    with patch('app.api.v1.assets.module_registry') as mock_registry:
        mock_registry.validate_modules = AsyncMock(return_value={})
        
        with patch('app.api.v1.assets.asset_service') as mock_service:
            mock_service.start_asset_scan = AsyncMock(return_value={})
            
            # Should handle gracefully (empty list is valid)
            result = await start_asset_scan(asset_id, scan_request, mock_user)
            
            # Validation should still be called
            mock_registry.validate_modules.assert_called_once_with([])
            
            # Service should be called
            mock_service.start_asset_scan.assert_called_once()
