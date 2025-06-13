from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.schemas.analysis import AnalyzeRequest, AnalysisStatus, AnalysisResult
from app.api.deps import get_current_user, check_user_credits
from app.services import AnalysisService
from typing import Dict, Any
from app.core.constants import AnalysisStatus as AnalysisStatusConstants

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(get_current_user)]
)

@router.post("/analyze", response_model=AnalysisStatus)
async def analyze_site(request: AnalyzeRequest, background_tasks: BackgroundTasks, user_data=Depends(check_user_credits)):
    """
    Analyze a website and return the job ID for polling status
    """
    user = user_data["user"]
    
    initial_job_data = await AnalysisService.create_analysis_job(
        url=str(request.url),
        user_id=user["uid"]
    )
    
    job_id = initial_job_data["job_id"]
    
    background_tasks.add_task(
        AnalysisService.perform_analysis_task,
        job_id=job_id,
        url=str(request.url),
        user_id=user["uid"]
    )
    
    return AnalysisStatus(**initial_job_data)

@router.get("/status/{job_id}", response_model=AnalysisStatus)
async def job_status(job_id: str, user=Depends(get_current_user)):
    """
    Get the status of an analysis job
    """
    status_data = await AnalysisService.get_job_status(job_id, user["uid"])
    
    if status_data.get("status") == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if status_data.get("status") == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this job"
        )
    
    return AnalysisStatus(**status_data)

@router.get("/reports/{job_id}", response_model=AnalysisResult)
async def get_report(job_id: str, user=Depends(get_current_user)):
    """
    Get a complete analysis report
    """
    report_data = await AnalysisService.get_job_report(job_id, user["uid"])
    
    if report_data.get("status") == AnalysisStatusConstants.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if report_data.get("status") == AnalysisStatusConstants.FORBIDDEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this report"
        )
    
    if report_data.get("status") != AnalysisStatusConstants.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report is not ready yet. Current status: {report_data.get('status')}"
        )
    
    return report_data.get("result") 