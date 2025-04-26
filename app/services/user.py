from typing import Dict, Any, Optional, List
from app.core.firebase import db
from firebase_admin import firestore
from datetime import datetime

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
        
        user_data = user_doc.to_dict()
        if user_data.get("created_at") and not isinstance(user_data["created_at"], datetime):
            user_data["created_at"] = user_data["created_at"].datetime() if hasattr(user_data["created_at"], "datetime") else datetime.now()
        
        if "email" in user_data and (user_data["email"] == "" or user_data["email"] is None):
            user_data["email"] = None
        
        return user_data
    
    @staticmethod
    async def get_user_reports(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve user's analysis reports
        """
        reports_ref = db.collection("users").document(user_id).collection("reports")
        reports = reports_ref.order_by("created_at", direction="DESCENDING").limit(limit).stream()
        
        result = []
        for report in reports:
            report_data = report.to_dict()
            if report_data.get("created_at") and not isinstance(report_data["created_at"], datetime):
                report_data["created_at"] = report_data["created_at"].datetime() if hasattr(report_data["created_at"], "datetime") else datetime.now()
            result.append(report_data)
        
        return result

    @staticmethod
    async def create_user_if_not_exists(user_id: str, email: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new user record in Firestore if it doesn't exist
        """
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            current_time = datetime.now()
            email_value = None if not email or email == "" else email
            user_data = {
                "uid": user_id,
                "email": email_value,
                "display_name": display_name or (email.split("@")[0] if email else f"User_{user_id[:6]}"),
                "credits": 3,
                "created_at": current_time,
                "reports": []
            }
            
            storage_data = user_data.copy()
            storage_data["created_at"] = firestore.SERVER_TIMESTAMP
            
            user_ref.set(storage_data)
            return user_data
        
        user_data = user_doc.to_dict()
        if user_data.get("created_at") and not isinstance(user_data["created_at"], datetime):
            user_data["created_at"] = user_data["created_at"].datetime() if hasattr(user_data["created_at"], "datetime") else datetime.now()
        
        if "email" in user_data and (user_data["email"] == "" or user_data["email"] is None):
            user_data["email"] = None
        
        return user_data 

    @staticmethod
    async def promote_user(user_id: str, email: Optional[str] = None, display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Promote a user from anonymous to persistent authentication
        
        Updates:
        - Sets persistent field to true
        - Updates email and display_name if provided
        - Sets credits to 5
        """
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return None
        
        update_data = {
            "persistent": True,
            "credits": 5
        }
        
        if email is not None and email != "":
            update_data["email"] = email
            
        if display_name is not None and display_name != "":
            update_data["display_name"] = display_name
            
        user_ref.update(update_data)
        
        # Get updated user data
        updated_user = user_ref.get().to_dict()
        if updated_user.get("created_at") and not isinstance(updated_user["created_at"], datetime):
            updated_user["created_at"] = updated_user["created_at"].datetime() if hasattr(updated_user["created_at"], "datetime") else datetime.now()
        
        if "email" in updated_user and (updated_user["email"] == "" or updated_user["email"] is None):
            updated_user["email"] = None
            
        return updated_user 