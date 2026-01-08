"""
Tier configuration for paywall system.
Defines limits for free vs paid users.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class TierLimits:
    """Limits for a user tier."""
    urls_limit: Optional[int]  # Total URLs visible (None = unlimited)
    rate_limit: str  # Requests per minute


# Tier configuration
# - free: Default tier with limited access
# - pro: Paid tier ($13.37 one-time, 100 early adopter spots)
# - enterprise: Future tier (manual assignment, not part of 100 spots)
TIER_LIMITS = {
    "free": TierLimits(
        urls_limit=250,  # Total URLs visible
        rate_limit="30/minute",
    ),
    "pro": TierLimits(
        urls_limit=None,  # Unlimited
        rate_limit="100/minute",
    ),
    "enterprise": TierLimits(
        urls_limit=None,
        rate_limit="200/minute",
    ),
}


def get_tier_limits(plan_type: str) -> TierLimits:
    """Get limits for a given tier."""
    return TIER_LIMITS.get(plan_type, TIER_LIMITS["free"])


# Paywall configuration
MAX_PAID_USERS = 100  # First 100 users only
PRICE_USD = 13.37
