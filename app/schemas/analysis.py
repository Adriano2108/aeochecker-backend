from pydantic import HttpUrl, Field
from typing import List, Optional
from datetime import datetime
from app.core.constants import AnalysisStatus as AnalysisStatusConstants, AnalysisTagType
from app.core.models import CamelCaseModel

class AnalyzeRequest(CamelCaseModel):
    url: HttpUrl

class AnalysisTask(CamelCaseModel):
    id: str
    title: str
    tag_type: AnalysisTagType
    result: str
    completed: bool

class AnalysisResult(CamelCaseModel):
    url: HttpUrl
    score: float
    title: str
    analysis_synthesis: str
    analysis_items: List[AnalysisTask]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "score": 85.5,
                "title": "Analysis Title",
                "analysis_synthesis": "Analysis Synthesis",
                "analysis_items": [
                    {"id": "task1", "title": "SEO Analysis", "tag_type": "important", "result": "Good SEO practices found", "completed": True},
                    {"id": "task2", "title": "Performance Check", "tag_type": "high_impact", "result": "Site loads quickly", "completed": True},
                    {"id": "task3", "title": "Accessibility", "tag_type": "fixes", "result": "Some accessibility issues found", "completed": True},
                    {"id": "task4", "title": "Mobile Friendly", "tag_type": "important", "result": "Site is mobile friendly", "completed": True}
                ],
                "created_at": "2023-07-10T14:23:56.123Z"
            }
        }

class AnalysisStatus(CamelCaseModel):
    job_id: str
    status: AnalysisStatusConstants
    progress: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123",
                "status": AnalysisStatusConstants.PROCESSING,
                "progress": 0.75,
            }
        } 