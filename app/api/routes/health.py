from fastapi import APIRouter
from app.schemas.health import HealthCheckResponse
from app.core.config import settings

router = APIRouter()

@router.get("/health", response_model=HealthCheckResponse, tags=["health"])
async def health_check():
    """
    Health check endpoint
    """
    return HealthCheckResponse(
        status="ok",
        last_backend_breaking_update=settings.BACKEND_LAST_BREAKING_CHANGE_DATE
    ) 