from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal, Optional
from app.api.deps import get_current_user

from app.services import StripeService

# Router for authenticated Stripe endpoints
router = APIRouter(
    prefix="/stripe",
    tags=["stripe"],
    dependencies=[Depends(get_current_user)]
)

# Router for public Stripe webhook endpoint (no auth dependency here)
webhook_router = APIRouter(
    prefix="/stripe", # Assuming same prefix, adjust if needed in main.py
    tags=["stripe"]   # Can share tags or have a different one
)

class CheckoutSessionRequest(BaseModel):
    tier_id: Literal['starter', 'developer'] = Field(alias="tierId")

class CheckoutSessionResponse(BaseModel):
    sessionId: str
    url: str

class PortalSessionResponse(BaseModel):
    url: str

@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session_endpoint(request_data: CheckoutSessionRequest, user=Depends(get_current_user)):
    """
    Create a Stripe Checkout session for the selected product.
    Requires `tierId` ('starter' or 'developer'). User info is from token.
    """
    user_email = user.get("decoded_token", {}).get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token.")

    try:
        session = await StripeService.create_checkout_session(request_data.tier_id, user["uid"], user_email)
        return session
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.post("/create-portal-session", response_model=PortalSessionResponse)
async def create_portal_session_endpoint(user=Depends(get_current_user)):
    """
    Create a Stripe Customer Portal session for subscription management.
    User info is taken from the token.
    """
    user_email = user.get("decoded_token", {}).get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token.")

    try:
        portal_session = await StripeService.create_portal_session(user["uid"])
        return {"url": portal_session.url}
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# Move webhook to the new router
@webhook_router.post("/webhook", tags=["stripe"], dependencies=[])
async def stripe_webhook_endpoint(request: Request):
    """
    Stripe webhook endpoint.
    Stripe will send events to this endpoint.
    The `Stripe-Signature` header is used to verify the event.
    """
    stripe_signature = request.headers.get("Stripe-Signature")
    try:
        return await StripeService.handle_stripe_webhook(request, stripe_signature)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing error.") 