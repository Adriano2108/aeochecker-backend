from typing import Dict, Any, Optional, List
from app.core.firebase import db
from firebase_admin import firestore

class UserService:
    """Service for user data management"""
    
    @staticmethod
    async def get_user_data(user_id: str) -> Dict[str, Any]:
        """
        Retrieve user data from Firestore
        """
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return None
        
        return user_doc.to_dict()
    
    @staticmethod
    async def get_user_reports(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve user's analysis reports
        """
        reports_ref = db.collection("users").document(user_id).collection("reports")
        reports = reports_ref.order_by("created_at", direction="DESCENDING").limit(limit).stream()
        
        return [report.to_dict() for report in reports]
    
    @staticmethod
    async def add_credits(user_id: str, credits: int) -> Dict[str, Any]:
        """
        Add credits to user account
        """
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"credits": firestore.Increment(credits)})
        
        # Get updated user data
        user_doc = user_ref.get()
        return user_doc.to_dict()
    
    @staticmethod
    async def create_user_if_not_exists(user_id: str, email: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new user record in Firestore if it doesn't exist
        """
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            user_data = {
                "uid": user_id,
                "email": email,
                "display_name": display_name or email.split("@")[0],
                "credits": 3,
                "created_at": firestore.SERVER_TIMESTAMP,
                "reports": []
            }
            
            user_ref.set(user_data)
            return user_data
        
        return user_doc.to_dict() 