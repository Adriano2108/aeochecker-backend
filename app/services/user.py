from typing import Dict, Any, Optional, List
from app.core.firebase import db, firebase_auth
from firebase_admin import firestore
from datetime import datetime
from app.core.constants import UserCredits, UserTypes
from app.schemas.analysis import ReportSummary

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
    async def get_user_reports(user_id: str, limit: int = 10) -> List[ReportSummary]:
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
            
            summary = ReportSummary(
                url=report_data.get("url"),
                title=report_data.get("title"),
                score=report_data.get("score"),
                created_at=report_data.get("created_at"),
                analysis_synthesis=report_data.get("analysis_synthesis"),
                job_id=report.id
            )
            result.append(summary)
        
        return result

    @staticmethod
    async def create_user_if_not_exists(user_id: str, email: str, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new user record in Firestore if it doesn't exist
        """

        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            current_time = datetime.now()

            user_type = UserTypes.PERSISTENT if email else UserTypes.ANONYMOUS
            user_credits = UserCredits.PERSISTENT_USER if email else UserCredits.ANONYMOUS_USER
            email_value = None if not email or email == "" else email
            username_value = username or (email.split("@")[0] if email else f"User_{user_id[:6]}")
            
            user_data = {
                "uid": user_id,
                "email": email_value,
                "username": username_value,
                "credits": user_credits,
                "user_type": user_type,
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
    async def promote_user(user_id: str, email: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Promote a user from anonymous to persistent authentication
        
        Updates:
        - Sets persistent field to true
        - Updates email and username if provided
        - Sets credits to persistent user credits value
        """
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return None
        
        update_data = {
            "persistent": True,
            "credits": UserCredits.PERSISTENT_USER
        }
        
        if email is not None and email != "":
            update_data["email"] = email
            
        if username is not None and username != "":
            update_data["username"] = username
            
        user_ref.update(update_data)
        
        # Get updated user data
        updated_user = user_ref.get().to_dict()
        if updated_user.get("created_at") and not isinstance(updated_user["created_at"], datetime):
            updated_user["created_at"] = updated_user["created_at"].datetime() if hasattr(updated_user["created_at"], "datetime") else datetime.now()
        
        if "email" in updated_user and (updated_user["email"] == "" or updated_user["email"] is None):
            updated_user["email"] = None
            
        return updated_user 

    @staticmethod
    async def delete_user(user_id: str) -> bool:
        """
        Delete a user from both Firestore database and Firebase Auth
        
        1. Delete user document from Firestore
        2. Delete any subcollections (reports, etc.)
        3. Delete user from Firebase Auth
        """
        try:
            # Check if user exists in Firestore
            user_ref = db.collection("users").document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                return False
            
            # Delete reports subcollection if it exists
            reports_ref = user_ref.collection("reports")
            reports = reports_ref.stream()
            for report in reports:
                report.reference.delete()
            
            # Delete the user document from Firestore
            user_ref.delete()
            
            # Delete user from Firebase Auth
            firebase_auth.delete_user(user_id)
            
            return True
        except Exception as e:
            print(f"Error deleting user {user_id}: {str(e)}")
            return False 