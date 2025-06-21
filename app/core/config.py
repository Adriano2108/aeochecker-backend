import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import Literal

load_dotenv()

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AEOChecker API"
    APP_ENV: Literal["development", "production"] = os.getenv("APP_ENV", "development") # type: ignore
    
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