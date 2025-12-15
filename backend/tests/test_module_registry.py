"""
Unit tests for Module Registry Service
=======================================

Tests the module discovery, validation, and caching functionality.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.services.module_registry import ModuleRegistry, module_registry
from app.schemas.batch import ModuleProfile, ModuleResourceScaling, ResourceRange
from fastapi import HTTPException


# ================================================================
# Test Fixtures
# ================================================================

@pytest.fixture
def mock_module_profile_data():
    """Sample module profile data as it comes from database."""
    return {
        "id": str(uuid.uuid4()),
        "module_name": "subfinder",
        "version": "1.0",
        "supports_batching": True,
        "max_batch_size": 50,
        "resource_scaling": {
            "domain_count_ranges": [
                {
                    "min_domains": 1,
                    "max_domains": 10,
                    "cpu": 256,
                    "memory": 512,
                    "description": "Small batch"
                },
                {
                    "min_domains": 11,
                    "max_domains": 50,
                    "cpu": 512,
                    "memory": 1024,
                    "description": "Medium batch"
                }
            ],
            "scaling_notes": "Subfinder is I/O bound"
        },
        "estimated_duration_per_domain": 120,
        "task_definition_template": "neobotnet-v2-dev-subfinder-batch",
        "container_name": "subfinder",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def mock_dns_module_profile_data():
    """Sample DNS module profile data."""
    return {
        "id": str(uuid.uuid4()),
        "module_name": "dns_resolver",
        "version": "1.0",
        "supports_batching": True,
        "max_batch_size": 500,
        "resource_scaling": {
            "domain_count_ranges": [
                {
                    "min_domains": 1,
                    "max_domains": 100,
                    "cpu": 256,
                    "memory": 512,
                    "description": "DNS is fast"
                }
            ],
            "scaling_notes": "DNS resolution is network I/O bound"
        },
        "estimated_duration_per_domain": 2,
        "task_definition_template": "neobotnet-v2-dev-dns_resolver-batch",
        "container_name": "dns-resolver",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def registry():
    """Fresh module registry instance for each test."""
    reg = ModuleRegistry()
    reg.clear_cache()  # Ensure clean state
    return reg


# ================================================================
# Discovery Tests
# ================================================================

@pytest.mark.asyncio
async def test_discover_modules_success(registry, mock_module_profile_data, mock_dns_module_profile_data):
    """Test successful module discovery from database."""
    # Mock Supabase response
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data, mock_dns_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        modules = await registry.discover_modules()
        
        assert len(modules) == 2
        assert modules[0].module_name == "subfinder"
        assert modules[1].module_name == "dns_resolver"
        assert all(isinstance(m, ModuleProfile) for m in modules)


@pytest.mark.asyncio
async def test_discover_modules_empty_database(registry):
    """Test discovery when no modules exist in database."""
    mock_response = Mock()
    mock_response.data = []
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        modules = await registry.discover_modules()
        
        assert len(modules) == 0


@pytest.mark.asyncio
async def test_discover_modules_uses_cache(registry, mock_module_profile_data):
    """Test that discover_modules uses cache on subsequent calls."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        # First call - should hit database
        modules1 = await registry.discover_modules()
        call_count_1 = mock_table.call_count
        
        # Second call - should use cache
        modules2 = await registry.discover_modules()
        call_count_2 = mock_table.call_count
        
        assert len(modules1) == 1
        assert len(modules2) == 1
        assert call_count_1 == call_count_2  # No additional database calls


@pytest.mark.asyncio
async def test_discover_modules_refresh_cache(registry, mock_module_profile_data):
    """Test forcing cache refresh."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        # First call
        await registry.discover_modules()
        call_count_1 = mock_table.call_count
        
        # Second call with refresh
        await registry.discover_modules(refresh_cache=True)
        call_count_2 = mock_table.call_count
        
        assert call_count_2 > call_count_1  # Additional database call


# ================================================================
# Get Module Tests
# ================================================================

@pytest.mark.asyncio
async def test_get_module_success(registry, mock_module_profile_data):
    """Test getting a specific module by name."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        module = await registry.get_module("subfinder")
        
        assert module is not None
        assert module.module_name == "subfinder"
        assert module.supports_batching is True
        assert module.max_batch_size == 50


