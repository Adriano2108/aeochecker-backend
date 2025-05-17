import stripe
from fastapi import HTTPException, Request, Header
from app.core.config import settings
from app.schemas.user import UserInDB

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
                "user_id": user_id 
            },
        )
        return {"sessionId": checkout_session.id, "url": checkout_session.url}
    except Exception as e:
        print(f"Error creating Stripe checkout session: {e}")
        import traceback
        traceback.print_exc() # This will print the full traceback to your console
        raise HTTPException(status_code=500, detail=str(e))

async def handle_stripe_webhook(request: Request, user: UserInDB, stripe_signature: str = Header(None)):
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
        user_id = session.get('metadata', {}).get('user_id')
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        print(f"Checkout session completed for user: {user_id}")
        print(f"Customer ID: {customer_id}, Subscription ID: {subscription_id}")
        # Example: update_user_subscription(user_id, customer_id, subscription_id, session['display_items'][0]['plan']['id'])

    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        # Handle successful payment for recurring subscriptions
        # customer_id = invoice.get('customer')
        # subscription_id = invoice.get('subscription')
        # plan_id = invoice['lines']['data'][0]['plan']['id']
        # user_id = invoice.get('metadata', {}).get('user_id') # if you passed it during session creation or on customer
        # Or retrieve user by customer_id/subscription_id
        print(f"Invoice payment succeeded: {invoice['id']}")
        # Example: handle_recurring_payment(customer_id, subscription_id, plan_id)
        
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        # Handle failed payment
        # Notify the user, etc.
        print(f"Invoice payment failed: {invoice['id']}")

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        # Handle subscription cancellation
        print(f"Subscription deleted: {subscription['id']}")
        # Example: update_user_on_cancellation(subscription['customer'])
        
    # ... handle other event types
    else:
        print(f"Unhandled event type {event['type']}")

    return {"status": "success"}
