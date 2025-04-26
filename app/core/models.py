import re
from pydantic import BaseModel
from datetime import datetime

def to_camel_case(snake_str):
    """Convert snake_case string to camelCase"""
    return re.sub(r'_([a-z])', lambda m: m.group(1).upper(), snake_str)

class CamelCaseModel(BaseModel):
    """Base model that converts all snake_case field names to camelCase in JSON output"""
    
    class Config:
        alias_generator = to_camel_case
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
        
        from_attributes = True  # Support for model creation from ORM objects 