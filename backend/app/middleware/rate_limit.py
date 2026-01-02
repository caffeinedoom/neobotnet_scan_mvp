"""
Rate limiting middleware for tiered rate limiting.

Applies rate limits based on user plan type:
- Free: 30 requests/minute
- Paid: 100 requests/minute
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.dependencies.rate_limit import (
    get_rate_limit_key,
    check_rate_limit,
    add_rate_limit_headers,
)

logger = logging.getLogger(__name__)

# Paths that are exempt from rate limiting
EXEMPT_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Paths that use public rate limiting (handled by slowapi)
PUBLIC_RATE_LIMITED_PATHS = {
    "/api/v1/public/showcase",
}


class TieredRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies tiered rate limiting based on user plan.
    
    - Unauthenticated requests: 30/minute (IP-based)
    - Free tier: 30/minute (user-based)
    - Paid tier: 100/minute (user-based)
    """
    
    def __init__(self, app, free_limit: int = 30, paid_limit: int = 100):
        super().__init__(app)
        self.free_limit = free_limit
        self.paid_limit = paid_limit
    
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        
        # Skip rate limiting for exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)
        
        # Skip for paths that have their own rate limiting
        if path in PUBLIC_RATE_LIMITED_PATHS:
            return await call_next(request)
        
        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Determine rate limit based on authentication
        user_id = None
        tier = "free"
        
        # Try to extract user from Authorization header
        auth_header = request.headers.get("authorization", "")
        api_key_header = request.headers.get("x-api-key", "")
        
        if auth_header or api_key_header:
            # User is attempting authentication
            # We'll apply rate limiting after checking their tier
            # For now, use IP-based limiting during auth check
            try:
                # Try to get tier from token
                tier = await self._get_tier_from_auth(request, auth_header, api_key_header)
                user_id = await self._get_user_id_from_auth(request, auth_header, api_key_header)
            except Exception as e:
                logger.debug(f"Could not determine tier: {e}")
                tier = "free"
        
        # Determine limit based on tier
        if tier in ["paid", "pro", "enterprise"]:
            limit = self.paid_limit
        else:
            limit = self.free_limit
        
        # Generate rate limit key
        key = get_rate_limit_key(request, user_id)
        
        # Check rate limit
        is_allowed, remaining, reset_in = check_rate_limit(key, limit)
        
        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Try again in {reset_in} seconds.",
                    "retry_after": reset_in,
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                    "Retry-After": str(reset_in),
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)
        
        return response
    
    async def _get_tier_from_auth(self, request: Request, auth_header: str, api_key: str) -> str:
        """Extract tier from authentication credentials."""
        from app.dependencies.tier_check import get_user_tier
        
        user_id = await self._get_user_id_from_auth(request, auth_header, api_key)
        if user_id:
            return await get_user_tier(user_id)
        return "free"
    
    async def _get_user_id_from_auth(self, request: Request, auth_header: str, api_key: str) -> str | None:
        """Extract user ID from authentication credentials."""
        # Try JWT token
        if auth_header.startswith("Bearer "):
            try:
                from app.services.auth_service import AuthService
                token = auth_header.replace("Bearer ", "")
                auth_service = AuthService()
                user = await auth_service.get_current_user(token)
                if user:
                    return str(user.id)
            except Exception:
                pass
        
        # Try API key
        if api_key:
            try:
                from app.core.supabase_client import supabase_client
                import hashlib
                
                key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                result = supabase_client.service_client.table("api_keys").select(
                    "user_id"
                ).eq("key_hash", key_hash).eq("is_active", True).single().execute()
                
                if result.data:
                    return result.data.get("user_id")
            except Exception:
                pass
        
        return None
