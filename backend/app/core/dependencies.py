"""
FastAPI dependencies for authentication and authorization.

Supports two authentication methods:
1. JWT tokens (via httpOnly cookie or Authorization header) - for browser sessions
2. API keys (via X-API-Key header or Authorization header) - for programmatic access
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import verify_token
from ..services.auth_service import auth_service
from ..services.api_key_service import api_key_service
from ..schemas.auth import UserResponse


# HTTP Bearer token scheme (fallback for API clients)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> UserResponse:
    """
    Dependency to get the current authenticated user.
    
    Supports multiple authentication methods (in priority order):
    1. X-API-Key header (for programmatic API access)
    2. httpOnly cookie (for browser sessions)
    3. Authorization Bearer header (for API clients with JWT)
    
    Args:
        request: FastAPI request object for reading cookies
        credentials: Optional HTTP Bearer token credentials
        x_api_key: Optional API key from X-API-Key header
        
    Returns:
        UserResponse: Current user information
        
    Raises:
        HTTPException: If authentication fails
    """
    
    # Priority 1: Check for API key in X-API-Key header
    if x_api_key:
        if x_api_key.startswith("nb_live_"):
            return await _authenticate_with_api_key(x_api_key)
        else:
            # API key provided but wrong format
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format. Keys must start with 'nb_live_'.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
    
    # Priority 2: Check for API key in Authorization header (Bearer nb_live_...)
    if credentials and credentials.credentials.startswith("nb_live_"):
        return await _authenticate_with_api_key(credentials.credentials)
    
    # Priority 3: Try JWT authentication
    token = None
    
    # Try httpOnly cookie first (most secure for browsers)
    # Check new cookie name first, then legacy name for backwards compatibility
    token = request.cookies.get("neobotnet_session") or request.cookies.get("access_token")
    
    # Fallback to Authorization header (JWT)
    if not token and credentials:
        token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication provided. Use API key (X-API-Key header) or JWT token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify the JWT token and get user
    try:
        user = await auth_service.get_current_user(token)
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _authenticate_with_api_key(api_key: str) -> UserResponse:
    """
    Authenticate a request using an API key.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        UserResponse: User information associated with the API key
        
    Raises:
        HTTPException: If API key is invalid
    """
    validation = await api_key_service.validate_key(api_key)
    
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=validation.error or "Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Fetch user details from Supabase
    try:
        from ..core.supabase_client import supabase_client
        
        result = supabase_client.service_client.auth.admin.get_user_by_id(
            validation.user_id
        )
        
        if not result or not result.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found for API key",
            )
        
        user = result.user
        user_metadata = user.user_metadata or {}
        
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user_metadata.get("full_name"),
            created_at=str(user.created_at) if user.created_at else None,
            email_confirmed_at=str(user.email_confirmed_at) if user.email_confirmed_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}",
        )


async def get_current_user_websocket(token: str) -> UserResponse:
    """
    Authentication function specifically for WebSocket connections.
    
    Since WebSockets can't use standard FastAPI dependency injection,
    this function takes a token directly and returns the authenticated user.
    
    Args:
        token: JWT token for authentication
        
    Returns:
        UserResponse: Current user information
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided for WebSocket connection",
        )
    
    try:
        user = await auth_service.get_current_user(token)
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="WebSocket authentication failed: Could not validate credentials",
        )


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    Dependency to get the current active user.
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        UserResponse: Current active user information
        
    Raises:
        HTTPException: If user is inactive
    """
    # For now, we consider all users active
    # This can be extended to check user status from database
    return current_user


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[UserResponse]:
    """
    Dependency to optionally get the current user (allows anonymous access).
    
    Args:
        request: FastAPI request object for reading cookies
        credentials: Optional HTTP Bearer token credentials
        
    Returns:
        Optional[UserResponse]: Current user information if authenticated, None otherwise
    """
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None 