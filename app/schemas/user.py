from pydantic import EmailStr
from typing import List, Optional
from datetime import datetime
from app.core.constants import UserCredits, UserTypes
from app.core.models import CamelCaseModel

class UserBase(CamelCaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None

class UserInDB(UserBase):
    uid: str
    credits: int = 0
    created_at: datetime
    reports: Optional[List[str]] = []
    persistent: Optional[bool] = False
    user_type: UserTypes
    
    class Config:
        json_schema_extra = {
            "example": {
                "uid": "abc123def456",
                "email": "user@example.com",
                "username": "John",
                "credits": UserCredits.PERSISTENT_USER,
                "created_at": "2023-07-01T10:00:00.000Z",
                "reports": ["report1", "report2"],
                "persistent": False,
                "user_type": UserTypes.PERSISTENT
            }
        }

class UserResponse(UserInDB):
    pass 