import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import Literal
from datetime import datetime

load_dotenv()

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AEOChecker API"
    APP_ENV: Literal["development", "production"] = os.getenv("APP_ENV", "development")
    BACKEND_LAST_BREAKING_CHANGE_DATE: str = os.getenv("BACKEND_LAST_BREAKING_CHANGE_DATE", datetime(2025, 7, 4, 10, 0, 0).isoformat())
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "https://aeochecker.vercel.app",
        "https://aeochecker.ai",
        "https://www.aeochecker.ai",
    ]

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://aeochecker.ai")
    
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "")
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")
    
    # LLM API Configuration
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    LLM_CONNECT_TIMEOUT_SECONDS: int = int(os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "10"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_RETRY_BASE_DELAY: float = float(os.getenv("LLM_RETRY_BASE_DELAY", "1.0"))
    
    # Production Stripe Variables
    STRIPE_SECRET_KEY_PROD: str = os.getenv("STRIPE_SECRET_KEY_PROD", "")
    STRIPE_WEBHOOK_SECRET_PROD: str = os.getenv("STRIPE_WEBHOOK_SECRET_PROD", "")
    STRIPE_PRICE_ID_STARTER_PROD: str = os.getenv("STRIPE_PRICE_ID_STARTER_PROD", "")
    STRIPE_PRICE_ID_DEVELOPER_PROD: str = os.getenv("STRIPE_PRICE_ID_DEVELOPER_PROD", "")

    # Development Stripe Variables
    STRIPE_SECRET_KEY_DEV: str = os.getenv("STRIPE_SECRET_KEY_DEV", "")
    STRIPE_WEBHOOK_SECRET_DEV: str = os.getenv("STRIPE_WEBHOOK_SECRET_DEV", "")
    STRIPE_PRICE_ID_STARTER_DEV: str = os.getenv("STRIPE_PRICE_ID_STARTER_DEV", "")
    STRIPE_PRICE_ID_DEVELOPER_DEV: str = os.getenv("STRIPE_PRICE_ID_DEVELOPER_DEV", "")

    # Reddit API Variables
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "")

    @property
    def STRIPE_SECRET_KEY(self) -> str:
        if self.APP_ENV == "production":
            return self.STRIPE_SECRET_KEY_PROD
        return self.STRIPE_SECRET_KEY_DEV

    @property
    def STRIPE_WEBHOOK_SECRET(self) -> str:
        if self.APP_ENV == "production":
            return self.STRIPE_WEBHOOK_SECRET_PROD
        return self.STRIPE_WEBHOOK_SECRET_DEV

    @property
    def STRIPE_PRICE_ID_STARTER(self) -> str:
        if self.APP_ENV == "production":
            return self.STRIPE_PRICE_ID_STARTER_PROD
        return self.STRIPE_PRICE_ID_STARTER_DEV

    @property
    def STRIPE_PRICE_ID_DEVELOPER(self) -> str:
        if self.APP_ENV == "production":
            return self.STRIPE_PRICE_ID_DEVELOPER_PROD
        return self.STRIPE_PRICE_ID_DEVELOPER_DEV
    
    class Config:
        case_sensitive = True


settings = Settings() 