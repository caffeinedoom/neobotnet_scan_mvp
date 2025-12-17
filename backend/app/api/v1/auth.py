"""
Authentication API routes.

LEAN Refactor:
- Removed email/password authentication (use Google SSO via Supabase)
- Added API key management endpoints
- Simplified auth flow
- Added httpOnly cookie session management for XSS protection
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from ...schemas.auth import UserResponse
from ...services.api_key_service import api_key_service, APIKey, APIKeyCreated, APIKeyWithSecret
from ...services.auth_service import auth_service
from ...core.dependencies import get_current_active_user
from ...core.config import settings


router = APIRouter(prefix="/auth", tags=["Authentication"])

# For extracting Bearer token
bearer_scheme = HTTPBearer(auto_error=False)

# Cookie configuration
COOKIE_NAME = "neobotnet_session"


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
# API KEY MANAGEMENT ENDPOINTS (One Key Per User)
# ============================================================================

@router.get("/api-key", response_model=Optional[APIKey])
async def get_api_key(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get the user's API key (without revealing the secret).
    
    Each user can have only ONE API key.
        
    Returns:
        APIKey if exists, null otherwise
    """
    return await api_key_service.get_user_key(current_user.id)


@router.get("/api-key/reveal", response_model=Optional[APIKeyWithSecret])
async def reveal_api_key(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get the user's API key with the secret revealed.
    
    Returns the full API key that can be copied and used.
        
    Returns:
        APIKeyWithSecret with the actual key value
    """
    return await api_key_service.get_user_key_revealed(current_user.id)


@router.post("/api-key", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Create a new API key (one-click).
    
    Each user can only have ONE API key. If you already have a key,
    you must delete it first before creating a new one.
    
    The key can be revealed anytime using the /api-key/reveal endpoint.
        
    Returns:
        Created API key with the full key value
        
    Raises:
        400: If user already has an API key
    """
    try:
        return await api_key_service.create_key(user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/api-key")
async def delete_api_key(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Delete the user's API key.
    
    This action cannot be undone. You can create a new key afterward.
        
    Returns:
        Confirmation message
    """
    success = await api_key_service.delete_key(user_id=current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No API key found to delete"
        )
    
    return {"message": "API key deleted successfully"}


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
