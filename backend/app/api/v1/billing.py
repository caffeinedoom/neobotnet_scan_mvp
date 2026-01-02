"""
Billing API endpoints for Stripe integration.
Handles checkout, webhooks, and billing status.
"""

import os
import stripe
from fastapi import APIRouter, HTTPException, Request, Depends, Header, status
from typing import Optional

from app.schemas.billing import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    BillingStatusResponse,
    WebhookResponse,
)
from app.dependencies.auth import get_current_user
from app.dependencies.tier_check import (
    get_user_tier,
    get_user_urls_viewed,
    get_paid_spots_remaining,
    can_purchase,
)
from app.core.tier_limits import get_tier_limits, MAX_PAID_USERS
from app.core.supabase_client import supabase_client


router = APIRouter()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for upgrading to paid tier.
    """
    user_id = user.get("id") or user.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found",
        )
    
    # Check if already paid
    plan_type = await get_user_tier(user_id)
    if plan_type in ["paid", "pro", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a paid plan",
        )
    
    # Check if spots available
    if not await can_purchase():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sorry, all early access spots have been claimed",
        )
    
    try:
        # Get user email for Stripe
        user_email = user.get("email")
        
        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price": STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_email=user_email,
            metadata={
                "user_id": user_id,
            },
            # Collect billing address for tax purposes
            billing_address_collection="auto",
        )
        
        return CheckoutSessionResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Handle Stripe webhook events.
    Called by Stripe when payment is completed.
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )
    
    try:
        payload = await request.body()
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )
    
    # Handle checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        
        if user_id:
            await upgrade_user_to_paid(
                user_id=user_id,
                stripe_customer_id=session.get("customer"),
                stripe_payment_id=session.get("payment_intent"),
            )
            return WebhookResponse(
                status="success",
                message=f"User {user_id} upgraded to paid",
            )
    
    # Handle payment_intent.succeeded (backup)
    elif event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        # Payment succeeded but we primarily use checkout.session.completed
        return WebhookResponse(
            status="success",
            message="Payment intent succeeded",
        )
    
    return WebhookResponse(
        status="ignored",
        message=f"Unhandled event type: {event['type']}",
    )


async def upgrade_user_to_paid(
    user_id: str,
    stripe_customer_id: Optional[str],
    stripe_payment_id: Optional[str],
) -> None:
    """
    Upgrade a user to paid tier in the database.
    """
    from datetime import datetime, timezone
    
    try:
        # Update user_quotas table
        supabase_client.service_client.table("user_quotas").update({
            "plan_type": "paid",
            "stripe_customer_id": stripe_customer_id,
            "stripe_payment_id": stripe_payment_id,
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }).eq("user_id", user_id).execute()
        
    except Exception as e:
        # Log error but don't fail - we can manually fix later
        print(f"Error upgrading user {user_id}: {e}")


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(
    user: dict = Depends(get_current_user),
):
    """
    Get the current user's billing status and URL quota.
    """
    user_id = user.get("id") or user.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found",
        )
    
    # Get tier and limits
    plan_type = await get_user_tier(user_id)
    limits = get_tier_limits(plan_type)
    urls_viewed = await get_user_urls_viewed(user_id)
    spots_remaining = await get_paid_spots_remaining()
    
    # Calculate remaining URLs
    urls_remaining = None
    if limits.urls_limit is not None:
        urls_remaining = max(0, limits.urls_limit - urls_viewed)
    
    # Get paid_at if applicable
    paid_at = None
    if plan_type in ["paid", "pro", "enterprise"]:
        try:
            result = supabase_client.service_client.table("user_quotas").select(
                "paid_at"
            ).eq("user_id", user_id).single().execute()
            if result.data:
                paid_at = result.data.get("paid_at")
        except Exception:
            pass
    
    return BillingStatusResponse(
        plan_type=plan_type,
        is_paid=plan_type in ["paid", "pro", "enterprise"],
        paid_at=paid_at,
        urls_limit=limits.urls_limit,
        urls_viewed=urls_viewed,
        urls_remaining=urls_remaining,
        spots_remaining=spots_remaining,
        can_upgrade=plan_type == "free" and spots_remaining > 0,
    )


@router.get("/spots-remaining")
async def get_spots_remaining():
    """
    Public endpoint to get remaining paid spots.
    No authentication required.
    """
    spots = await get_paid_spots_remaining()
    return {
        "spots_remaining": spots,
        "max_spots": MAX_PAID_USERS,
        "spots_claimed": MAX_PAID_USERS - spots,
    }
