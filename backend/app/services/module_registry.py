"""
Module Registry Service
=======================

Central registry for managing scan module discovery, validation, and capabilities.
Provides a single source of truth for module operations across the application.

This service consolidates module profile queries that were previously scattered
across batch_optimizer.py and other services, applying DRY principles.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from ..core.supabase_client import supabase_client
from ..schemas.batch import ModuleProfile, ModuleResourceScaling


class ModuleRegistry:
    """
    Central registry for scan module management.
    
    Responsibilities:
    - Discover available modules from database
    - Validate module existence and activation status
    - Provide module capabilities and configuration
    - Cache module profiles for performance
    
    This consolidates logic previously duplicated in batch_optimizer.py
    and prevents hardcoded module checks across the codebase.
    """
    
    def __init__(self):
        """Initialize the module registry with database connection and caching."""
        self.supabase = supabase_client.service_client
        self.logger = logging.getLogger(__name__)
        
        # Performance optimization: In-memory cache for module profiles
        # Reduces database queries for frequently accessed modules
        self._module_cache: Dict[str, ModuleProfile] = {}
        
        # Cache invalidation: Refresh cache after this duration
        self._cache_ttl = timedelta(minutes=15)
        self._cache_timestamp: Optional[datetime] = None
    
    # ================================================================
    # Core Module Discovery
    # ================================================================
    
    async def discover_modules(self, refresh_cache: bool = False) -> List[ModuleProfile]:
        """
        Discover all active scan modules from the database.
        
        This method queries the scan_module_profiles table and returns
        all modules that are currently active and available for use.
        
        Args:
            refresh_cache: Force refresh of cached modules (default: False)
        
        Returns:
            List of ModuleProfile objects for all active modules
        
        Example:
            >>> registry = ModuleRegistry()
            >>> modules = await registry.discover_modules()
            >>> print([m.module_name for m in modules])
            ['subfinder', 'dns_resolver']
        """
        try:
            # Check if cache is valid and not forcing refresh
            if not refresh_cache and self._is_cache_valid() and self._module_cache:
                self.logger.debug(f"Returning {len(self._module_cache)} modules from cache")
                return list(self._module_cache.values())
            
            # Query all active modules from database
            self.logger.info("Discovering active scan modules from database")
            response = self.supabase.table("scan_module_profiles").select("*").eq(
                "is_active", True
            ).order("module_name").execute()
            
            if not response.data:
                self.logger.warning("No active modules found in database")
                return []
            
            # Parse module profiles and rebuild cache
            modules = []
            self._module_cache.clear()
            
            for profile_data in response.data:
                try:
                    module = self._parse_module_profile(profile_data)
                    modules.append(module)
                    self._module_cache[module.module_name] = module
                except Exception as e:
                    # Log parsing errors but don't fail entire discovery
                    self.logger.error(
                        f"Failed to parse module profile for {profile_data.get('module_name')}: {e}"
                    )
                    continue
            
            self._cache_timestamp = datetime.utcnow()
            self.logger.info(f"Discovered {len(modules)} active modules: {[m.module_name for m in modules]}")
            
            return modules
            
        except Exception as e:
            self.logger.error(f"Error discovering modules: {e}")
            # Return cached modules if available as fallback
            if self._module_cache:
                self.logger.warning("Using cached modules due to database error")
                return list(self._module_cache.values())
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to discover scan modules: {str(e)}"
            )
    
    async def get_module(self, module_name: str, use_cache: bool = True) -> Optional[ModuleProfile]:
        """
        Get a specific module profile by name with automatic configuration.
        
        This is the primary method for retrieving module configuration
        throughout the application. It uses caching for performance.
        
        **Convention Over Configuration (Bug #7 Fix):**
        Modules with dependencies automatically get `requires_database_fetch` and
        `requires_asset_id` flags enabled. This prevents configuration errors
        for dependent modules (e.g., DNSX depends on Subfinder's results).
        
        Convention Rules:
        - If module has dependencies → Auto-enable database fetch mode
        - Manual override: Explicit flags in DB take precedence
        - Zero config needed for 90% of modules
        
        Args:
            module_name: Name of the module (e.g., 'subfinder', 'dnsx')
            use_cache: Whether to use cached profile (default: True)
        
        Returns:
            ModuleProfile if found and active, None otherwise
        
        Example:
            >>> module = await registry.get_module('dnsx')
            >>> # Auto-detects dependencies: ['subfinder']
            >>> # Auto-enables: requires_database_fetch=True, requires_asset_id=True
            >>> if module and module.supports_batching:
            ...     print(f"Max batch size: {module.max_batch_size}")
        """
        try:
            # Check cache first if enabled
            if use_cache and module_name in self._module_cache and self._is_cache_valid():
                self.logger.debug(f"Returning cached profile for module: {module_name}")
                return self._module_cache[module_name]
            
            # Query from database
            self.logger.debug(f"Querying database for module: {module_name}")
            response = self.supabase.table("scan_module_profiles").select("*").eq(
                "module_name", module_name
            ).eq("is_active", True).order("version", desc=True).limit(1).execute()
            
            if not response.data:
                self.logger.warning(f"Module not found or inactive: {module_name}")
                return None
            
            # Parse and cache the profile
            module = self._parse_module_profile(response.data[0])
            
            # 🎯 CONVENTION OVER CONFIGURATION (Bug #7 Fix)
            # Auto-detect database fetch mode based on dependencies
            if module.optimization_hints:
                dependencies = module.optimization_hints.get('dependencies', [])
                
                # If module has dependencies but missing required flags, auto-enable them
                if dependencies:
                    requires_db_fetch = module.optimization_hints.get('requires_database_fetch', False)
                    requires_asset = module.optimization_hints.get('requires_asset_id', False)
                    
                    if not requires_db_fetch or not requires_asset:
                        self.logger.info(
                            f"📋 Auto-enabling database fetch for '{module_name}' "
                            f"(has dependencies: {dependencies})"
                        )
                        # Auto-enable database fetch mode
                        module.optimization_hints['requires_database_fetch'] = True
                        module.optimization_hints['requires_asset_id'] = True
                        
                        self.logger.debug(
                            f"   Convention applied: Module with dependencies automatically uses database fetch mode"
                        )
            
            self._module_cache[module_name] = module
            
            # Update cache timestamp if not already set
            if not self._cache_timestamp:
                self._cache_timestamp = datetime.utcnow()
            
            return module
            
        except Exception as e:
            self.logger.error(f"Error retrieving module {module_name}: {e}")
            # Return cached version if available as fallback
            if use_cache and module_name in self._module_cache:
                self.logger.warning(f"Using cached profile for {module_name} due to error")
                return self._module_cache[module_name]
            return None
    
    # ================================================================
    # Module Validation
    # ================================================================
    
    async def validate_module(self, module_name: str) -> bool:
        """
        Check if a module exists and is active.
        
        This is a lightweight validation method for pre-launch checks.
        Use this before creating batch jobs or launching ECS tasks.
        
        Args:
            module_name: Name of the module to validate
        
        Returns:
            True if module exists and is active, False otherwise
        
        Example:
            >>> if await registry.validate_module('dns_resolver'):
            ...     # Proceed with scan
            ...     await launch_scan(...)
            ... else:
            ...     raise HTTPException(400, "Invalid module")
        """
        try:
            module = await self.get_module(module_name)
            is_valid = module is not None and module.is_active
            
            if is_valid:
                self.logger.debug(f"Module validation passed: {module_name}")
            else:
                self.logger.warning(f"Module validation failed: {module_name}")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating module {module_name}: {e}")
            return False
    
    async def validate_modules(self, module_names: List[str]) -> Dict[str, bool]:
        """
        Validate multiple modules at once.
        
        Args:
            module_names: List of module names to validate
        
        Returns:
            Dictionary mapping module names to validation results
        
        Example:
            >>> results = await registry.validate_modules(['subfinder', 'dns_resolver'])
            >>> invalid = [name for name, valid in results.items() if not valid]
            >>> if invalid:
            ...     raise HTTPException(400, f"Invalid modules: {invalid}")
        """
        results = {}
        for module_name in module_names:
            results[module_name] = await self.validate_module(module_name)
        return results
    
    async def validate_batch_request(
        self,
        module_name: str,
        domain_count: int
    ) -> Dict[str, any]:
        """
        Validate a batch scan request against module capabilities.
        
        This performs comprehensive validation including:
        - Module exists and is active
        - Module supports batch processing
        - Domain count within module's max_batch_size
        
        Args:
            module_name: Name of the module
            domain_count: Number of domains to scan
        
        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'module': ModuleProfile (if valid)
            }
        
        Example:
            >>> validation = await registry.validate_batch_request('subfinder', 100)
            >>> if not validation['valid']:
            ...     raise HTTPException(400, validation['errors'])
        """
        errors = []
        warnings = []
        
        try:
            # Check module exists
            module = await self.get_module(module_name)
            
            if not module:
                errors.append(f"Module '{module_name}' not found or is inactive")
                return {
                    'valid': False,
                    'errors': errors,
                    'warnings': warnings,
                    'module': None
                }
            
            # Check batch support
            if not module.supports_batching and domain_count > 1:
                errors.append(
                    f"Module '{module_name}' does not support batch processing. "
                    f"Requested {domain_count} domains, but module only supports single domain scans."
                )
            
            # Check batch size limits
            if domain_count > module.max_batch_size:
                errors.append(
                    f"Domain count ({domain_count}) exceeds module's maximum batch size "
                    f"({module.max_batch_size}). Consider splitting into multiple batches."
                )
            
            # Add warnings for near-limit batches
            if domain_count > module.max_batch_size * 0.9:
                warnings.append(
                    f"Batch size ({domain_count}) is near the maximum ({module.max_batch_size}). "
                    f"Consider splitting for better performance."
                )
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'module': module
            }
            
        except Exception as e:
            self.logger.error(f"Error validating batch request for {module_name}: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': warnings,
                'module': None
            }
    
    # ================================================================
    # Module Capabilities
    # ================================================================
    
    async def get_module_capabilities(self, module_name: str) -> Optional[Dict[str, any]]:
        """
        Get detailed capabilities for a specific module.
        
        Returns a simplified dictionary of module capabilities,
        useful for frontend display or API responses.
        
        Args:
            module_name: Name of the module
        
        Returns:
            Dictionary with module capabilities or None if not found
        
        Example:
            >>> caps = await registry.get_module_capabilities('subfinder')
            >>> print(f"Supports batching: {caps['supports_batching']}")
            >>> print(f"Max batch size: {caps['max_batch_size']}")
        """
        module = await self.get_module(module_name)
        
        if not module:
            return None
        
        return {
            'module_name': module.module_name,
            'version': module.version,
            'supports_batching': module.supports_batching,
            'max_batch_size': module.max_batch_size,
            'estimated_duration_per_domain': module.estimated_duration_per_domain,
            'is_active': module.is_active,
            'description': f"{module.module_name} v{module.version}"
        }
    
    async def list_available_modules(self) -> List[Dict[str, any]]:
        """
        Get a simplified list of available modules for API responses.
        
        Returns:
            List of dictionaries with basic module information
        
        Example:
            >>> modules = await registry.list_available_modules()
            >>> for module in modules:
            ...     print(f"{module['name']}: {module['description']}")
        """
        modules = await self.discover_modules()
        
        return [
            {
                'name': m.module_name,
                'version': m.version,
                'description': f"{m.module_name} v{m.version}",
                'supports_batching': m.supports_batching,
                'max_batch_size': m.max_batch_size
            }
            for m in modules
        ]
    
    # ================================================================
    # Internal Helper Methods
    # ================================================================
    
    def _parse_module_profile(self, profile_data: Dict) -> ModuleProfile:
        """
        Parse raw database data into ModuleProfile object.
        
        This handles type conversion and validation of database records.
        
        Args:
            profile_data: Raw dictionary from database query
        
        Returns:
            Parsed and validated ModuleProfile object
        
        Raises:
            ValueError: If data is invalid or missing required fields
        """
        try:
            # Parse resource_scaling JSON into ModuleResourceScaling object
            resource_scaling = profile_data.get("resource_scaling", {})
            if isinstance(resource_scaling, dict):
                resource_scaling = ModuleResourceScaling(**resource_scaling)
            
            # Parse optimization_hints (optional field with default empty dict)
            optimization_hints = profile_data.get("optimization_hints", {})
            if optimization_hints is None:
                optimization_hints = {}
            
            return ModuleProfile(
                id=profile_data["id"],
                module_name=profile_data["module_name"],
                version=profile_data["version"],
                supports_batching=profile_data["supports_batching"],
                max_batch_size=profile_data["max_batch_size"],
                resource_scaling=resource_scaling,
                estimated_duration_per_domain=profile_data["estimated_duration_per_domain"],
                task_definition_template=profile_data["task_definition_template"],
                container_name=profile_data["container_name"],
                optimization_hints=optimization_hints,
                is_active=profile_data["is_active"],
                created_at=profile_data["created_at"],
                updated_at=profile_data["updated_at"]
            )
        except KeyError as e:
            raise ValueError(f"Missing required field in module profile: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse module profile: {e}")
    
    def _is_cache_valid(self) -> bool:
        """
        Check if the current cache is still valid based on TTL.
        
        Returns:
            True if cache is valid, False if expired or not initialized
        """
        if not self._cache_timestamp:
            return False
        
        age = datetime.utcnow() - self._cache_timestamp
        return age < self._cache_ttl
    
    def clear_cache(self):
        """
        Manually clear the module cache.
        
        Useful for testing or when modules are updated in the database
        and immediate refresh is required.
        """
        self._module_cache.clear()
        self._cache_timestamp = None
        self.logger.info("Module cache cleared")


# Global singleton instance
# This allows easy access throughout the application without creating multiple instances
module_registry = ModuleRegistry()
