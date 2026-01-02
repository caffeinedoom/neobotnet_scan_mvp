"""
Pydantic schemas for billing endpoints.
"""

from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class CheckoutSessionRequest(BaseModel):
    """Request to create a checkout session."""
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Response with checkout session URL."""
    checkout_url: str
    session_id: str


class BillingStatusResponse(BaseModel):
    """User's billing/tier status."""
    plan_type: str
    is_paid: bool
    paid_at: Optional[datetime] = None
    urls_limit: Optional[int] = None
    urls_viewed: int = 0
    urls_remaining: Optional[int] = None
    spots_remaining: int
    can_upgrade: bool


class WebhookResponse(BaseModel):
    """Response from webhook processing."""
    status: str
    message: str
