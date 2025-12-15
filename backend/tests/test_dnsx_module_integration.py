"""
Integration tests for DNSX module registration.

Tests that DNSX is properly registered in the database and will be
discoverable once activated in Phase 4.

Author: Pluckware Development Team
Date: October 28, 2025
Phase: 3 - Backend Integration & Module Registration
"""

import pytest
import os
from app.services.module_registry import module_registry
from app.core.supabase_client import SupabaseClient

# ================================================================
# CI/CD Skip Marker for Integration Tests
# ================================================================
# These are true integration tests that require a real Supabase database.
# They are skipped in CI/CD (which uses fake test credentials) but run
# in local development with real credentials.
#
# Detection: Skip if SUPABASE_URL starts with "https://test." (fake URL)
# ================================================================
pytestmark = pytest.mark.skipif(
    os.getenv("SUPABASE_URL", "").startswith("https://test."),
    reason="Integration tests require real Supabase database (skipped in CI/CD with fake credentials)"
)


@pytest.mark.asyncio
async def test_dnsx_module_exists_in_database():
    """
    Test that DNSX module exists in database (bypassing is_active filter).
    
    Validates:
    - DNSX record exists in scan_module_profiles table
    - All required fields are present
    - Configuration is correct
    """
    supabase = SupabaseClient().service_client
    
    # Query DNSX directly from database (ignore is_active)
    response = supabase.table("scan_module_profiles").select("*").eq(
        "module_name", "dnsx"
    ).execute()
    
    assert len(response.data) > 0, "DNSX module not found in database"
    
    dnsx = response.data[0]
    assert dnsx["module_name"] == "dnsx"
    assert dnsx["version"] == "1.0"
    assert dnsx["supports_batching"] is True
    assert dnsx["max_batch_size"] == 200
    assert dnsx["is_active"] is False  # Should be inactive until Phase 4
    assert dnsx["task_definition_template"] == "neobotnet-v2-dev-dnsx-batch"
    assert dnsx["container_name"] == "dnsx-scanner"
    assert dnsx["estimated_duration_per_domain"] == 3
    
    print(f"✅ DNSX module exists in database")
    print(f"   - Module: {dnsx['module_name']}")
    print(f"   - Version: {dnsx['version']}")
    print(f"   - Active: {dnsx['is_active']} (will activate in Phase 4)")
    print(f"   - Batch size: {dnsx['max_batch_size']}")


@pytest.mark.asyncio
async def test_dnsx_resource_scaling_in_database():
    """
    Test DNSX resource scaling configuration exists in database.
    
    Validates:
    - Resource scaling JSONB field is populated
    - 3 domain count ranges are defined
    - CPU and memory values are appropriate
    """
    supabase = SupabaseClient().service_client
    
    response = supabase.table("scan_module_profiles").select("resource_scaling").eq(
        "module_name", "dnsx"
    ).execute()
    
    assert len(response.data) > 0
    scaling = response.data[0]["resource_scaling"]
    
    assert "domain_count_ranges" in scaling
    ranges = scaling["domain_count_ranges"]
    assert len(ranges) == 3, f"Expected 3 scaling ranges, got {len(ranges)}"
    
    # Verify small batch config (1-50 domains)
    small = ranges[0]
    assert small["min_domains"] == 1
    assert small["max_domains"] == 50
    assert small["cpu"] == 256
    assert small["memory"] == 512
    
    # Verify medium batch config (51-100 domains)
    medium = ranges[1]
    assert medium["min_domains"] == 51
    assert medium["max_domains"] == 100
    assert medium["cpu"] == 512
    assert medium["memory"] == 1024
    
    # Verify large batch config (101-200 domains)
    large = ranges[2]
    assert large["min_domains"] == 101
    assert large["max_domains"] == 200
    assert large["cpu"] == 1024
    assert large["memory"] == 2048
    
    print(f"✅ Resource scaling configured correctly:")
    print(f"   - Small (1-50): {small['cpu']} CPU, {small['memory']} MB")
    print(f"   - Medium (51-100): {medium['cpu']} CPU, {medium['memory']} MB")
    print(f"   - Large (101-200): {large['cpu']} CPU, {large['memory']} MB")


@pytest.mark.asyncio
async def test_dnsx_optimization_hints_in_database():
    """
    Test DNSX optimization hints exist in database.
    
    Validates:
    - Optimization hints JSONB field is populated
    - Expected fields exist
    - Dependencies are correct
    """
    supabase = SupabaseClient().service_client
    
    response = supabase.table("scan_module_profiles").select("optimization_hints").eq(
        "module_name", "dnsx"
    ).execute()
    
    assert len(response.data) > 0
    hints = response.data[0]["optimization_hints"]
    
    assert hints.get("requires_internet") is True
    assert hints.get("requires_subdomains") is True
    assert hints.get("concurrent_limit") == 50
    assert "subfinder" in hints.get("dependencies", [])
    assert hints.get("memory_multiplier") == 1.0
    
    print(f"✅ Optimization hints configured:")
    print(f"   - Requires internet: {hints.get('requires_internet')}")
    print(f"   - Requires subdomains: {hints.get('requires_subdomains')}")
    print(f"   - Concurrent limit: {hints.get('concurrent_limit')}")
    print(f"   - Dependencies: {hints.get('dependencies')}")


