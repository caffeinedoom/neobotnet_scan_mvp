"""
Dependencies module for FastAPI dependency injection.
"""

from .tier_check import (
    get_user_tier,
    get_user_urls_viewed,
    increment_urls_viewed,
    get_tier_and_limits,
    get_remaining_url_quota,
    get_paid_spots_remaining,
    can_purchase,
)

from .rate_limit import (
    tiered_rate_limiter,
    TieredRateLimiter,
    check_rate_limit,
    get_rate_limit_key,
)

__all__ = [
    # Tier checking
    "get_user_tier",
    "get_user_urls_viewed",
    "increment_urls_viewed",
    "get_tier_and_limits",
    "get_remaining_url_quota",
    "get_paid_spots_remaining",
    "can_purchase",
    # Rate limiting
    "tiered_rate_limiter",
    "TieredRateLimiter",
    "check_rate_limit",
    "get_rate_limit_key",
]
