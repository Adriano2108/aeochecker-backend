from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field
from typing import Literal
from app.api.deps import get_current_user

from app.services import stripe_service

router = APIRouter(
    prefix="/stripe",
    tags=["stripe"],
    dependencies=[Depends(get_current_user)]
)

class CheckoutSessionRequest(BaseModel):
    tier_id: Literal['starter', 'developer'] = Field(alias="tierId")

class CheckoutSessionResponse(BaseModel):
    sessionId: str
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
        session = await stripe_service.create_checkout_session(request_data.tier_id, user["uid"], user_email)
        return session
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.post("/webhook", tags=["stripe"])
async def stripe_webhook_endpoint(request: Request, user=Depends(get_current_user), stripe_signature: str = Header(None)):
    """
    Stripe webhook endpoint.
    Stripe will send events to this endpoint.
    The `Stripe-Signature` header is used to verify the event.
    """
    try:
        return await stripe_service.handle_stripe_webhook(request, user, stripe_signature)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing error.") 