"""
Constants module for AEOChecker application.

This module contains constant values used throughout the application.
"""
from enum import Enum, auto

class UserCredits:
    """Constants related to user credits"""
    PERSISTENT_USER = 1
    ANONYMOUS_USER = 0
    PREMIUM_USER = 10

class AnalysisStatus(str, Enum):
    """Constants related to analysis status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed" 
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"

PROVIDER_MODELS = {
    "openai": ["gpt-4.1-mini", "gpt-4o-mini"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
    "gemini": ["gemini-2.5-flash-lite-preview-06-17", "gemini-2.0-flash"],
    "perplexity": ["sonar"]
}

MODEL_FIELD_MAPPING = {
    "gpt-4.1-mini": "gpt_4_1_mini",
    "gpt-4o-mini": "gpt_4o_mini",
    "claude-sonnet-4-20250514": "claude_sonnet_4_20250514",
    "claude-3-5-haiku-20241022": "claude_3_5_haiku_20241022",
    "gemini-2.5-flash-lite-preview-06-17": "gemini_2_5_flash_lite_preview_06_17",
    "gemini-2.0-flash": "gemini_2_0_flash",
    "sonar": "perplexity" 
}