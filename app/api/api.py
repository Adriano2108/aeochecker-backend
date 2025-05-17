from fastapi import APIRouter
from app.api.routes import analysis, user, contact, stripe

api_router = APIRouter()

# Include all route modules
api_router.include_router(analysis.router)
api_router.include_router(user.router)
api_router.include_router(contact.router)
api_router.include_router(stripe.router)
api_router.include_router(stripe.webhook_router) 