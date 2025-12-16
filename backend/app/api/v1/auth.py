"""
Authentication API routes.

LEAN Refactor:
- Removed email/password authentication (use Google SSO via Supabase)
- Added API key management endpoints
- Simplified auth flow
- Added httpOnly cookie session management for XSS protection
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from ...schemas.auth import UserResponse
from ...services.api_key_service import api_key_service, APIKey, APIKeyCreated
from ...services.auth_service import auth_service
from ...core.dependencies import get_current_active_user
from ...core.config import settings


router = APIRouter(prefix="/auth", tags=["Authentication"])

# For extracting Bearer token
bearer_scheme = HTTPBearer(auto_error=False)

# Cookie configuration
COOKIE_NAME = "neobotnet_session"


# ============================================================================
# SCHEMAS
# ============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str = "Default"


class SessionResponse(BaseModel):
    """Response for session operations."""
    message: str
    user: Optional[UserResponse] = None


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS (httpOnly Cookie Auth)
# ============================================================================

@router.post("/session", response_model=SessionResponse)
async def create_session(
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
):
    """
    Create a session by exchanging a Supabase JWT for an httpOnly cookie.
    
    This is the secure way to authenticate browser sessions:
    1. Frontend authenticates with Supabase (Google SSO)
    2. Frontend calls this endpoint with the Supabase JWT
    3. Backend validates JWT and sets httpOnly cookie
    4. All subsequent requests use the cookie automatically
    
    The cookie is:
    - httpOnly: JavaScript cannot access it (XSS protection)
    - Secure: Only sent over HTTPS (in production)
    - SameSite=Lax: CSRF protection while allowing normal navigation
    
    Args:
        response: FastAPI response object for setting cookies
        credentials: Bearer token with Supabase JWT
        
    Returns:
        SessionResponse with user info
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required to create session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Validate the JWT and get user info
    try:
        user = await auth_service.get_current_user(token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Set httpOnly cookie with the JWT
    # Cookie settings based on environment
    is_production = settings.environment in ["production", "prod", "staging"]
    
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=settings.cookie_httponly,
        secure=is_production or settings.cookie_secure,  # Force secure in production
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,  # None = current domain only
        max_age=settings.access_token_expire_minutes * 60,  # Convert to seconds
        path="/",  # Available for all paths
    )
    
    return SessionResponse(
        message="Session created successfully",
        user=user
    )


@router.delete("/session")
async def delete_session(response: Response):
    """
    Delete the session (logout).
    
    Clears the httpOnly cookie, effectively logging out the user.
    This endpoint does not require authentication - it simply clears
    any existing session cookie.
    
    Args:
        response: FastAPI response object for clearing cookies
        
    Returns:
        Confirmation message
    """
    # Clear the session cookie
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        domain=settings.cookie_domain,
    )
    
    return {"message": "Session deleted successfully"}


@router.get("/session", response_model=SessionResponse)
async def get_session(
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get current session information.
    
    Returns the user info if a valid session exists.
    Works with both cookie auth and Bearer token auth.
    
    Args:
        request: FastAPI request object
        current_user: Current authenticated user
        
    Returns:
        SessionResponse with user info
    """
    return SessionResponse(
        message="Session active",
        user=current_user
    )


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
