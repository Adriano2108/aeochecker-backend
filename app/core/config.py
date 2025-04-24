import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AEOChecker API"
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "https://aeochecker.vercel.app"
    ]
    
    # Firebase
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "")
    
    class Config:
        case_sensitive = True


settings = Settings() 