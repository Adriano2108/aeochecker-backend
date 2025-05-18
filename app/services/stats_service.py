from app.core.firebase import db
from firebase_admin import firestore
from datetime import datetime

class StatsService:
    @staticmethod
    async def increment_checkout_created_count(product_id: str):
        """
        Increments the checkout_created_count for a given product_id in the 'stats' collection.
        """
        stats_ref = db.collection("stats").document(product_id)
        
        try:
            await stats_ref.update({
                "checkout_created_count": firestore.Increment(1),
            })
            print(f"Incremented checkout_created_count for product: {product_id}")
        except Exception as e:
            if "No document to update" in str(e) or "NOT_FOUND" in str(e):
                await stats_ref.set({
                    "checkout_created_count": 1,
                }, merge=True)
                print(f"Initialized checkout_created_count for product: {product_id}")
            else:
                print(f"Error incrementing checkout_created_count for {product_id}: {e}")
                raise

    @staticmethod
    async def increment_job_created_count():
        """
        Increments the job_created_count in the 'stats' collection under a document named 'analysis_jobs'.
        """
        stats_ref = db.collection("stats").document("analysis_jobs")
        
        try:
            await stats_ref.update({
                "job_created_count": firestore.Increment(1),
            })
            print("Incremented job_created_count for analysis_jobs")
        except Exception as e:
            if "No document to update" in str(e) or "NOT_FOUND" in str(e):
                await stats_ref.set({
                    "job_created_count": 1,
                }, merge=True)
                print("Initialized job_created_count for analysis_jobs")
            else:
                print(f"Error incrementing job_created_count: {e}")
                raise 