"""
Unit Tests for Batch Optimizer Service
=====================================

Tests for intelligent batch processing, resource allocation,
and cost optimization algorithms.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from pydantic import ValidationError

from app.schemas.batch import (
    BatchOptimizationRequest, BatchOptimizationResult, BatchScanJob,
    BatchType, BatchStatus, ResourceProfile, ModuleProfile,
    ModuleResourceScaling, ResourceRange
)
from app.services.batch_optimizer import BatchOptimizer

class TestBatchOptimizer:
    """Test suite for BatchOptimizer service."""
    
    @pytest.fixture
    def batch_optimizer(self):
        """Create a BatchOptimizer instance for testing."""
        optimizer = BatchOptimizer()
        optimizer.supabase = Mock()  # Mock Supabase client
        return optimizer
    
    @pytest.fixture
    def sample_subfinder_profile(self):
        """Sample subfinder module profile for testing."""
        return ModuleProfile(
            id=uuid.uuid4(),
            module_name="subfinder",
            version="1.0",
            supports_batching=True,
            max_batch_size=200,
            resource_scaling=ModuleResourceScaling(
                domain_count_ranges=[
                    ResourceRange(min_domains=1, max_domains=10, cpu=256, memory=512, description="Small batch"),
                    ResourceRange(min_domains=11, max_domains=50, cpu=512, memory=1024, description="Medium batch"),
                    ResourceRange(min_domains=51, max_domains=200, cpu=1024, memory=2048, description="Large batch")
                ],
                scaling_notes="Subfinder scales linearly"
            ),
            estimated_duration_per_domain=90,
            task_definition_template="neobotnet-v2-dev-subfinder",
            container_name="subfinder",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_request_small(self):
        """Small optimization request (20 domains)."""
        return BatchOptimizationRequest(
            asset_scan_requests=[
                {
                    "asset_id": str(uuid.uuid4()),
                    "domains": ["example1.com", "example2.com", "test1.com"],
                    "asset_scan_id": str(uuid.uuid4())
                },
                {
                    "asset_id": str(uuid.uuid4()),
                    "domains": ["sample1.com", "sample2.com"],
                    "asset_scan_id": str(uuid.uuid4())
                }
            ],
            modules=["subfinder"],
            priority=1,
            user_id=uuid.uuid4()
        )
    
    @pytest.fixture
    def sample_request_large(self):
        """Large optimization request (600 domains)."""
        asset_scan_requests = []
        
        # Create 20 assets with 30 domains each = 600 total domains
        for i in range(20):
            domains = [f"domain{j}-asset{i}.com" for j in range(30)]
            asset_scan_requests.append({
                "asset_id": str(uuid.uuid4()),
                "domains": domains,
                "asset_scan_id": str(uuid.uuid4())
            })
        
        return BatchOptimizationRequest(
            asset_scan_requests=asset_scan_requests,
            modules=["subfinder"],
            priority=1,
            user_id=uuid.uuid4()
        )

    @pytest.mark.asyncio
    async def test_small_batch_optimization(self, batch_optimizer, sample_request_small, sample_subfinder_profile):
        """Test optimization with small number of domains."""
        
        # Mock module profile lookup
        batch_optimizer._get_module_profile = AsyncMock(return_value=sample_subfinder_profile)
        
        # Mock resource calculation
        batch_optimizer._calculate_batch_resources = AsyncMock(return_value=ResourceProfile(
            cpu=512,
            memory=1024,
            estimated_duration_minutes=8,
            description="Medium batch for 5 domains",
            domain_count=5,
            module_name="subfinder"
        ))
        
        result = await batch_optimizer.optimize_scans(sample_request_small)
        
        # Assertions
        assert isinstance(result, BatchOptimizationResult)
        assert result.total_domains == 5  # 3 + 2 domains
        assert result.total_batches == 1  # Should fit in one batch
        assert result.estimated_cost_savings_percent > 0
        assert len(result.batch_jobs) == 1
        
        # Check batch job details
        batch_job = result.batch_jobs[0]
        assert batch_job.total_domains == 5
        assert batch_job.module == "subfinder"
        assert batch_job.batch_type == BatchType.MULTI_ASSET  # Multiple assets
        assert batch_job.allocated_cpu == 512
        assert batch_job.allocated_memory == 1024

    @pytest.mark.asyncio 
    async def test_large_batch_optimization(self, batch_optimizer, sample_request_large, sample_subfinder_profile):
        """Test optimization with large number of domains (600)."""
        
        # Mock module profile lookup
        batch_optimizer._get_module_profile = AsyncMock(return_value=sample_subfinder_profile)
        
        # Mock resource calculation - return different resources for different batch sizes
        async def mock_resource_calc(module_name, domain_count):
            if domain_count <= 50:
                return ResourceProfile(
                    cpu=512, memory=1024, estimated_duration_minutes=domain_count * 1.5,
                    description=f"Medium batch for {domain_count} domains",
                    domain_count=domain_count, module_name=module_name
                )
            else:
                return ResourceProfile(
                    cpu=1024, memory=2048, estimated_duration_minutes=domain_count * 1.5,
                    description=f"Large batch for {domain_count} domains", 
                    domain_count=domain_count, module_name=module_name
                )
        
        batch_optimizer._calculate_batch_resources = AsyncMock(side_effect=mock_resource_calc)
        
        result = await batch_optimizer.optimize_scans(sample_request_large)
        
        # Assertions for large batch
        assert result.total_domains == 600
        assert result.total_batches == 3  # 600 domains / 200 max batch size = 3 batches
        assert result.estimated_cost_savings_percent > 40  # Should have significant savings
        assert len(result.batch_jobs) == 3
        
        # Check all batches use large resource profile
        for batch_job in result.batch_jobs:
            assert batch_job.total_domains == 200  # Max batch size
            assert batch_job.allocated_cpu == 1024  # Large batch CPU
            assert batch_job.allocated_memory == 2048  # Large batch memory
            assert batch_job.batch_type == BatchType.MULTI_ASSET

    # ============================================================================
    # CLEANUP NOTE (2025-10-06): Multi-module test commented out
    # ============================================================================
    # This test used cloud_ssl as a second module to test multi-module optimization.
    # Re-enable when a second module (DNS, HTTPX, etc.) is implemented.
    # ============================================================================
    
    # @pytest.mark.asyncio
    # async def test_multi_module_optimization(self, batch_optimizer, sample_request_small, sample_subfinder_profile):
    #     """Test optimization with multiple modules."""
    #     
    #     # Modify request to include multiple modules
    #     sample_request_small.modules = ["subfinder", "second_module"]
    #     
    #     # Mock module profiles
    #     async def mock_get_profile(module_name):
    #         if module_name == "subfinder":
    #             return sample_subfinder_profile
    #         else:
    #             # second_module doesn't support batching
    #             second_profile = sample_subfinder_profile.copy()
    #             second_profile.module_name = "second_module"
    #             second_profile.supports_batching = False
    #             second_profile.max_batch_size = 1
    #             return second_profile
    #     
    #     batch_optimizer._get_module_profile = AsyncMock(side_effect=mock_get_profile)
    #     batch_optimizer._calculate_batch_resources = AsyncMock(return_value=ResourceProfile(
    #         cpu=512, memory=1024, estimated_duration_minutes=5,
    #         description="Test resource profile", domain_count=5, module_name="subfinder"
    #     ))
    #     
    #     result = await batch_optimizer.optimize_scans(sample_request_small)
    #     
    #     # Should create batches for both modules
    #     assert result.total_batches == 6  # 1 subfinder batch + 5 individual second_module batches
    #     
    #     # Check module distribution
    #     subfinder_batches = [b for b in result.batch_jobs if b.module == "subfinder"]
    #     second_batches = [b for b in result.batch_jobs if b.module == "second_module"]
    #     
    #     assert len(subfinder_batches) == 1  # One optimized batch
    #     assert len(second_batches) == 5  # Five individual batches
    #     assert subfinder_batches[0].total_domains == 5
    #     assert all(batch.total_domains == 1 for batch in second_batches)

    def test_cost_savings_calculation(self, batch_optimizer):
        """Test cost savings calculation logic."""
        
        # Test small optimization (≤20 domains cap at 50%)
        savings_small = batch_optimizer._calculate_cost_savings(
            total_domains=10, total_batches=1, modules=["subfinder"]
        )
        assert 0 <= savings_small <= 50  # Small batches capped at 50%
        
        # Test large optimization (>100 domains cap at 80%)
        savings_large = batch_optimizer._calculate_cost_savings(
            total_domains=600, total_batches=3, modules=["subfinder"]
        )
        assert savings_large > savings_small  # Larger batches should save more
        assert savings_large <= 80  # Large batches capped at 80%
        
        # CLEANUP NOTE (2025-10-06): Multi-module cost test commented out
        # Re-enable when second module is implemented
        # Test multi-module scenario
        # savings_multi = batch_optimizer._calculate_cost_savings(
        #     total_domains=100, total_batches=5, modules=["subfinder", "second_module"]
        # )
        # assert savings_multi > 0  # Should still have savings

    def test_optimization_strategy_descriptions(self, batch_optimizer):
        """Test strategy description generation."""
        
        # Single batch strategy
        strategy_single = batch_optimizer._get_optimization_strategy(
            total_domains=50, total_batches=1, modules=["subfinder"]
        )
        assert "Single optimized batch" in strategy_single
        
        # Small scale strategy
        strategy_small = batch_optimizer._get_optimization_strategy(
            total_domains=30, total_batches=2, modules=["subfinder"]
        )
        assert "Small-scale optimization" in strategy_small
        
        # Medium scale strategy
        strategy_medium = batch_optimizer._get_optimization_strategy(
            total_domains=150, total_batches=3, modules=["subfinder"]
        )
        assert "Medium-scale optimization" in strategy_medium
        
        # Large scale strategy
        strategy_large = batch_optimizer._get_optimization_strategy(
            total_domains=600, total_batches=5, modules=["subfinder"]
        )
        assert "Large-scale optimization" in strategy_large

    @pytest.mark.asyncio
    async def test_domain_asset_mapping_preservation(self, batch_optimizer, sample_request_small, sample_subfinder_profile):
        """Test that domain to asset scan mapping is preserved correctly."""
        
        batch_optimizer._get_module_profile = AsyncMock(return_value=sample_subfinder_profile)
        batch_optimizer._calculate_batch_resources = AsyncMock(return_value=ResourceProfile(
            cpu=512, memory=1024, estimated_duration_minutes=8,
            description="Test profile", domain_count=5, module_name="subfinder"
        ))
        
        result = await batch_optimizer.optimize_scans(sample_request_small)
        
        # Check that asset scan mapping is preserved
        batch_job = result.batch_jobs[0]
        assert len(batch_job.asset_scan_mapping) == 5  # All domains mapped
        
        # Verify that all original domains are present
        expected_domains = {"example1.com", "example2.com", "test1.com", "sample1.com", "sample2.com"}
        actual_domains = set(batch_job.batch_domains)
        assert actual_domains == expected_domains
        
        # Verify that each domain has an asset scan ID
        for domain in batch_job.batch_domains:
            assert domain in batch_job.asset_scan_mapping
            assert batch_job.asset_scan_mapping[domain] is not None

    @pytest.mark.asyncio
    async def test_empty_request_handling(self, batch_optimizer):
        """Test handling of empty or invalid requests."""
        
        # Test that empty asset scan requests are prevented by validation
        with pytest.raises(ValidationError):  # Should raise Pydantic ValidationError
            BatchOptimizationRequest(
                asset_scan_requests=[],
                modules=["subfinder"],
                priority=1,
                user_id=uuid.uuid4()
            )
        
        # Test with asset scans that have no domains
        no_domains_request = BatchOptimizationRequest(
            asset_scan_requests=[
                {
                    "asset_id": str(uuid.uuid4()),
                    "domains": [],
                    "asset_scan_id": str(uuid.uuid4())
                }
            ],
            modules=["subfinder"],
            priority=1,
            user_id=uuid.uuid4()
        )
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await batch_optimizer.optimize_scans(no_domains_request)

    @pytest.mark.asyncio
    async def test_module_profile_caching(self, batch_optimizer, sample_subfinder_profile):
        """Test that module profiles are cached properly."""
        
        # Mock the database query
        mock_response = Mock()
        mock_response.data = [{
            "id": str(sample_subfinder_profile.id),
            "module_name": "subfinder",
            "version": "1.0",
            "supports_batching": True,
            "max_batch_size": 200,
            "resource_scaling": sample_subfinder_profile.resource_scaling.dict(),
            "estimated_duration_per_domain": 90,
            "task_definition_template": "neobotnet-v2-dev-subfinder",
            "container_name": "subfinder",
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }]
        
        batch_optimizer.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        # First call should query database
        profile1 = await batch_optimizer._get_module_profile("subfinder")
        assert profile1.module_name == "subfinder"
        
        # Second call should use cache
        profile2 = await batch_optimizer._get_module_profile("subfinder")
        assert profile2.module_name == "subfinder"
        
        # Verify database was only called once
        batch_optimizer.supabase.table.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__])