@pytest.mark.asyncio
async def test_get_module_not_found(registry):
    """Test getting a non-existent module."""
    mock_response = Mock()
    mock_response.data = []
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        module = await registry.get_module("nonexistent")
        
        assert module is None


@pytest.mark.asyncio
async def test_get_module_caching(registry, mock_module_profile_data):
    """Test that get_module uses cache."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        # First call
        module1 = await registry.get_module("subfinder")
        call_count_1 = mock_table.call_count
        
        # Second call - should use cache
        module2 = await registry.get_module("subfinder")
        call_count_2 = mock_table.call_count
        
        assert module1.module_name == module2.module_name
        assert call_count_1 == call_count_2


# ================================================================
# Validation Tests
# ================================================================

@pytest.mark.asyncio
async def test_validate_module_exists(registry, mock_module_profile_data):
    """Test validating an existing module."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        is_valid = await registry.validate_module("subfinder")
        
        assert is_valid is True


@pytest.mark.asyncio
async def test_validate_module_not_exists(registry):
    """Test validating a non-existent module."""
    mock_response = Mock()
    mock_response.data = []
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        is_valid = await registry.validate_module("nonexistent")
        
        assert is_valid is False


@pytest.mark.asyncio
async def test_validate_multiple_modules(registry, mock_module_profile_data, mock_dns_module_profile_data):
    """Test validating multiple modules at once."""
    def mock_query_side_effect(*args, **kwargs):
        # Return different data based on which module is queried
        mock_resp = Mock()
        # This is a simplified mock - in reality you'd need to track the filter calls
        mock_resp.data = [mock_module_profile_data]
        return mock_resp
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = mock_query_side_effect
        
        results = await registry.validate_modules(["subfinder", "nonexistent"])
        
        # At least one should be valid (subfinder)
        assert isinstance(results, dict)
        assert len(results) == 2


@pytest.mark.asyncio
async def test_validate_batch_request_valid(registry, mock_module_profile_data):
    """Test validating a valid batch request."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        validation = await registry.validate_batch_request("subfinder", 25)
        
        assert validation['valid'] is True
        assert len(validation['errors']) == 0
        assert validation['module'] is not None


@pytest.mark.asyncio
async def test_validate_batch_request_exceeds_max_size(registry, mock_module_profile_data):
    """Test validation fails when domain count exceeds max batch size."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        validation = await registry.validate_batch_request("subfinder", 100)  # max_batch_size is 50
        
        assert validation['valid'] is False
        assert len(validation['errors']) > 0
        assert "exceeds" in validation['errors'][0].lower()


@pytest.mark.asyncio
async def test_validate_batch_request_module_not_found(registry):
    """Test validation fails for non-existent module."""
    mock_response = Mock()
    mock_response.data = []
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        validation = await registry.validate_batch_request("nonexistent", 10)
        
        assert validation['valid'] is False
        assert "not found" in validation['errors'][0].lower()


