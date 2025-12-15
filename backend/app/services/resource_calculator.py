"""
Module Resource Calculator for Dynamic ECS Allocation
==================================================

Intelligent resource calculation that optimizes ECS task allocation
based on workload size, module capabilities, and cost efficiency.

Key Features:
• Dynamic CPU/memory scaling based on domain count
• Cost optimization through efficient resource utilization  
• Module-aware resource profiles with safety limits
• Integration with database-driven resource scaling
"""

import uuid
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging

from ..core.supabase_client import supabase_client
from ..schemas.batch import ResourceProfile, ModuleProfile
from .module_registry import module_registry

logger = logging.getLogger(__name__)

@dataclass
class CostEstimate:
    """Cost estimation for resource allocation."""
    cpu_cost_per_hour: float
    memory_cost_per_hour: float
    total_cost_per_hour: float
    estimated_total_cost: float
    estimated_duration_hours: float
    cost_breakdown: Dict[str, float]
    
    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

@dataclass
class ResourceAllocation:
    """Complete resource allocation with cost analysis."""
    cpu: int  # CPU units (256 = 0.25 vCPU)
    memory: int  # Memory in MB
    estimated_duration_minutes: int
    cost_estimate: CostEstimate
    scaling_reasoning: str
    module_name: str
    domain_count: int
    optimization_applied: str
    
    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

