"""
API Key Service for managing user API keys.

LEAN MVP Simplification:
- One key per user (enforced)
- No key names needed
- Keys can be revealed after creation (encrypted storage)

This service handles:
- Generating secure API keys
- Encrypting keys for storage (Fernet symmetric encryption)
- Hashing keys for fast lookup (SHA-256)
- Validating keys during API requests
- Managing key lifecycle (create, get, delete)
"""
import secrets
import hashlib
import base64
import os
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from cryptography.fernet import Fernet

from ..core.supabase_client import supabase_client
from ..core.config import settings


# ============================================================================
# SCHEMAS
# ============================================================================

class APIKey(BaseModel):
    """API key response model."""
    id: str
    user_id: str
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_active: bool


class APIKeyWithSecret(BaseModel):
    """API key with the decrypted secret (for reveal)."""
    id: str
    user_id: str
    key: str  # The actual API key
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_active: bool


class APIKeyCreated(BaseModel):
    """Response model when a new API key is created."""
    id: str
    key: str  # Full key
    key_prefix: str
    created_at: datetime
    message: str = "Your API key has been created. You can reveal it anytime from this page."


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
    """Service for managing API keys (one per user)."""
    
    # Key format: nb_live_<32 random chars>
    KEY_PREFIX = "nb_live_"
    KEY_LENGTH = 32  # Random part length
    
    def __init__(self):
        self.supabase = supabase_client.service_client
        # Derive encryption key from JWT secret (or use dedicated key)
        self._init_encryption_key()
    
    def _init_encryption_key(self):
        """Initialize Fernet encryption key from settings."""
        # Use JWT secret as base for encryption key (derive a proper Fernet key)
        secret = settings.jwt_secret_key or "fallback-secret-key-for-dev"
        # Create a proper 32-byte key using SHA-256
        key_bytes = hashlib.sha256(secret.encode()).digest()
        # Fernet requires URL-safe base64-encoded 32-byte key
        self.fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
    
    def _generate_key(self) -> str:
        """Generate a new API key."""
        random_part = secrets.token_urlsafe(self.KEY_LENGTH)[:self.KEY_LENGTH]
        return f"{self.KEY_PREFIX}{random_part}"
    
    def _hash_key(self, key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _encrypt_key(self, key: str) -> str:
        """Encrypt the API key for storage."""
        return self.fernet.encrypt(key.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt the API key for reveal."""
        return self.fernet.decrypt(encrypted_key.encode()).decode()
    
    def _get_key_prefix(self, key: str) -> str:
        """Get the display prefix for a key (first 16 chars)."""
        return key[:16] + "..." if len(key) > 16 else key
    
    async def get_user_key(self, user_id: str) -> Optional[APIKey]:
        """
        Get the user's API key (without revealing the secret).
        
        Args:
            user_id: The user's ID
            
        Returns:
            APIKey if exists, None otherwise
        """
        result = self.supabase.table("api_keys").select(
            "id, user_id, key_prefix, created_at, last_used_at, is_active"
        ).eq(
            "user_id", user_id
        ).eq(
            "is_active", True
        ).limit(1).execute()
        
        if not result.data:
            return None
        
        return APIKey(**result.data[0])
    
    async def get_user_key_revealed(self, user_id: str) -> Optional[APIKeyWithSecret]:
        """
        Get the user's API key with the secret revealed.
        
        Args:
            user_id: The user's ID
            
        Returns:
            APIKeyWithSecret if exists, None otherwise
        """
        result = self.supabase.table("api_keys").select(
            "id, user_id, key_prefix, encrypted_key, created_at, last_used_at, is_active"
        ).eq(
            "user_id", user_id
        ).eq(
            "is_active", True
        ).limit(1).execute()
        
        if not result.data:
            return None
        
        record = result.data[0]
        
        # Decrypt the key
        encrypted_key = record.get("encrypted_key")
        if not encrypted_key:
            # Fallback for old keys without encrypted storage
            return APIKeyWithSecret(
                id=record["id"],
                user_id=record["user_id"],
                key="[Key not recoverable - please regenerate]",
                key_prefix=record["key_prefix"],
                created_at=record["created_at"],
                last_used_at=record.get("last_used_at"),
                is_active=record["is_active"]
            )
        
        try:
            decrypted_key = self._decrypt_key(encrypted_key)
        except Exception:
            return APIKeyWithSecret(
                id=record["id"],
                user_id=record["user_id"],
                key="[Decryption failed - please regenerate]",
                key_prefix=record["key_prefix"],
                created_at=record["created_at"],
                last_used_at=record.get("last_used_at"),
                is_active=record["is_active"]
            )
        
        return APIKeyWithSecret(
            id=record["id"],
            user_id=record["user_id"],
            key=decrypted_key,
            key_prefix=record["key_prefix"],
            created_at=record["created_at"],
            last_used_at=record.get("last_used_at"),
            is_active=record["is_active"]
        )
    
    async def create_key(self, user_id: str) -> APIKeyCreated:
        """
        Create a new API key for a user.
        
        Enforces one key per user - will fail if user already has a key.
        
        Args:
            user_id: The user's ID (from Supabase auth)
            
        Returns:
            APIKeyCreated with the full key
            
        Raises:
            ValueError: If user already has an active key
        """
        # Check if user already has an active key
        existing = await self.get_user_key(user_id)
        if existing:
            raise ValueError("You already have an API key. Delete it first to create a new one.")
        
        # Generate new key
        raw_key = self._generate_key()
        key_hash = self._hash_key(raw_key)
        key_prefix = self._get_key_prefix(raw_key)
        encrypted_key = self._encrypt_key(raw_key)
        
        # Insert into database
        result = self.supabase.table("api_keys").insert({
            "user_id": user_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "encrypted_key": encrypted_key,
            "name": "API Key",  # Default name (not shown in UI)
            "is_active": True
        }).execute()
        
        if not result.data:
            raise ValueError("Failed to create API key")
        
        record = result.data[0]
        
        return APIKeyCreated(
            id=record["id"],
            key=raw_key,
            key_prefix=key_prefix,
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
                error="Invalid or expired API key"
            )
        
        # Hash the key and look it up
        key_hash = self._hash_key(key)
        
        try:
            # Use .limit(1) instead of .single() to avoid exception on no results
            result = self.supabase.table("api_keys").select(
                "id, user_id, is_active"
            ).eq(
                "key_hash", key_hash
            ).limit(1).execute()
            
            # Check if key was found
            if not result.data or len(result.data) == 0:
                return APIKeyValidation(
                    is_valid=False,
                    error="Invalid or expired API key"
                )
            
            record = result.data[0]
            
            # Check if key is active
            if not record["is_active"]:
                return APIKeyValidation(
                    is_valid=False,
                    error="Invalid or expired API key"
                )
            
            # Update last_used_at (fire and forget)
            try:
                self.supabase.rpc(
                    "update_api_key_last_used",
                    {"p_key_hash": key_hash}
                ).execute()
            except Exception:
                pass
            
            return APIKeyValidation(
                is_valid=True,
                user_id=record["user_id"],
                key_id=record["id"]
            )
            
        except Exception:
            # Don't leak internal error details - return generic message
            return APIKeyValidation(
                is_valid=False,
                error="Invalid or expired API key"
            )
    
    async def delete_key(self, user_id: str) -> bool:
        """
        Permanently delete the user's API key.
        
        Args:
            user_id: The user's ID
            
        Returns:
            True if deleted, False if not found
        """
        result = self.supabase.table("api_keys").delete().eq(
            "user_id", user_id
        ).eq(
            "is_active", True
        ).execute()
        
        return len(result.data) > 0
    
    async def has_key(self, user_id: str) -> bool:
        """
        Check if user has an active API key.
        
        Args:
            user_id: The user's ID
            
        Returns:
            True if user has an active key
        """
        key = await self.get_user_key(user_id)
        return key is not None


# Global service instance
api_key_service = APIKeyService()
