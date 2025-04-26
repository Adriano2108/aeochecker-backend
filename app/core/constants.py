"""
Constants module for AEOChecker application.

This module contains constant values used throughout the application.
"""
from enum import Enum, auto

class UserCredits:
    """Constants related to user credits"""
    PERSISTENT_USER = 3
    ANONYMOUS_USER = 1
    PREMIUM_USER = 10

class UserTypes(str, Enum):
    """Constants related to user types"""
    ANONYMOUS = "anonymous"
    PERSISTENT = "persistent"
    PREMIUM = "premium"

class AnalysisStatus(str, Enum):
    """Constants related to analysis status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed" 
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"

class AnalysisTagType(str, Enum):
    """Constants related to analysis tag type"""
    FIXES = "fixes"
    HIGH_IMPACT = "high_impact"
    IMPORTANT = "important"
