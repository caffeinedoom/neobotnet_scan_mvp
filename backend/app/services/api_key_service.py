"""
API Key Service for managing user API keys.

This service handles:
- Generating secure API keys
- Hashing keys for storage (SHA-256)
- Validating keys during API requests
- Managing key lifecycle (create, list, revoke)
"""
import secrets
import hashlib
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from ..core.supabase_client import supabase_client


# ============================================================================
# SCHEMAS
# ============================================================================

class APIKey(BaseModel):
    """API key response model (never includes the full key after creation)."""
    id: str
    user_id: str
    key_prefix: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_active: bool


class APIKeyCreate(BaseModel):
    """Request model for creating an API key."""
    name: str = "Default"


class APIKeyCreated(BaseModel):
    """Response model when a new API key is created (includes full key ONCE)."""
    id: str
    key: str  # Full key - only shown once at creation
    key_prefix: str
    name: str
    created_at: datetime
    message: str = "Store this key securely. It will not be shown again."


class APIKeyValidation(BaseModel):
    """Result of API key validation."""
    is_valid: bool
    user_id: Optional[str] = None
    key_id: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# SERVICE
# ============================================================================

class APIKeyService:
    """Service for managing API keys."""
    
    # Key format: nb_live_<32 random chars> = 40 chars total
    KEY_PREFIX = "nb_live_"
    KEY_LENGTH = 32  # Random part length
    
    def __init__(self):
        self.supabase = supabase_client.service_client  # Use service role for DB operations
    
    def _generate_key(self) -> str:
        """Generate a new API key."""
        random_part = secrets.token_urlsafe(self.KEY_LENGTH)[:self.KEY_LENGTH]
        return f"{self.KEY_PREFIX}{random_part}"
    
    def _hash_key(self, key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _get_key_prefix(self, key: str) -> str:
        """Get the display prefix for a key (first 16 chars)."""
        return key[:16] + "..." if len(key) > 16 else key
    
    async def create_key(self, user_id: str, name: str = "Default") -> APIKeyCreated:
        """
        Create a new API key for a user.
        
        Args:
            user_id: The user's ID (from Supabase auth)
            name: Optional name for the key
            
        Returns:
            APIKeyCreated with the full key (shown only once)
        """
        # Generate new key
        raw_key = self._generate_key()
        key_hash = self._hash_key(raw_key)
        key_prefix = self._get_key_prefix(raw_key)
        
        # Insert into database
        result = self.supabase.table("api_keys").insert({
            "user_id": user_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": name,
            "is_active": True
        }).execute()
        
        if not result.data:
            raise ValueError("Failed to create API key")
        
        record = result.data[0]
        
        return APIKeyCreated(
            id=record["id"],
            key=raw_key,  # Return full key ONLY at creation
            key_prefix=key_prefix,
            name=record["name"],
            created_at=record["created_at"]
        )
    
    async def validate_key(self, key: str) -> APIKeyValidation:
        """
        Validate an API key.
        
        Args:
            key: The raw API key to validate
            
        Returns:
            APIKeyValidation with validation result and user_id if valid
        """
        # Basic format check
        if not key or not key.startswith(self.KEY_PREFIX):
            return APIKeyValidation(
                is_valid=False,
                error="Invalid key format"
            )
        
        # Hash the key and look it up
        key_hash = self._hash_key(key)
        
        try:
            result = self.supabase.table("api_keys").select(
                "id, user_id, is_active"
            ).eq(
                "key_hash", key_hash
            ).single().execute()
            
            if not result.data:
                return APIKeyValidation(
                    is_valid=False,
                    error="API key not found"
                )
            
            record = result.data
            
            # Check if key is active
            if not record["is_active"]:
                return APIKeyValidation(
                    is_valid=False,
                    error="API key is inactive"
                )
            
            # Update last_used_at (fire and forget - don't wait)
            try:
                self.supabase.rpc(
                    "update_api_key_last_used",
                    {"p_key_hash": key_hash}
                ).execute()
            except Exception:
                pass  # Don't fail validation if timestamp update fails
            
            return APIKeyValidation(
                is_valid=True,
                user_id=record["user_id"],
                key_id=record["id"]
            )
            
        except Exception as e:
            return APIKeyValidation(
                is_valid=False,
                error=f"Validation error: {str(e)}"
            )
    
    async def list_keys(self, user_id: str) -> List[APIKey]:
        """
        List all API keys for a user.
        
        Args:
            user_id: The user's ID
            
        Returns:
            List of APIKey objects (without the actual key values)
        """
        result = self.supabase.table("api_keys").select(
            "id, user_id, key_prefix, name, created_at, last_used_at, is_active"
        ).eq(
            "user_id", user_id
        ).order(
            "created_at", desc=True
        ).execute()
        
        return [APIKey(**record) for record in result.data]
    
    async def revoke_key(self, user_id: str, key_id: str) -> bool:
        """
        Revoke (deactivate) an API key.
        
        Args:
            user_id: The user's ID (for authorization)
            key_id: The key ID to revoke
            
        Returns:
            True if revoked, False if not found or unauthorized
        """
        result = self.supabase.table("api_keys").update({
            "is_active": False
        }).eq(
            "id", key_id
        ).eq(
            "user_id", user_id  # Ensure user owns the key
        ).execute()
        
        return len(result.data) > 0
    
    async def delete_key(self, user_id: str, key_id: str) -> bool:
        """
        Permanently delete an API key.
        
        Args:
            user_id: The user's ID (for authorization)
            key_id: The key ID to delete
            
        Returns:
            True if deleted, False if not found or unauthorized
        """
        result = self.supabase.table("api_keys").delete().eq(
            "id", key_id
        ).eq(
            "user_id", user_id  # Ensure user owns the key
        ).execute()
        
        return len(result.data) > 0
    
    async def get_key_count(self, user_id: str) -> int:
        """
        Get the number of API keys a user has.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Number of API keys
        """
        result = self.supabase.table("api_keys").select(
            "id", count="exact"
        ).eq(
            "user_id", user_id
        ).execute()
        
        return result.count or 0


# Global service instance
api_key_service = APIKeyService()

