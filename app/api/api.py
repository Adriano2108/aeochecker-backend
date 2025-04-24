from fastapi import APIRouter
from app.api.routes import analysis, user

api_router = APIRouter()

# Include all route modules
api_router.include_router(analysis.router)
api_router.include_router(user.router) 