class ModuleResourceCalculator:
    """
    Intelligent resource calculator for scan modules.
    
    This class provides dynamic resource allocation that optimizes
    for both performance and cost based on workload characteristics.
    """
    
    # AWS Fargate pricing (as of 2024, us-east-1)
    FARGATE_CPU_COST_PER_VCPU_HOUR = 0.04048
    FARGATE_MEMORY_COST_PER_GB_HOUR = 0.004445
    
    # Resource limits to prevent runaway costs
    MAX_CPU_UNITS = 4096  # 4 vCPUs
    MAX_MEMORY_MB = 8192  # 8 GB
    MIN_CPU_UNITS = 256   # 0.25 vCPU
    MIN_MEMORY_MB = 512   # 512 MB
    
    # AWS Fargate valid CPU/memory combinations
    FARGATE_CONFIGURATIONS = {
        256: [512, 1024, 2048],  # 0.25 vCPU
        512: [1024, 1536, 2048, 3072, 4096],  # 0.5 vCPU
        1024: [2048, 3072, 4096, 5120, 6144, 7168, 8192],  # 1 vCPU
        2048: [4096, 5120, 6144, 7168, 8192, 9216, 10240, 11264, 12288, 13312, 14336, 15360, 16384],  # 2 vCPU
        4096: [8192, 9216, 10240, 11264, 12288, 13312, 14336, 15360, 16384, 17408, 18432, 19456, 20480, 21504, 22528, 23552, 24576, 25600, 26624, 27648, 28672, 29696, 30720]  # 4 vCPU
    }
    
    def __init__(self):
        self.supabase = supabase_client.service_client
        self._module_cache: Dict[str, ModuleProfile] = {}
    
    def _snap_to_fargate_configuration(self, cpu: int, memory: int) -> Tuple[int, int]:
        """
        Snap calculated CPU/memory to valid AWS Fargate configurations.
        
        This ensures all resource allocations work with Fargate's predefined
        CPU/memory combinations, preventing deployment failures.
        
        Args:
            cpu: Calculated CPU units
            memory: Calculated memory in MB
            
        Returns:
            Tuple of (valid_cpu, valid_memory) that Fargate supports
        """
        # Find the best CPU match
        available_cpus = sorted(self.FARGATE_CONFIGURATIONS.keys())
        
        # If calculated CPU is below minimum, use minimum
        if cpu < available_cpus[0]:
            target_cpu = available_cpus[0]
        else:
            # Find the smallest valid CPU that can accommodate our needs
            target_cpu = None
            for fargate_cpu in available_cpus:
                if cpu <= fargate_cpu:
                    target_cpu = fargate_cpu
                    break
            
            # If no valid CPU found (above maximum), use maximum
            if target_cpu is None:
                target_cpu = available_cpus[-1]
        
        # Find the best memory match for the chosen CPU
        available_memories = self.FARGATE_CONFIGURATIONS[target_cpu]
        
        # If calculated memory is below minimum for this CPU, use minimum
        if memory < available_memories[0]:
            target_memory = available_memories[0]
        else:
            # Find the smallest valid memory that can accommodate our needs
            target_memory = None
            for fargate_memory in available_memories:
                if memory <= fargate_memory:
                    target_memory = fargate_memory
                    break
            
            # If no valid memory found (above maximum), use maximum
            if target_memory is None:
                target_memory = available_memories[-1]
        
        logger.info(f"Fargate config snap: {cpu}CPU/{memory}MB → {target_cpu}CPU/{target_memory}MB")
        return target_cpu, target_memory
        
    async def calculate_resources(
        self, 
        module_name: str, 
        domain_count: int,
        priority: int = 1,
        cost_optimization: bool = True
    ) -> ResourceAllocation:
        """
        Calculate optimal resources for a module and domain count.
        
        Args:
            module_name: Name of the scan module
            domain_count: Number of domains to process
            priority: Priority level (1=highest, 5=lowest)
            cost_optimization: Whether to apply cost optimizations
            
        Returns:
            ResourceAllocation with optimized CPU, memory, and cost analysis
        """
        try:
            logger.info(f"Calculating resources for {module_name} with {domain_count} domains")
            
            # Get base resource profile from database
            base_profile = await self._get_base_resource_profile(module_name, domain_count)
            
            # Apply optimization strategies
            optimized_resources = await self._apply_optimization_strategies(
                base_profile, module_name, domain_count, priority, cost_optimization
            )
            
            # Calculate cost estimate
            cost_estimate = self._calculate_cost_estimate(
                optimized_resources['cpu'],
                optimized_resources['memory'], 
                optimized_resources['duration_minutes']
            )
            
            # Create resource allocation
            allocation = ResourceAllocation(
                cpu=optimized_resources['cpu'],
                memory=optimized_resources['memory'],
                estimated_duration_minutes=optimized_resources['duration_minutes'],
                cost_estimate=cost_estimate,
                scaling_reasoning=optimized_resources['reasoning'],
                module_name=module_name,
                domain_count=domain_count,
                optimization_applied=optimized_resources['optimization']
            )
            
            logger.info(f"Resource allocation complete: {allocation.cpu} CPU, {allocation.memory}MB RAM, ${allocation.cost_estimate.estimated_total_cost:.4f}")
            return allocation
            
        except Exception as e:
            logger.error(f"Resource calculation failed for {module_name}/{domain_count}: {str(e)}")
            # Return fallback allocation
            return self._get_fallback_allocation(module_name, domain_count)
    
    async def _get_base_resource_profile(self, module_name: str, domain_count: int) -> Dict[str, Any]:
        """Get base resource profile using database function."""
        
        try:
            response = self.supabase.rpc(
                "calculate_module_resources",
                {"p_module_name": module_name, "p_domain_count": domain_count}
            ).execute()
            
            if not response.data:
                raise Exception("No resource profile returned from database")
            
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to get base resource profile: {str(e)}")
            # Fallback to basic calculation
            return {
                "cpu": min(256 * domain_count, self.MAX_CPU_UNITS),
                "memory": min(512 * domain_count, self.MAX_MEMORY_MB),
                "estimated_duration_minutes": domain_count * 2,
                "description": f"Fallback allocation for {domain_count} domains",
                "module_name": module_name,
                "domain_count": domain_count
            }
    
    async def _apply_optimization_strategies(
        self, 
        base_profile: Dict[str, Any], 
        module_name: str, 
        domain_count: int,
        priority: int,
        cost_optimization: bool
    ) -> Dict[str, Any]:
        """Apply various optimization strategies to base resource profile."""
        
        cpu = base_profile["cpu"]
        memory = base_profile["memory"]
        duration = base_profile["estimated_duration_minutes"]
        
        optimizations_applied = []
        reasoning_parts = []
        
        # Strategy 1: Priority-based scaling
        if priority <= 2:  # High priority
            cpu = min(int(cpu * 1.25), self.MAX_CPU_UNITS)
            memory = min(int(memory * 1.25), self.MAX_MEMORY_MB)
            duration = max(int(duration * 0.8), 1)  # Faster completion
            optimizations_applied.append("high_priority_boost")
            reasoning_parts.append("High priority: +25% resources for faster completion")
        elif priority >= 4:  # Low priority
            cpu = max(int(cpu * 0.8), self.MIN_CPU_UNITS)
            memory = max(int(memory * 0.8), self.MIN_MEMORY_MB)
            duration = int(duration * 1.2)  # Slower but cheaper
            optimizations_applied.append("low_priority_reduction")
            reasoning_parts.append("Low priority: -20% resources for cost savings")
        
        # Strategy 2: Batch size optimization
        if domain_count >= 100:
            # Large batches get better resource efficiency
            cpu_efficiency = min(1.15, 1 + (domain_count - 100) * 0.001)
            cpu = min(int(cpu * cpu_efficiency), self.MAX_CPU_UNITS)
            optimizations_applied.append("large_batch_efficiency")
            reasoning_parts.append(f"Large batch efficiency: +{int((cpu_efficiency-1)*100)}% CPU for {domain_count} domains")
        
        # Strategy 3: Module-specific optimizations (database-driven)
        # Load optimization hints from module profile (eliminates hardcoded logic)
        module_profile = await module_registry.get_module(module_name)
        if module_profile and module_profile.optimization_hints:
            hints = module_profile.optimization_hints
            
            # Apply memory multiplier if configured
            memory_multiplier = hints.get("memory_multiplier")
            memory_threshold = hints.get("memory_threshold_domains", 0)
            
            if memory_multiplier and domain_count > memory_threshold:
                old_memory = memory
                memory = min(int(memory * memory_multiplier), self.MAX_MEMORY_MB)
                optimization_name = hints.get("optimization_name", f"{module_name}_optimization")
                optimizations_applied.append(optimization_name)
                
                # Use custom reasoning message or generate one
                custom_reason = hints.get("reason")
                if custom_reason:
                    reasoning_parts.append(custom_reason)
                else:
                    reasoning_parts.append(
                        f"{module_name.capitalize()} optimization: "
                        f"+{int((memory_multiplier-1)*100)}% memory "
                        f"(from {old_memory}MB to {memory}MB)"
                    )
        
        # Strategy 4: Cost optimization
        if cost_optimization and domain_count < 10:
            # Small batches: minimize resources to reduce cost
            cpu = max(self.MIN_CPU_UNITS, int(cpu * 0.9))
            memory = max(self.MIN_MEMORY_MB, int(memory * 0.9))
            optimizations_applied.append("small_batch_cost_optimization")
            reasoning_parts.append("Small batch cost optimization: minimal resources")
        
        # Strategy 5: Safety limits
        cpu = max(self.MIN_CPU_UNITS, min(cpu, self.MAX_CPU_UNITS))
        memory = max(self.MIN_MEMORY_MB, min(memory, self.MAX_MEMORY_MB))
        
        # Strategy 6: Fargate configuration validation
        original_cpu, original_memory = cpu, memory
        cpu, memory = self._snap_to_fargate_configuration(cpu, memory)
        
        if cpu != original_cpu or memory != original_memory:
            optimizations_applied.append("fargate_config_validation")
            reasoning_parts.append(f"Fargate validation: {original_cpu}CPU/{original_memory}MB → {cpu}CPU/{memory}MB")
        
        return {
            "cpu": cpu,
            "memory": memory,
            "duration_minutes": duration,
            "reasoning": "; ".join(reasoning_parts) or base_profile.get("description", "Standard allocation"),
            "optimization": ", ".join(optimizations_applied) or "none"
        }
    
    def _calculate_cost_estimate(self, cpu: int, memory: int, duration_minutes: int) -> CostEstimate:
        """Calculate detailed cost estimate for resource allocation."""
        
        # Convert to standard units
        vcpus = cpu / 1024  # Convert CPU units to vCPUs
        gb_memory = memory / 1024  # Convert MB to GB
        duration_hours = duration_minutes / 60
        
        # Calculate costs
        cpu_cost_per_hour = vcpus * self.FARGATE_CPU_COST_PER_VCPU_HOUR
        memory_cost_per_hour = gb_memory * self.FARGATE_MEMORY_COST_PER_GB_HOUR
        total_cost_per_hour = cpu_cost_per_hour + memory_cost_per_hour
        
        estimated_total_cost = total_cost_per_hour * duration_hours
        
        return CostEstimate(
            cpu_cost_per_hour=cpu_cost_per_hour,
            memory_cost_per_hour=memory_cost_per_hour,
            total_cost_per_hour=total_cost_per_hour,
            estimated_total_cost=estimated_total_cost,
            estimated_duration_hours=duration_hours,
            cost_breakdown={
                "cpu_cost": cpu_cost_per_hour * duration_hours,
                "memory_cost": memory_cost_per_hour * duration_hours,
                "total_cost": estimated_total_cost
            }
        )
    
    def _get_fallback_allocation(self, module_name: str, domain_count: int) -> ResourceAllocation:
        """Get fallback resource allocation when calculation fails."""
        
        # Conservative fallback allocation
        cpu = max(self.MIN_CPU_UNITS, min(256 * min(domain_count, 4), self.MAX_CPU_UNITS))
        memory = max(self.MIN_MEMORY_MB, min(512 * min(domain_count, 4), self.MAX_MEMORY_MB))
        duration = max(5, domain_count * 2)
        
        # Ensure fallback allocation is Fargate-compatible
        cpu, memory = self._snap_to_fargate_configuration(cpu, memory)
        
        cost_estimate = self._calculate_cost_estimate(cpu, memory, duration)
        
        return ResourceAllocation(
            cpu=cpu,
            memory=memory,
            estimated_duration_minutes=duration,
            cost_estimate=cost_estimate,
            scaling_reasoning="Fallback allocation due to calculation error",
            module_name=module_name,
            domain_count=domain_count,
            optimization_applied="fallback"
        )
    
    async def calculate_batch_comparison(
        self, 
        individual_allocations: List[Tuple[str, int]], 
        batch_allocation: Tuple[str, int]
    ) -> Dict[str, Any]:
        """
        Compare cost and performance of individual vs batch processing.
        
        Args:
            individual_allocations: List of (module, domain_count) for individual processing
            batch_allocation: Single (module, total_domain_count) for batch processing
            
        Returns:
            Comparison analysis with cost savings and performance impact
        """
        
        # Calculate individual processing costs
        individual_costs = []
        total_individual_cost = 0
        total_individual_duration = 0
        
        for module, domain_count in individual_allocations:
            allocation = await self.calculate_resources(module, domain_count)
            individual_costs.append(allocation)
            total_individual_cost += allocation.cost_estimate.estimated_total_cost
            total_individual_duration = max(total_individual_duration, allocation.estimated_duration_minutes)
        
        # Calculate batch processing cost
        batch_module, batch_domain_count = batch_allocation
        batch_cost = await self.calculate_resources(batch_module, batch_domain_count)
        
        # Calculate savings
        cost_savings = total_individual_cost - batch_cost.cost_estimate.estimated_total_cost
        cost_savings_percent = (cost_savings / total_individual_cost) * 100 if total_individual_cost > 0 else 0
        
        time_savings = total_individual_duration - batch_cost.estimated_duration_minutes
        time_savings_percent = (time_savings / total_individual_duration) * 100 if total_individual_duration > 0 else 0
        
        return {
            "individual_processing": {
                "total_cost": total_individual_cost,
                "total_duration_minutes": total_individual_duration,
                "job_count": len(individual_allocations),
                "allocations": [allocation.dict() for allocation in individual_costs]
            },
            "batch_processing": {
                "total_cost": batch_cost.cost_estimate.estimated_total_cost,
                "total_duration_minutes": batch_cost.estimated_duration_minutes,
                "job_count": 1,
                "allocation": batch_cost.dict()
            },
            "savings": {
                "cost_savings_dollars": cost_savings,
                "cost_savings_percent": cost_savings_percent,
                "time_savings_minutes": time_savings,
                "time_savings_percent": time_savings_percent,
                "job_reduction": len(individual_allocations) - 1
            },
            "recommendation": "batch" if cost_savings_percent > 10 else "individual"
        }

# Global instance
resource_calculator = ModuleResourceCalculator()
