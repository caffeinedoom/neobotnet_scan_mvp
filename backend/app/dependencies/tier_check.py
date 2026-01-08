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
        # Use .limit(1) instead of .single() to avoid exception on no results
        result = supabase_client.service_client.table("user_quotas").select(
            "plan_type"
        ).eq("user_id", user_id).limit(1).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0].get("plan_type", "free")
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
    
    Uses atomic database operation to prevent race conditions.
    """
    try:
        # First, try to ensure user has a record (upsert with current value if exists)
        # This handles the case where user_usage doesn't exist yet
        supabase_client.service_client.table("user_usage").upsert({
            "user_id": user_id,
            "urls_viewed_count": count  # Initial value if new record
        }, on_conflict="user_id", ignore_duplicates=True).execute()
        
        # Then, atomically increment using raw SQL via RPC
        # This prevents race conditions by doing increment at database level
        supabase_client.service_client.rpc(
            "increment_url_quota",
            {"p_user_id": user_id, "p_count": count}
        ).execute()
    except Exception:
        # Fallback to non-atomic if RPC doesn't exist (backwards compatibility)
        try:
            current = await get_user_urls_viewed(user_id)
            new_count = current + count
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
    Includes both 'pro' users and 'pending_payment' reservations.
    """
    try:
        # Count pro users
        result = supabase_client.service_client.rpc(
            "get_paid_user_count"
        ).execute()
        pro_count = result.data if result.data else 0
        
        # Also count pending reservations
        pending_result = supabase_client.service_client.table("user_quotas").select(
            "id", count="exact"
        ).eq("plan_type", "pending_payment").execute()
        pending_count = pending_result.count if pending_result.count else 0
        
        total_reserved = pro_count + pending_count
        return max(0, MAX_PAID_USERS - total_reserved)
    except Exception:
        return 0  # FAIL CLOSED - assume no spots on error


async def can_purchase() -> bool:
    """
    Check if user can purchase (spots still available).
    
    DEPRECATED: Use try_reserve_spot() instead for atomic reservation.
    This function has a race condition - use only for display purposes.
    """
    remaining = await get_paid_spots_remaining()
    return remaining > 0


async def try_reserve_spot(user_id: str) -> bool:
    """
    Atomically try to reserve a pro spot for a user.
    
    Uses database-level locking to prevent race conditions where
    multiple users could claim the last available spot.
    
    Args:
        user_id: The user's UUID
        
    Returns:
        True if spot was reserved (or user already has pro/enterprise)
        False if no spots available
    """
    try:
        result = supabase_client.service_client.rpc(
            "try_reserve_pro_spot",
            {"p_user_id": user_id, "max_spots": MAX_PAID_USERS}
        ).execute()
        return result.data if result.data else False
    except Exception:
        return False  # Fail closed - don't allow purchase on error


async def release_expired_reservations(expiry_hours: int = 24) -> int:
    """
    Release pending_payment reservations older than specified hours.
    
    Call this periodically (e.g., via cron job) to free up spots
    from users who started checkout but never completed payment.
    
    Args:
        expiry_hours: Hours after which to expire reservations (default: 24)
        
    Returns:
        Number of reservations released
    """
    try:
        result = supabase_client.service_client.rpc(
            "release_expired_reservations",
            {"expiry_hours": expiry_hours}
        ).execute()
        return result.data if result.data else 0
    except Exception:
        return 0
