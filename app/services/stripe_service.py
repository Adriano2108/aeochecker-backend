import stripe
from fastapi import HTTPException, Request
from typing import Optional
from app.core.config import settings
from app.services.user import UserService

stripe.api_key = settings.STRIPE_SECRET_KEY

PRODUCT_TO_PRICE_MAP = {
    "starter": settings.STRIPE_PRICE_ID_STARTER,
    "developer": settings.STRIPE_PRICE_ID_DEVELOPER,
}

async def create_checkout_session(product_id: str, user_id: str, user_email: str):
    """
    Creates a Stripe Checkout Session for the given product_id.
    product_id can be 'starter' or 'developer'.
    """

    print(f"Checkout function called with product_id: {product_id}, user_id: {user_id}, user_email: {user_email}")
    if product_id not in PRODUCT_TO_PRICE_MAP:
        raise HTTPException(status_code=400, detail="Invalid product ID")

    price_id = PRODUCT_TO_PRICE_MAP[product_id]
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=settings.FRONTEND_URL,
            customer_email = user_email,
            metadata={
                "user_id": user_id,
                "plan_name": product_id
            },
            subscription_data={
                "metadata": {
                    "user_id": user_id,
                    "plan_name": product_id
                }
            }
        )
        return {"sessionId": checkout_session.id, "url": checkout_session.url}
    except Exception as e:
        print(f"Error creating Stripe checkout session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def create_portal_session(user_id: str):
    """
    Creates a Stripe Customer Portal session for subscription management.
    Requires the user_id to find their Stripe customer ID.
    """
    try:
        user_data = await UserService.get_user_data(user_id)
        
        if not user_data or not user_data.get("subscription") or not user_data.get("subscription", {}).get("customer_id"):
            raise HTTPException(status_code=404, detail="No active subscription found for this user")
        
        customer_id = user_data.get("subscription", {}).get("customer_id")
        
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=settings.FRONTEND_URL,
        )
        
        return portal_session
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error creating Stripe portal session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def handle_stripe_webhook(request: Request, stripe_signature: Optional[str]):
    """
    Handles incoming Stripe webhooks.
    Verifies the event signature and processes the event.
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        user_id = metadata.get('user_id')
        plan_name = metadata.get('plan_name')
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        print(f"Checkout session completed for user: {user_id}, plan: {plan_name}")
        print(f"Customer ID: {customer_id}, Subscription ID: {subscription_id}")

        if user_id and subscription_id and plan_name and customer_id:
            if plan_name not in ["starter", "developer"]:
                print(f"Error: Invalid plan_name '{plan_name}' from session metadata for user {user_id}.")
            else:
                await UserService.update_user_subscription_details(user_id, subscription_id, "active", plan_name, customer_id)
        else:
            print(f"Error: Missing user_id, subscription_id, plan_name, or customer_id in checkout.session.completed for session {session.get('id')}")
        
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        print(f"Invoice payment succeeded: {invoice['id']}")
        
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        print(f"Invoice payment failed: {invoice['id']}")

    elif event['type'] == 'customer.subscription.deleted':
        subscription_obj = event['data']['object']
        metadata = subscription_obj.get('metadata', {})
        user_id = metadata.get('user_id')
        plan_name = metadata.get('plan_name')
        subscription_id = subscription_obj.get('id')
        customer_id = subscription_obj.get('customer')
        
        print(f"Subscription {subscription_id} deleted for user: {user_id}, plan: {plan_name}")

        if user_id and subscription_id and plan_name:
            if plan_name not in ["starter", "developer"]:
                print(f"Error: Invalid plan_name '{plan_name}' from subscription metadata for user {user_id}, subscription {subscription_id}.")
            else:
                user_data = await UserService.get_user_data(user_id)
                existing_customer_id = None
                if user_data and user_data.get("subscription"):
                    existing_customer_id = user_data.get("subscription", {}).get("customer_id")
                final_customer_id = customer_id or existing_customer_id
                
                await UserService.update_user_subscription_details(
                    user_id, 
                    subscription_id, 
                    "cancelled", 
                    plan_name, 
                    final_customer_id
                )
        else:
            print(f"Error: Missing user_id, subscription_id, or plan_name in customer.subscription.deleted for subscription {subscription_id}")

    elif event['type'] == 'customer.subscription.updated':
        subscription_obj = event['data']['object']
        # Check for cancellation via 'incomplete_expired' or if status is 'canceled'
        # Stripe might also send 'canceled' status directly if a subscription is canceled e.g. due to payment failures after retries
        if subscription_obj.get('status') == 'incomplete_expired' or subscription_obj.get('cancel_at_period_end') is True or subscription_obj.get('status') == 'canceled':
            metadata = subscription_obj.get('metadata', {})
            user_id = metadata.get('user_id')
            plan_name = metadata.get('plan_name')
            subscription_id = subscription_obj.get('id')
            customer_id = subscription_obj.get('customer')

            print(f"Subscription {subscription_id} updated (likely cancelled/expired) for user: {user_id}, plan: {plan_name}, status: {subscription_obj.get('status')}")

            if user_id and subscription_id and plan_name:
                if plan_name not in ["starter", "developer"]:
                    print(f"Error: Invalid plan_name '{plan_name}' from subscription metadata for user {user_id}, subscription {subscription_id}.")
                else:
                    user_data = await UserService.get_user_data(user_id)
                    existing_customer_id = None
                    if user_data and user_data.get("subscription"):
                        existing_customer_id = user_data.get("subscription", {}).get("customer_id")
                    final_customer_id = customer_id or existing_customer_id
                    
                    await UserService.update_user_subscription_details(
                        user_id, 
                        subscription_id, 
                        "cancelled", 
                        plan_name, 
                        final_customer_id
                    )
            else:
                print(f"Error: Missing user_id, subscription_id, or plan_name in customer.subscription.updated for subscription {subscription_id}")
        else:
            print(f"Unhandled subscription update status for {subscription_obj.get('id')}: {subscription_obj.get('status')}")
        
    else:
        print(f"Unhandled event type {event['type']}")

    return {"status": "success"}
