from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.analysis import AnalyzeRequest, AnalysisStatus, AnalysisResult
from app.api.deps import get_current_user, check_user_credits
from app.services.analysis import AnalysisService
from typing import Dict, Any

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(get_current_user)]
)

@router.post("/analyze", response_model=AnalysisStatus)
async def analyze_site(request: AnalyzeRequest, user_data=Depends(check_user_credits)):
    """
    Analyze a website and return the job ID for polling status
    """
    user = user_data["user"]
    
    # Start the analysis process
    result = await AnalysisService.analyze_website(
        url=str(request.url),
        user_id=user["uid"]
    )
    
    return result

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
    
    return status_data

@router.get("/reports/{job_id}", response_model=AnalysisResult)
async def get_report(job_id: str, user=Depends(get_current_user)):
    """
    Get a complete analysis report
    """
    report_data = await AnalysisService.get_job_report(job_id, user["uid"])
    
    if report_data.get("status") == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if report_data.get("status") == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this report"
        )
    
    if report_data.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report is not ready yet. Current status: {report_data.get('status')}"
        )
    
    return report_data.get("result") 