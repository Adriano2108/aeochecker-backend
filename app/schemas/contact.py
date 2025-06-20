from pydantic import EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.schemas.user import UserInDB
from app.core.models import CamelCaseModel

class ContactMessageBase(CamelCaseModel):
    user: Optional[UserInDB] = None
    email: Optional[EmailStr] = None
    message: str

    @field_validator('email', mode='before')
    @classmethod
    def empty_str_to_none(cls, value):
        if isinstance(value, str) and value == '':
            return None
        return value

class ContactMessageCreate(ContactMessageBase):
    pass

class ContactMessageInDB(ContactMessageBase):
    id: str
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg_12345",
                "user": {
                    "uid": "abc123def456",
                    "email": "user@example.com",
                    "username": "John",
                    "credits": 2,
                    "createdAt": "2023-07-01T10:00:00.000Z",
                    "reports": ["report1", "report2"],
                    "persistent": False,
                    "subscription": {
                        "id": "sub_1234567890",
                        "status": "active",
                        "type": "starter"
                    }
                },
                "email": None,
                "message": "Hello, I have a question.",
                "createdAt": "2023-07-15T12:00:00.000Z"
            }
        } 