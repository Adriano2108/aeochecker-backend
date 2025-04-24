from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

class AnalyzeRequest(BaseModel):
    url: HttpUrl

class AnalysisTask(BaseModel):
    id: str
    description: str
    result: str
    completed: bool

class AnalysisResult(BaseModel):
    url: HttpUrl
    score: float
    tasks: List[AnalysisTask]
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "score": 85.5,
                "tasks": [
                    {"id": "task1", "description": "SEO Analysis", "result": "Good SEO practices found", "completed": True},
                    {"id": "task2", "description": "Performance Check", "result": "Site loads quickly", "completed": True},
                    {"id": "task3", "description": "Accessibility", "result": "Some accessibility issues found", "completed": True},
                    {"id": "task4", "description": "Mobile Friendly", "result": "Site is mobile friendly", "completed": True}
                ],
                "created_at": "2023-07-10T14:23:56.123Z"
            }
        }

class AnalysisStatus(BaseModel):
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: Optional[float] = None
    result: Optional[AnalysisResult] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "abc123",
                "status": "processing",
                "progress": 0.75,
                "result": None
            }
        } 