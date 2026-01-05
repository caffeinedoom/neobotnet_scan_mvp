"""
Dependency for checking user tier and applying limits.
"""

from typing import Optional, Tuple

from app.core.supabase_client import supabase_client
from app.core.tier_limits import get_tier_limits, TierLimits, MAX_PAID_USERS


async def get_user_tier(user_id: str) -> str:
    """
    Get user's plan type from user_quotas table.
    Returns 'free' if not found.
    """
    try:
        result = supabase_client.service_client.table("user_quotas").select(
            "plan_type"
        ).eq("user_id", user_id).single().execute()
        
        if result.data:
            return result.data.get("plan_type", "free")
        return "free"
    except Exception:
        return "free"


async def get_user_urls_viewed(user_id: str) -> int:
    """
    Get the count of URLs a user has viewed.
    Used for enforcing 250 URL limit for free tier.
    """
    try:
        result = supabase_client.service_client.table("user_usage").select(
            "urls_viewed_count"
        ).eq("user_id", user_id).single().execute()
        
        if result.data:
            return result.data.get("urls_viewed_count", 0) or 0
        return 0
    except Exception:
        return 0


async def increment_urls_viewed(user_id: str, count: int) -> None:
    """
    Increment the URLs viewed count for a user.
    Called when a free user fetches URLs.
    
    Uses UPSERT to handle users who don't have a user_usage record yet.
    """
    try:
        # Get current count
        current = await get_user_urls_viewed(user_id)
        new_count = current + count
        
        # Use upsert to create record if it doesn't exist
        supabase_client.service_client.table("user_usage").upsert({
            "user_id": user_id,
            "urls_viewed_count": new_count
        }, on_conflict="user_id").execute()
    except Exception:
        pass  # Don't fail the request if tracking fails


async def get_tier_and_limits(user_id: str) -> Tuple[str, TierLimits]:
    """
    Get user tier and corresponding limits.
    Returns tuple of (plan_type, TierLimits).
    """
    plan_type = await get_user_tier(user_id)
    limits = get_tier_limits(plan_type)
    return plan_type, limits


async def get_remaining_url_quota(user_id: str) -> Tuple[int, Optional[int]]:
    """
    Get remaining URL quota for a user.
    Returns (urls_viewed, urls_limit).
    urls_limit is None for unlimited.
    """
    plan_type = await get_user_tier(user_id)
    limits = get_tier_limits(plan_type)
    
    if limits.urls_limit is None:
        return 0, None  # Unlimited
    
    urls_viewed = await get_user_urls_viewed(user_id)
    return urls_viewed, limits.urls_limit


async def get_paid_spots_remaining() -> int:
    """
    Get number of paid spots remaining (out of MAX_PAID_USERS).
    """
    try:
        result = supabase_client.service_client.rpc(
            "get_paid_user_count"
        ).execute()
        
        paid_count = result.data if result.data else 0
        return max(0, MAX_PAID_USERS - paid_count)
    except Exception:
        return MAX_PAID_USERS  # Assume spots available on error


async def can_purchase() -> bool:
    """
    Check if user can purchase (spots still available).
    """
    remaining = await get_paid_spots_remaining()
    return remaining > 0
