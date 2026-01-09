"""
User tier checking for rate limiting and paywall.

LEAN Refactor (2026-01): Simplified tier checking without Stripe billing.
"""

import logging
from typing import Optional, Dict, Any, Tuple

from app.core.supabase_client import supabase_client
from app.core.tier_limits import get_tier_limits, TierLimits, MAX_PAID_USERS

logger = logging.getLogger(__name__)


async def get_user_tier(user_id: str) -> str:
    """
    Get user's tier/plan type.
    
    Args:
        user_id: The user's UUID
        
    Returns:
        'free', 'pro', or 'enterprise'
    """
    if not user_id:
        return "free"
    
    try:
        result = supabase_client.service_client.table("user_tiers").select(
            "plan_type"
        ).eq("user_id", user_id).single().execute()
        
        if result.data and result.data.get("plan_type"):
            plan_type = result.data["plan_type"]
            if plan_type in ["paid", "pro", "enterprise"]:
                return plan_type
        
        return "free"
        
    except Exception as e:
        logger.debug(f"Could not fetch tier for user {user_id}: {e}")
        return "free"


async def is_user_paid(user_id: str) -> bool:
    """Check if user has a paid subscription."""
    tier = await get_user_tier(user_id)
    return tier in ["paid", "pro", "enterprise"]


async def get_user_urls_viewed(user_id: str) -> int:
    """
    Get the count of unique URLs viewed by a user.
    
    For LEAN architecture, we track URL views to enforce free tier limits.
    """
    if not user_id:
        return 0
    
    try:
        result = supabase_client.service_client.table("user_url_views").select(
            "urls_viewed"
        ).eq("user_id", user_id).single().execute()
        
        if result.data:
            return result.data.get("urls_viewed", 0)
        return 0
        
    except Exception as e:
        logger.debug(f"Could not fetch URL views for user {user_id}: {e}")
        return 0


async def increment_urls_viewed(user_id: str, count: int = 1) -> int:
    """
    Increment the count of URLs viewed by a user.
    
    Returns the new total count.
    """
    if not user_id:
        return 0
    
    try:
        # Upsert to handle first-time users
        current = await get_user_urls_viewed(user_id)
        new_count = current + count
        
        supabase_client.service_client.table("user_url_views").upsert({
            "user_id": user_id,
            "urls_viewed": new_count
        }).execute()
        
        return new_count
        
    except Exception as e:
        logger.error(f"Could not increment URL views for user {user_id}: {e}")
        return 0


async def get_tier_and_limits(user_id: str) -> Tuple[str, TierLimits]:
    """
    Get user's tier and associated limits.
    
    Returns:
        (tier_name, TierLimits)
    """
    tier = await get_user_tier(user_id)
    limits = get_tier_limits(tier)
    return tier, limits


async def get_remaining_url_quota(user_id: str) -> Optional[int]:
    """
    Get remaining URL quota for user.
    
    Returns:
        Number of URLs remaining, or None if unlimited
    """
    tier, limits = await get_tier_and_limits(user_id)
    
    # Unlimited for paid users
    if limits.urls_limit is None:
        return None
    
    viewed = await get_user_urls_viewed(user_id)
    remaining = max(0, limits.urls_limit - viewed)
    return remaining


async def get_paid_spots_remaining() -> int:
    """
    Get the number of remaining paid spots.
    
    For early adopter pricing, only MAX_PAID_USERS spots available.
    """
    try:
        result = supabase_client.service_client.table("user_tiers").select(
            "id", count="exact"
        ).in_("plan_type", ["paid", "pro"]).execute()
        
        current_paid = result.count or 0
        remaining = max(0, MAX_PAID_USERS - current_paid)
        return remaining
        
    except Exception as e:
        logger.error(f"Could not get paid spots count: {e}")
        return MAX_PAID_USERS  # Assume all spots available on error


async def has_spots_available() -> bool:
    """Check if there are still paid spots available."""
    remaining = await get_paid_spots_remaining()
    return remaining > 0


async def check_url_access(user_id: str, current_count: int) -> Tuple[bool, Optional[int]]:
    """
    Check if user can access more URLs based on their tier.
    
    Returns:
        (has_access, limit) - limit is None for unlimited
    """
    tier, limits = await get_tier_and_limits(user_id)
    
    # Unlimited access
    if limits.urls_limit is None:
        return True, None
    
    # Check against limit
    has_access = current_count <= limits.urls_limit
    return has_access, limits.urls_limit
