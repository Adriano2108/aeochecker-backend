from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None

class UserInDB(UserBase):
    uid: str
    credits: int = 0
    created_at: datetime
    reports: Optional[List[str]] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "uid": "abc123def456",
                "email": "user@example.com",
                "display_name": "John Doe",
                "credits": 5,
                "created_at": "2023-07-01T10:00:00.000Z",
                "reports": ["report1", "report2"]
            }
        }

class UserResponse(UserInDB):
    pass 