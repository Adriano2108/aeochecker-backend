from pydantic import HttpUrl, field_validator
from typing import List, Optional, Any, Tuple
from datetime import datetime
from app.core.constants import AnalysisStatus as AnalysisStatusConstants
from app.core.models import CamelCaseModel, to_camel_case

class AnalyzeRequest(CamelCaseModel):
    url: HttpUrl

class AnalysisTask(CamelCaseModel):
    id: str
    title: str
    result: Any
    score: float
    completed: bool

    @field_validator('id', mode='before')
    def camel_case_id_value(cls, v: Any) -> Any:
        if isinstance(v, str):
            return to_camel_case(v)
        return v

class CompetitorEntry(CamelCaseModel):
    name: str
    count: int
    
class CompetitorLandscapeAnalysisResult(CamelCaseModel):
    sorted_competitors: List[CompetitorEntry]
    included: bool


class AnalysisResult(CamelCaseModel):
    url: HttpUrl
    score: float
    title: str
    dummy: bool
    analysis_synthesis: str
    analysis_items: List[AnalysisTask]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "score": 85.5,
                "title": "Analysis Title",
                "dummy": False,
                "analysis_synthesis": "This is an example of the analysis synthesis",
                "analysis_items": [
                    {"id": "task1", "title": "SEO Analysis", "result": "Good SEO practices found", "completed": True},
                    {"id": "task2", "title": "Performance Check", "result": "Site loads quickly", "completed": True},
                    {"id": "task3", "title": "Accessibility", "result": "Some accessibility issues found", "completed": True},
                    {"id": "task4", "title": "Mobile Friendly", "result": "Site is mobile friendly", "completed": True}
                ],
                "created_at": "2023-07-10T14:23:56.123Z"
            }
        }

class AnalysisStatus(CamelCaseModel):
    job_id: str
    status: AnalysisStatusConstants
    progress: Optional[float] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123",
                "status": AnalysisStatusConstants.PROCESSING,
                "progress": 0.75,
                "error": None
            }
        }

class ReportSummary(CamelCaseModel):
    url: HttpUrl
    title: str
    score: float
    created_at: datetime
    analysis_synthesis: str
    job_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "title": "Analysis Title",
                "score": 85.5,
                "createdAt": "2023-07-10T14:23:56.123Z",
                "analysisSynthesis": "Analysis Synthesis"
            }
        }

class ShareLink(CamelCaseModel):
    share_url: HttpUrl

    class Config:
        json_schema_extra = {
            "example": {
                "shareUrl": "https://aeochecker.ai/results?share=abc123def456ghi789"
            }
        } 