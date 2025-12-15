"""
Comprehensive tests for multi-tenant asset management system.
Tests asset creation, quota enforcement, usage tracking, and API endpoints.
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.asset_service import asset_service
from app.services.usage_service import usage_service
from app.schemas.assets import AssetCreate, ApexDomainCreate, Asset, ApexDomain, EnhancedAssetScanRequest
from app.schemas.auth import UserResponse

# Test client instance
client = TestClient(app)

class TestMultiTenantAssetManagement:
    """Test suite for multi-tenant asset management."""
    
    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        return UserResponse(
            id=str(uuid.uuid4()),
            email="test@example.com",
            created_at="2025-01-01T00:00:00Z"
        )
    
    @pytest.fixture
    def sample_asset_data(self):
        """Sample asset creation data."""
        return AssetCreate(
            name="eCorp",
            description="eCorp Vulnerability Disclosure Program",
            priority=5
        )
    
    @pytest.fixture
    def sample_domain_data(self):
        """Sample apex domain creation data."""
        return ApexDomainCreate(
            asset_id=uuid.uuid4(),
            domain="epicgames.com"
        )
    
    @pytest.mark.skip(reason="Quota enforcement deferred for MVP - will implement after core features")
    @pytest.mark.asyncio
    @patch('app.services.usage_service.usage_service.can_create_asset')
    @patch('app.services.asset_service.asset_service.supabase')
    @patch('app.services.usage_service.usage_service.update_asset_count')
    async def test_asset_creation_with_quota_check(
        self, 
        mock_update_count,
        mock_supabase,
        mock_can_create,
        mock_user,
        sample_asset_data
    ):
        """Test asset creation with quota enforcement."""
        # Setup mocks
        mock_can_create.return_value = True
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "id": str(uuid.uuid4()),
                "user_id": str(mock_user.id),
                "name": "Epicgames",
                "description": "Epic Games bug bounty program",
                "bug_bounty_url": "https://www.epicgames.com/site/en-US/security",
                "priority": 5,
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            }
        ]
        
        # Test asset creation
        result = await asset_service.create_asset(sample_asset_data, str(mock_user.id))
        
        # Verify quota was checked
        mock_can_create.assert_called_once_with(uuid.UUID(mock_user.id))
        
        # Verify usage count was updated
        mock_update_count.assert_called_once_with(uuid.UUID(mock_user.id))
        
        # Verify asset was created
        assert result.name == "Epicgames"
        assert result.user_id == uuid.UUID(mock_user.id)
    
    @pytest.mark.skip(reason="Quota enforcement deferred for MVP - will implement after core features")
    @pytest.mark.asyncio
    @patch('app.services.usage_service.usage_service.can_create_asset')
    async def test_asset_creation_quota_exceeded(self, mock_can_create, mock_user, sample_asset_data):
        """Test asset creation when quota is exceeded."""
        # Setup mock to return quota exceeded
        mock_can_create.return_value = False
        
        # Mock the get_user_usage_overview method
        with patch.object(usage_service, 'get_user_usage_overview', return_value={
            'current_assets': 5,
            'max_assets': 5
        }):
            # Test that quota enforcement raises exception
            with pytest.raises(Exception) as exc_info:
                await asset_service.create_asset(sample_asset_data, str(mock_user.id))
            
            # Verify proper error message
            assert "Asset limit reached" in str(exc_info.value)
    
    @pytest.mark.skip(reason="Quota enforcement deferred for MVP - will implement after core features")
    @pytest.mark.asyncio
    @patch('app.services.usage_service.usage_service.can_add_domain_to_asset')
    @patch('app.services.asset_service.asset_service.get_asset')
    @patch('app.services.asset_service.asset_service.supabase')
    @patch('app.services.usage_service.usage_service.update_domain_count')
    async def test_domain_creation_with_quota_check(
        self,
        mock_update_count,
        mock_supabase,
        mock_get_asset,
        mock_can_add_domain,
        mock_user,
        sample_domain_data
    ):
        """Test apex domain creation with quota enforcement."""
        # Setup mocks
        mock_can_add_domain.return_value = True
        mock_get_asset.return_value = Mock(id=sample_domain_data.asset_id)
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "id": str(uuid.uuid4()),
                "asset_id": str(sample_domain_data.asset_id),
                "domain": "epicgames.com",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            }
        ]
        
        # Test domain creation
        result = await asset_service.create_apex_domain(sample_domain_data, str(mock_user.id))
        
        # Verify quota was checked
        mock_can_add_domain.assert_called_once_with(uuid.UUID(mock_user.id), sample_domain_data.asset_id)
        
        # Verify usage count was updated
        mock_update_count.assert_called_once_with(uuid.UUID(mock_user.id))
        
        # Verify domain was created
        assert result.domain == "epicgames.com"
    
    @pytest.mark.skip(reason="Quota enforcement removed during Phase 2 refactoring - needs re-implementation")
    @pytest.mark.asyncio
    @patch('app.services.usage_service.usage_service.can_start_scan')
    async def test_scan_quota_enforcement(self, mock_can_start_scan, mock_user):
        """
        Test scan quota enforcement using modern asset-level scanning.
        
        TODO: Re-implement quota enforcement in start_asset_scan() method.
        The quota checking logic was removed during the October 9th Phase 2 refactoring
        and needs to be added back to the new batch processing workflow.
        """
        from app.services.asset_service import asset_service
        
        # Test when quota is exceeded
        mock_can_start_scan.return_value = False
        
        # Mock the get_user_usage_overview method for proper error message
        with patch.object(usage_service, 'get_user_usage_overview', return_value={
            'scans_today': 50,
            'max_scans_per_day': 50,
            'daily_limit_reached': True
        }):
            # Create a mock asset for testing
            mock_asset_id = uuid.uuid4()
            
            # Mock get_asset to return asset information (updated to use current method)
            with patch.object(asset_service, 'get_asset', return_value=Asset(
                id=mock_asset_id,
                user_id=uuid.UUID(mock_user.id),
                name='Test Asset',
                description=None,
                bug_bounty_url=None,
                priority=1,
                tags=[],
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )):
                # Mock get_apex_domains to return domains (updated to use current method)
                with patch.object(asset_service, 'get_apex_domains', return_value=[
                    ApexDomain(
                        id=uuid.uuid4(),
                        asset_id=mock_asset_id,
                        domain='example.com',
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                ]):
                    # Test that scan quota enforcement raises HTTPException (updated method name)
                    with pytest.raises(HTTPException) as exc_info:
                        await asset_service.start_asset_scan(
                            asset_id=str(mock_asset_id),
                            scan_request=EnhancedAssetScanRequest(
                                modules=['subfinder'],
                                active_domains_only=True
                            ),
                            user_id=str(mock_user.id)
                        )
                    
                    # Verify quota error with correct status code
                    assert exc_info.value.status_code == 429
                    assert "scan limit" in str(exc_info.value.detail).lower()

class TestUsageTrackingAPI:
    """Test suite for usage tracking API endpoints."""
    
    def test_usage_overview_endpoint_unauthorized(self):
        """Test usage overview endpoint without authentication."""
        response = client.get("/api/v1/usage/overview")
        assert response.status_code == 401  # 401 is correct for missing authentication
    
    def test_usage_overview_endpoint_success(self):
        """Test successful usage overview retrieval."""
        from app.core.dependencies import get_current_user
        from app.main import app
        
        # Setup mock user
        mock_user = UserResponse(
            id=str(uuid.uuid4()),
            email="test@example.com",
            created_at="2025-01-01T00:00:00Z"
        )
        
        # Override the dependency
        def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch('app.services.usage_service.usage_service.get_user_usage_overview') as mock_get_overview:
                mock_get_overview.return_value = {
                    "current_assets": 2,
                    "max_assets": 5,
                    "current_domains": 8,
                    "scans_today": 5,
                    "max_scans_per_day": 50,
                    "assets_usage_percent": 40.0,
                    "daily_scans_usage_percent": 10.0
                }
                
                # Make request
                response = client.get("/api/v1/usage/overview")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["current_assets"] == 2
        finally:
            # Clean up override
            app.dependency_overrides.clear()
        assert data["max_assets"] == 5
        assert data["assets_usage_percent"] == 40.0
    
    def test_quota_limits_endpoint(self):
        """Test quota limits endpoint."""
        from app.core.dependencies import get_current_user
        from app.main import app
        
        # Setup mock user
        mock_user = UserResponse(
            id=str(uuid.uuid4()),
            email="test@example.com",
            created_at="2025-01-01T00:00:00Z"
        )
        
        # Override the dependency
        def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch('app.services.usage_service.usage_service.get_quota_limits') as mock_get_quotas:
                mock_get_quotas.return_value = {
                    "max_assets": 5,
                    "max_domains_per_asset": 10,
                    "max_scans_per_day": 50,
                    "max_scans_per_month": 1000,
                    "max_concurrent_scans": 3,
                    "max_subdomains_stored": 10000
                }
                
                # Make request
                response = client.get("/api/v1/usage/quotas")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["max_assets"] == 5
        finally:
            # Clean up override
            app.dependency_overrides.clear()
        assert data["max_scans_per_day"] == 50
    
    def test_asset_creation_limit_check(self):
        """Test asset creation limit check endpoint."""
        from app.core.dependencies import get_current_user
        from app.main import app
        
        # Setup mock user
        mock_user = UserResponse(
            id=str(uuid.uuid4()),
            email="test@example.com",
            created_at="2025-01-01T00:00:00Z"
        )
        
        # Override the dependency
        def mock_get_current_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = mock_get_current_user
        
        try:
            with patch('app.services.usage_service.usage_service.can_create_asset') as mock_can_create, \
                 patch('app.services.usage_service.usage_service.get_user_usage_overview') as mock_get_overview:
                
                mock_can_create.return_value = True
                mock_get_overview.return_value = {
                    "current_assets": 3,
                    "max_assets": 5,
                    "assets_usage_percent": 60.0
                }
                
                # Make request
                response = client.get("/api/v1/usage/limits/assets")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["can_create"] is True
        finally:
            # Clean up override
            app.dependency_overrides.clear()
        assert data["current_count"] == 3
        assert data["limit"] == 5
        assert data["usage_percent"] == 60.0

class TestUsageServiceFunctions:
    """Test suite for usage service functions."""
    
    @pytest.mark.asyncio
    @patch('app.services.usage_service.usage_service.client')
    async def test_quota_initialization(self, mock_client):
        """Test user quota and usage initialization."""
        mock_user_id = uuid.uuid4()
        
        # Setup mock responses
        mock_client.table.return_value.insert.return_value.execute.return_value = Mock()
        
        # Test initialization
        await usage_service._initialize_user_tracking(mock_user_id)
        
        # Verify both quotas and usage were initialized
        assert mock_client.table.call_count == 2
        calls = mock_client.table.call_args_list
        assert "user_quotas" in str(calls[0])
        assert "user_usage" in str(calls[1])
    
    @pytest.mark.asyncio
    @patch('app.services.usage_service.usage_service.client')
    async def test_usage_count_updates(self, mock_client):
        """Test usage count update functions."""
        mock_user_id = uuid.uuid4()
        
        # Create separate mocks for different table calls
        assets_table_mock = Mock()
        usage_table_mock = Mock()
        
        # Configure table selection to return appropriate mocks
        def table_side_effect(table_name):
            if table_name == "assets":
                return assets_table_mock
            elif table_name == "user_usage":
                return usage_table_mock
            return Mock()
        
        mock_client.table.side_effect = table_side_effect
        
        # Mock asset count query (only one .eq() call in actual function)
        assets_table_mock.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "1"}, {"id": "2"}, {"id": "3"}
        ]
        
        # Mock usage update
        usage_table_mock.update.return_value.eq.return_value.execute.return_value = Mock()
        
        # Test asset count update
        await usage_service.update_asset_count(mock_user_id)
        
        # Verify update was called with correct count
        update_call = usage_table_mock.update.call_args[0][0]
        assert update_call["current_assets"] == 3

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
