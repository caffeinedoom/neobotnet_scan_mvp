"""
Authentication API routes.

LEAN Refactor:
- Removed email/password authentication (use Google SSO via Supabase)
- Added API key management endpoints
- Simplified auth flow
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel

from ...schemas.auth import UserResponse
from ...services.api_key_service import api_key_service, APIKey, APIKeyCreated
from ...core.dependencies import get_current_active_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# SCHEMAS
# ============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str = "Default"


# ============================================================================
# USER PROFILE ENDPOINTS
# ============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get current user profile information.
    
    Works with both:
    - Supabase JWT (from Google SSO)
    - API keys (X-API-Key header)
    
    Returns:
        User profile information
    """
    return current_user


# ============================================================================
# API KEY MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/api-keys", response_model=List[APIKey])
async def list_api_keys(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    List all API keys for the current user.
    
    Returns:
        List of API keys (without the actual key values)
    """
    return await api_key_service.list_keys(current_user.id)


@router.post("/api-keys", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Create a new API key.
    
    IMPORTANT: The full API key is only returned once at creation.
    Store it securely - it cannot be retrieved again.
    
    Args:
        request: API key creation request with optional name
        
    Returns:
        Created API key with the full key value (shown only once)
    """
    return await api_key_service.create_key(
        user_id=current_user.id,
        name=request.name
    )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Revoke (deactivate) an API key.
    
    The key will no longer work for authentication.
    
    Args:
        key_id: The ID of the key to revoke
        
    Returns:
        Confirmation message
    """
    success = await api_key_service.revoke_key(
        user_id=current_user.id,
        key_id=key_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or you don't have permission to revoke it"
        )
    
    return {"message": "API key revoked successfully", "key_id": key_id}


@router.delete("/api-keys/{key_id}/permanent")
async def delete_api_key(
    key_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Permanently delete an API key.
    
    This action cannot be undone.
    
    Args:
        key_id: The ID of the key to delete
        
    Returns:
        Confirmation message
    """
    success = await api_key_service.delete_key(
        user_id=current_user.id,
        key_id=key_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or you don't have permission to delete it"
        )
    
    return {"message": "API key deleted permanently", "key_id": key_id}


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def auth_health():
    """
    Health check endpoint for authentication service.
    
    Returns:
        Service health status
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "message": "Authentication service is running",
        "auth_methods": ["google_sso", "api_key"]
    }