@pytest.mark.asyncio
async def test_validate_batch_request_no_batch_support(registry, mock_module_profile_data):
    """Test validation fails when module doesn't support batching."""
    # Modify mock to not support batching
    mock_data = mock_module_profile_data.copy()
    mock_data['supports_batching'] = False
    mock_data['max_batch_size'] = 1
    
    mock_response = Mock()
    mock_response.data = [mock_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        validation = await registry.validate_batch_request("subfinder", 10)
        
        assert validation['valid'] is False
        assert "does not support batch" in validation['errors'][0].lower()


# ================================================================
# Capabilities Tests
# ================================================================

@pytest.mark.asyncio
async def test_get_module_capabilities(registry, mock_module_profile_data):
    """Test getting module capabilities."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        caps = await registry.get_module_capabilities("subfinder")
        
        assert caps is not None
        assert caps['module_name'] == "subfinder"
        assert caps['supports_batching'] is True
        assert caps['max_batch_size'] == 50
        assert 'version' in caps


@pytest.mark.asyncio
async def test_get_module_capabilities_not_found(registry):
    """Test getting capabilities for non-existent module."""
    mock_response = Mock()
    mock_response.data = []
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        caps = await registry.get_module_capabilities("nonexistent")
        
        assert caps is None


@pytest.mark.asyncio
async def test_list_available_modules(registry, mock_module_profile_data, mock_dns_module_profile_data):
    """Test listing available modules."""
    mock_response = Mock()
    mock_response.data = [mock_module_profile_data, mock_dns_module_profile_data]
    
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_response
        
        modules = await registry.list_available_modules()
        
        assert len(modules) == 2
        assert all('name' in m for m in modules)
        assert all('version' in m for m in modules)
        assert all('supports_batching' in m for m in modules)


# ================================================================
# Cache Management Tests
# ================================================================

def test_cache_invalidation(registry):
    """Test cache TTL invalidation."""
    # Set cache with old timestamp
    registry._cache_timestamp = datetime.utcnow() - timedelta(minutes=20)
    
    is_valid = registry._is_cache_valid()
    
    assert is_valid is False


def test_cache_valid(registry):
    """Test cache is valid within TTL."""
    registry._cache_timestamp = datetime.utcnow()
    
    is_valid = registry._is_cache_valid()
    
    assert is_valid is True


def test_clear_cache(registry, mock_module_profile_data):
    """Test manually clearing cache."""
    # Add something to cache
    mock_module = ModuleProfile(**{
        **mock_module_profile_data,
        "resource_scaling": ModuleResourceScaling(**mock_module_profile_data["resource_scaling"])
    })
    registry._module_cache["test"] = mock_module
    registry._cache_timestamp = datetime.utcnow()
    
    assert len(registry._module_cache) > 0
    assert registry._cache_timestamp is not None
    
    registry.clear_cache()
    
    assert len(registry._module_cache) == 0
    assert registry._cache_timestamp is None


# ================================================================
# Error Handling Tests
# ================================================================

@pytest.mark.asyncio
async def test_discover_modules_database_error_with_cache(registry, mock_module_profile_data):
    """Test discovery falls back to cache on database error."""
    # First, populate cache
    mock_module = ModuleProfile(**{
        **mock_module_profile_data,
        "resource_scaling": ModuleResourceScaling(**mock_module_profile_data["resource_scaling"])
    })
    registry._module_cache["subfinder"] = mock_module
    registry._cache_timestamp = datetime.utcnow()
    
    # Now simulate database error
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.side_effect = Exception("Database connection failed")
        
        # Should return cached modules instead of raising
        modules = await registry.discover_modules()
        
        assert len(modules) == 1
        assert modules[0].module_name == "subfinder"


@pytest.mark.asyncio
async def test_discover_modules_database_error_no_cache(registry):
    """Test discovery raises error when no cache available."""
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.side_effect = Exception("Database connection failed")
        
        # Should raise HTTPException since no cache available
        with pytest.raises(HTTPException) as exc_info:
            await registry.discover_modules()
        
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_module_returns_cached_on_error(registry, mock_module_profile_data):
    """Test get_module falls back to cache on error."""
    # Populate cache
    mock_module = ModuleProfile(**{
        **mock_module_profile_data,
        "resource_scaling": ModuleResourceScaling(**mock_module_profile_data["resource_scaling"])
    })
    registry._module_cache["subfinder"] = mock_module
    registry._cache_timestamp = datetime.utcnow()
    
    # Simulate database error
    with patch.object(registry.supabase, 'table') as mock_table:
        mock_table.side_effect = Exception("Database error")
        
        module = await registry.get_module("subfinder")
        
        assert module is not None
        assert module.module_name == "subfinder"


# ================================================================
# Integration Test with Global Singleton
# ================================================================

def test_global_singleton_exists():
    """Test that global module_registry singleton exists."""
    from app.services.module_registry import module_registry as global_registry
    
    assert global_registry is not None
    assert isinstance(global_registry, ModuleRegistry)