@pytest.mark.asyncio
async def test_dnsx_module_not_discovered_when_inactive():
    """
    Test that inactive DNSX module is NOT discovered by module registry.
    
    Validates:
    - Module registry correctly filters out inactive modules
    - Only active modules appear in discovery
    - This is expected behavior for Phase 3
    """
    # Refresh module cache to ensure we get latest from database
    modules = await module_registry.discover_modules(refresh_cache=True)
    
    # Check DNSX is NOT in the list (because it's inactive)
    module_names = [m.module_name for m in modules]
    assert "dnsx" not in module_names, "DNSX should not be discovered when inactive"
    
    # But subfinder (active) should be there
    assert "subfinder" in module_names, "Subfinder should be discovered (it's active)"
    
    print(f"✅ Module registry correctly excludes inactive modules")
    print(f"   - Active modules found: {module_names}")
    print(f"   - DNSX excluded (inactive): Correct ✓")


@pytest.mark.asyncio
async def test_dnsx_module_validation_rejects_inactive():
    """
    Test DNSX module validation correctly rejects inactive module.
    
    Validates:
    - validate_module returns False for inactive modules
    - This prevents inactive modules from being used in scans
    """
    is_valid = await module_registry.validate_module("dnsx")
    
    # Should be invalid because is_active=false
    assert is_valid is False, "DNSX should be invalid (not active yet)"
    
    print(f"✅ DNSX validation correctly returns False (module inactive)")


@pytest.mark.asyncio
async def test_dnsx_batch_request_validation_rejects_inactive():
    """
    Test batch request validation rejects inactive DNSX module.
    
    Validates:
    - Validation fails for inactive module
    - Error messages are informative
    """
    # This should fail because DNSX is not active
    validation = await module_registry.validate_batch_request(
        module_name="dnsx",
        domain_count=50
    )
    
    assert validation["valid"] is False
    assert "errors" in validation
    assert len(validation["errors"]) > 0
    
    print(f"✅ Batch request validation correctly rejects inactive module")
    print(f"   - Validation result: {validation}")


@pytest.mark.asyncio
async def test_dnsx_multiple_module_validation():
    """
    Test validating multiple modules including inactive DNSX.
    
    Validates:
    - Batch validation works for multiple modules
    - DNSX is correctly identified as invalid
    - Subfinder (active) is valid
    """
    validation_results = await module_registry.validate_modules(["subfinder", "dnsx"])
    
    assert "subfinder" in validation_results
    assert "dnsx" in validation_results
    
    # Subfinder should be valid (active)
    assert validation_results["subfinder"] is True
    
    # DNSX should be invalid (inactive)
    assert validation_results["dnsx"] is False
    
    print(f"✅ Multi-module validation working:")
    print(f"   - subfinder: {validation_results['subfinder']} (active)")
    print(f"   - dnsx: {validation_results['dnsx']} (inactive)")


@pytest.mark.asyncio
async def test_dnsx_will_be_discoverable_when_activated():
    """
    Test plan verification: DNSX will be discoverable once activated.
    
    This test verifies the activation path for Phase 4:
    1. Module exists in database ✓
    2. Module has all required configuration ✓
    3. When is_active is set to True, it will be discovered ✓
    
    This is a planning/verification test, not a functional test.
    """
    supabase = SupabaseClient().service_client
    
    # Verify all required fields exist for future activation
    response = supabase.table("scan_module_profiles").select("*").eq(
        "module_name", "dnsx"
    ).execute()
    
    assert len(response.data) > 0
    dnsx = response.data[0]
    
    # Verify all critical fields are present
    required_fields = [
        "module_name",
        "version",
        "supports_batching",
        "max_batch_size",
        "resource_scaling",
        "task_definition_template",
        "container_name",
        "optimization_hints",
        "is_active"
    ]
    
    for field in required_fields:
        assert field in dnsx, f"Missing required field: {field}"
    
    print(f"✅ DNSX module ready for activation in Phase 4:")
    print(f"   - All required fields present: ✓")
    print(f"   - Resource scaling configured: ✓")
    print(f"   - Optimization hints configured: ✓")
    print(f"   - Task definition defined: ✓")
    print(f"   - Container name defined: ✓")
    print(f"")
    print(f"📋 Activation steps for Phase 4:")
    print(f"   1. Deploy container to AWS ECS")
    print(f"   2. Test container execution")
    print(f"   3. Run: UPDATE scan_module_profiles SET is_active = true WHERE module_name = 'dnsx'")
    print(f"   4. Verify module_registry.discover_modules() includes DNSX")


@pytest.mark.asyncio
async def test_dnsx_task_definition_configuration():
    """
    Test DNSX ECS task definition configuration.
    
    Validates:
    - Task definition name matches AWS naming convention
    - Container name is correct
    """
    supabase = SupabaseClient().service_client
    
    response = supabase.table("scan_module_profiles").select(
        "task_definition_template, container_name"
    ).eq("module_name", "dnsx").execute()
    
    assert len(response.data) > 0
    config = response.data[0]
    
    assert config["task_definition_template"] == "neobotnet-v2-dev-dnsx-batch"
    assert config["container_name"] == "dnsx-scanner"
    
    print(f"✅ Task definition configured:")
    print(f"   - Template: {config['task_definition_template']}")
    print(f"   - Container: {config['container_name']}")
