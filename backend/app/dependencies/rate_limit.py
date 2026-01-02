"""
Tiered rate limiting based on user plan type.

Free users: 30 requests/minute
Paid users: 100 requests/minute
"""

import time
import hashlib
from typing import Optional, Callable
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.responses import Response

from app.core.tier_limits import get_tier_limits


# In-memory rate limit storage
# In production, consider using Redis for distributed rate limiting
_rate_limit_store: dict = defaultdict(lambda: {"count": 0, "reset_at": 0})


def get_rate_limit_key(request: Request, user_id: Optional[str] = None) -> str:
    """
    Generate a unique rate limit key based on user or IP.
    """
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to IP-based limiting
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    
    return f"ip:{ip}"


def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60
) -> tuple[bool, int, int]:
    """
    Check if request is within rate limit.
    
    Returns:
        (is_allowed, remaining, reset_in_seconds)
    """
    now = time.time()
    bucket = _rate_limit_store[key]
    
    # Reset bucket if window expired
    if now >= bucket["reset_at"]:
        bucket["count"] = 0
        bucket["reset_at"] = now + window_seconds
    
    # Check limit
    if bucket["count"] >= limit:
        reset_in = int(bucket["reset_at"] - now)
        return False, 0, reset_in
    
    # Increment counter
    bucket["count"] += 1
    remaining = limit - bucket["count"]
    reset_in = int(bucket["reset_at"] - now)
    
    return True, remaining, reset_in


async def get_user_id_from_request(request: Request) -> Optional[str]:
    """
    Extract user ID from request (via auth header).
    Returns None if not authenticated.
    """
    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user"):
        user = request.state.user
        if hasattr(user, "id"):
            return str(user.id)
        if isinstance(user, dict):
            return user.get("id") or user.get("sub")
    
    return None


async def get_user_tier_from_request(request: Request) -> str:
    """
    Get user's plan type from request.
    Returns 'free' if not authenticated or not found.
    """
    user_id = await get_user_id_from_request(request)
    
    if not user_id:
        return "free"
    
    try:
        from app.dependencies.tier_check import get_user_tier
        return await get_user_tier(user_id)
    except Exception:
        return "free"


class TieredRateLimiter:
    """
    Rate limiter that applies different limits based on user tier.
    
    Usage:
        rate_limiter = TieredRateLimiter()
        
        @app.get("/endpoint")
        async def endpoint(request: Request):
            await rate_limiter(request)
            return {"data": "..."}
    """
    
    def __init__(
        self,
        free_limit: int = 30,
        paid_limit: int = 100,
        window_seconds: int = 60
    ):
        self.free_limit = free_limit
        self.paid_limit = paid_limit
        self.window_seconds = window_seconds
    
    async def __call__(self, request: Request) -> None:
        """Check rate limit and raise HTTPException if exceeded."""
        user_id = await get_user_id_from_request(request)
        tier = await get_user_tier_from_request(request)
        
        # Get limit based on tier
        if tier in ["paid", "pro", "enterprise"]:
            limit = self.paid_limit
        else:
            limit = self.free_limit
        
        # Generate rate limit key
        key = get_rate_limit_key(request, user_id)
        
        # Check rate limit
        is_allowed, remaining, reset_in = check_rate_limit(
            key, limit, self.window_seconds
        )
        
        # Store rate limit info in request for headers
        request.state.rate_limit_limit = limit
        request.state.rate_limit_remaining = remaining
        request.state.rate_limit_reset = reset_in
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {reset_in} seconds.",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                    "Retry-After": str(reset_in),
                }
            )


def add_rate_limit_headers(response: Response, request: Request) -> Response:
    """
    Add rate limit headers to response.
    Call this in middleware or endpoint.
    """
    if hasattr(request.state, "rate_limit_limit"):
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)
    
    return response


# Pre-configured rate limiter instance
tiered_rate_limiter = TieredRateLimiter(
    free_limit=30,
    paid_limit=100,
    window_seconds=60
)
