"""
Constants module for AEOChecker application.

This module contains constant values used throughout the application.
"""

# User Credits
class UserCredits:
    """Constants related to user credits"""
    PERSISTENT_USER = 3
    ANONYMOUS_USER = 1
    PREMIUM_USER = 10

# User Types
class UserTypes:
    """Constants related to user types"""
    ANONYMOUS = "anonymous"
    PERSISTENT = "persistent"
    PREMIUM = "premium"

# Analysis Status
class AnalysisStatus:
    """Constants related to analysis status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed" 