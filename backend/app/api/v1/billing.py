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
from app.schemas.auth import UserResponse
from app.core.dependencies import get_current_user
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
    user: UserResponse = Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for upgrading to paid tier.
    """
    user_id = user.id
    
    # Check if already pro/enterprise
    plan_type = await get_user_tier(user_id)
    if plan_type in ["pro", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pro plan",
        )
    
    # Check if spots available
    if not await can_purchase():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sorry, all early access spots have been claimed",
        )
    
    try:
        # Get user email for Stripe
        user_email = user.email
        
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
            try:
                await upgrade_user_to_pro(
                    user_id=user_id,
                    stripe_customer_id=session.get("customer"),
                    stripe_payment_id=session.get("payment_intent"),
                )
                return WebhookResponse(
                    status="success",
                    message=f"User {user_id} upgraded to pro",
                )
            except Exception as e:
                # Return 500 so Stripe will retry the webhook
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upgrade user: {str(e)}",
                )
        else:
            # No user_id in metadata - log and return error
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user_id in session metadata",
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


async def upgrade_user_to_pro(
    user_id: str,
    stripe_customer_id: Optional[str],
    stripe_payment_id: Optional[str],
) -> None:
    """
    Upgrade a user to pro tier in the database.
    
    Uses UPSERT to handle users who don't have a user_quotas record yet.
    This is critical - new users may not have a record, and UPDATE would silently fail.
    """
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        paid_at = datetime.now(timezone.utc).isoformat()
        
        # Use UPSERT to create record if it doesn't exist, or update if it does
        # This fixes the bug where UPDATE silently fails for new users
        result = supabase_client.service_client.table("user_quotas").upsert({
            "user_id": user_id,
            "plan_type": "pro",
            "stripe_customer_id": stripe_customer_id,
            "stripe_payment_id": stripe_payment_id,
            "paid_at": paid_at,
        }, on_conflict="user_id").execute()
        
        # Verify the upgrade worked
        if result.data:
            logger.info(f"Successfully upgraded user {user_id} to pro tier")
        else:
            logger.error(f"UPSERT returned no data for user {user_id} - upgrade may have failed")
        
    except Exception as e:
        # Log with proper severity - this is a critical payment issue!
        logger.error(f"CRITICAL: Failed to upgrade user {user_id} to pro tier: {e}")
        logger.error(f"Stripe customer: {stripe_customer_id}, payment: {stripe_payment_id}")
        # Re-raise so webhook returns error and Stripe retries
        raise


@router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(
    user: UserResponse = Depends(get_current_user),
):
    """
    Get the current user's billing status and URL quota.
    """
    user_id = user.id
    
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
    if plan_type in ["pro", "enterprise"]:
        try:
            result = supabase_client.service_client.table("user_quotas").select(
                "paid_at"
            ).eq("user_id", user_id).limit(1).execute()
            if result.data and len(result.data) > 0:
                paid_at = result.data[0].get("paid_at")
        except Exception:
            pass
    
    return BillingStatusResponse(
        plan_type=plan_type,
        is_paid=plan_type in ["pro", "enterprise"],
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
