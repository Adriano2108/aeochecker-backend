from fastapi import APIRouter, Depends
from app.services.stats_service import StatsService
from app.schemas.stats import AnalysisCountResponse

router = APIRouter(
  prefix="/stats", 
  tags=["Stats"],
)

@router.get("/analysis-count", response_model=AnalysisCountResponse)
async def get_analysis_count():
    """
    Retrieve the total count of website analyses performed.
    """
    count = await StatsService.get_analysis_job_count()
    return AnalysisCountResponse(count=count) 