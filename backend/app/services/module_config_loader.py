"""
Module Configuration Loader - Single Source of Truth
====================================================

Loads module configuration from scan_module_profiles table at app startup.
Replaces hardcoded dictionaries in:
- scan_pipeline.py: DEPENDENCIES dict (Layer 4)
- batch_workflow_orchestrator.py: container_name_mapping (Layer 7)

This is Phase 2 of the 7-Layer Issue Fix.

Usage:
    from app.services.module_config_loader import get_module_config
    
    config = get_module_config()
    dependencies = config.get_dependencies('httpx')  # Returns ['subfinder']
    container = config.get_container_name('httpx')   # Returns 'httpx-scanner'

Author: Neobotnet Development Team
Date: 2025-11-18
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ModuleConfigLoader:
    """
    Loads and caches module configuration from scan_module_profiles table.
    
    This class replaces hardcoded module configuration dictionaries with
    database-driven configuration, enabling:
    - Dynamic module addition without code changes
    - Single source of truth for all module metadata
    - Runtime configuration reloading (future enhancement)
    
    Attributes:
        _dependencies: Maps module_name -> list of dependency module names
        _container_names: Maps module_name -> ECS container name
        _modules_cache: List of all active module names
        _initialized: Whether configuration has been loaded from database
    """
    
    def __init__(self):
        """Initialize empty configuration. Call initialize() to load from database."""
        self._dependencies: Optional[Dict[str, List[str]]] = None
        self._container_names: Optional[Dict[str, str]] = None
        self._modules_cache: Optional[List[str]] = None
        self._initialized = False
    
    async def initialize(self, supabase_client) -> None:
        """
        Load module configuration from database on app startup.
        
        Queries the scan_module_profiles table for all active modules and
        builds internal caches for fast lookups.
        
        Args:
            supabase_client: Supabase client instance (from get_supabase_client())
            
        Raises:
            Exception: If database query fails
        """
        logger.info("🔄 Loading module configuration from database...")
        
        try:
            # Query scan_module_profiles table for active modules
            response = supabase_client.table('scan_module_profiles').select(
                'module_name, container_name, dependencies, is_active'
            ).eq('is_active', True).order('module_name').execute()
            
            rows = response.data
            
            if not rows:
                logger.warning("⚠️  No active modules found in scan_module_profiles!")
                self._dependencies = {}
                self._container_names = {}
                self._modules_cache = []
                self._initialized = True
                return
            
            # Build configuration dictionaries
            self._dependencies = {}
            self._container_names = {}
            self._modules_cache = []
            
            for row in rows:
                module_name = row['module_name']
                self._dependencies[module_name] = row.get('dependencies') or []
                self._container_names[module_name] = row['container_name']
                self._modules_cache.append(module_name)
            
            self._initialized = True
            
            logger.info(f"✅ Loaded {len(rows)} active modules: {', '.join(sorted(self._modules_cache))}")
            logger.debug(f"   Dependencies: {self._dependencies}")
            logger.debug(f"   Container names: {self._container_names}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load module configuration: {e}")
            raise
    
    def get_dependencies(self, module_name: str) -> List[str]:
        """
        Get dependency modules for a given module.
        
        Replaces: scan_pipeline.DEPENDENCIES[module_name]
        
        Args:
            module_name: Module name (e.g., 'httpx')
            
        Returns:
            List of dependency module names (e.g., ['subfinder'])
            Returns empty list if module has no dependencies
            
        Raises:
            ValueError: If module not found or config not initialized
            
        Example:
            >>> config.get_dependencies('httpx')
            ['subfinder']
            >>> config.get_dependencies('subfinder')
            []
        """
        if not self._initialized:
            raise ValueError(
                "Module configuration not initialized! "
                "Call initialize() during app startup."
            )
        
        if module_name not in self._dependencies:
            raise ValueError(
                f"Module '{module_name}' not found in scan_module_profiles. "
                f"Available modules: {', '.join(sorted(self._modules_cache))}"
            )
        
        return self._dependencies[module_name].copy()  # Return copy to prevent mutation
    
    def get_container_name(self, module_name: str) -> str:
        """
        Get ECS container name for a module.
        
        Replaces: batch_workflow_orchestrator.container_name_mapping[module_name]
        
        Args:
            module_name: Module name (e.g., 'httpx')
            
        Returns:
            Container name (e.g., 'httpx-scanner')
            
        Raises:
            ValueError: If config not initialized
            
        Note:
            Falls back to module_name if not found in database (backward compatibility)
            
        Example:
            >>> config.get_container_name('httpx')
            'httpx-scanner'
            >>> config.get_container_name('subfinder')
            'subfinder'
        """
        if not self._initialized:
            raise ValueError(
                "Module configuration not initialized! "
                "Call initialize() during app startup."
            )
        
        if module_name not in self._container_names:
            # Fallback to module name for backward compatibility
            logger.warning(
                f"⚠️  Container name not found for '{module_name}', "
                f"using module name as fallback. "
                f"This module may not be in scan_module_profiles."
            )
            return module_name
        
        return self._container_names[module_name]
    
    def get_all_modules(self) -> List[str]:
        """
        Get list of all active module names.
        
        Returns:
            Sorted list of module names
            
        Raises:
            ValueError: If config not initialized
            
        Example:
            >>> config.get_all_modules()
            ['dnsx', 'httpx', 'subfinder']
        """
        if not self._initialized:
            raise ValueError(
                "Module configuration not initialized! "
                "Call initialize() during app startup."
            )
        
        return sorted(self._modules_cache.copy())  # Return sorted copy
    
    def has_module(self, module_name: str) -> bool:
        """
        Check if a module exists in the configuration.
        
        Args:
            module_name: Module name to check
            
        Returns:
            True if module exists and is active, False otherwise
            
        Raises:
            ValueError: If config not initialized
        """
        if not self._initialized:
            raise ValueError(
                "Module configuration not initialized! "
                "Call initialize() during app startup."
            )
        
        return module_name in self._modules_cache
    
    @property
    def is_initialized(self) -> bool:
        """Check if configuration has been loaded from database."""
        return self._initialized
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        if not self._initialized:
            return "<ModuleConfigLoader: not initialized>"
        return (
            f"<ModuleConfigLoader: {len(self._modules_cache)} modules loaded - "
            f"{', '.join(sorted(self._modules_cache))}>"
        )


# ================================================================
# Global Singleton Instance
# ================================================================

_module_config: Optional[ModuleConfigLoader] = None


def get_module_config() -> ModuleConfigLoader:
    """
    Get global module configuration singleton instance.
    
    This function returns the same instance across the application,
    ensuring configuration is loaded only once.
    
    Returns:
        ModuleConfigLoader instance
        
    Usage:
        from app.services.module_config_loader import get_module_config
        
        config = get_module_config()
        
        # Get dependencies for a module
        deps = config.get_dependencies('httpx')
        
        # Get container name for a module
        container = config.get_container_name('httpx')
        
        # Get all active modules
        modules = config.get_all_modules()
    """
    global _module_config
    if _module_config is None:
        _module_config = ModuleConfigLoader()
    return _module_config


async def initialize_module_config(supabase_client) -> None:
    """
    Initialize module configuration on app startup.
    
    Call this from main.py in the FastAPI startup event handler.
    
    Args:
        supabase_client: Supabase client instance
        
    Raises:
        Exception: If database query fails
        
    Usage:
        # In main.py:
        from app.services.module_config_loader import initialize_module_config
        from app.database import get_supabase_client
        
        @app.on_event("startup")
        async def startup_event():
            supabase = get_supabase_client()
            await initialize_module_config(supabase)
    """
    config = get_module_config()
    await config.initialize(supabase_client)
