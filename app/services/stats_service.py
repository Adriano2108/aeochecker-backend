from app.core.firebase import db
from firebase_admin import firestore
from datetime import datetime
from app.core.config import settings

class StatsService:
    @staticmethod
    def increment_checkout_created_count(product_id: str):
        """
        Increments the checkout_created_count for a given product_id in the 'stats' collection.
        """
        stats_ref = db.collection("stats").document(product_id)

        if settings.APP_ENV != "production":
            return
        
        try:
            stats_ref.update({
                "checkout_created_count": firestore.Increment(1),
            })
        except Exception as e:
            if "No document to update" in str(e) or "NOT_FOUND" in str(e):
                stats_ref.set({
                    "checkout_created_count": 1,
                }, merge=True)
                print(f"Initialized checkout_created_count for product: {product_id}")
            else:
                print(f"Error incrementing checkout_created_count for {product_id}: {e}")
                raise

    @staticmethod
    def increment_job_created_count():
        """
        Increments the job_created_count in the 'stats' collection under a document named 'analysis_jobs'.
        """
        stats_ref = db.collection("stats").document("analysis_jobs")

        if settings.APP_ENV != "production":
            return
        
        try:
            stats_ref.update({
                "job_created_count": firestore.Increment(1),
            })
        except Exception as e:
            if "No document to update" in str(e) or "NOT_FOUND" in str(e):
                stats_ref.set({
                    "job_created_count": 1,
                }, merge=True)
                print("Initialized job_created_count for analysis_jobs")
            else:
                print(f"Error incrementing job_created_count: {e}")
                raise

    @staticmethod
    def get_analysis_job_count() -> int:
        """
        Retrieves the job_created_count from the 'stats' collection under a document named 'analysis_jobs'.
        Returns 0 if the document or field does not exist.
        """
        stats_ref = db.collection("stats").document("analysis_jobs")
        
        try:
            doc = stats_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("job_created_count", 0)
            else:
                return 0
        except Exception as e:
            print(f"Error retrieving job_created_count: {e}")
            return 0