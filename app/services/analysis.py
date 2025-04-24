import uuid
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Tuple
from datetime import datetime
from app.core.firebase import db
from firebase_admin import firestore

class AnalysisService:
    """Service for analyzing websites and generating reports"""
    
    @staticmethod
    async def perform_seo_analysis(url: str) -> Tuple[float, str]:
        """
        Analyze SEO aspects of the website
        Returns: (score, description)
        """
        # Placeholder for actual implementation
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Example: Check for title and meta description
                title = soup.title.string if soup.title else None
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                
                # Calculate a simple score (actual implementation would be more complex)
                score = 0
                if title and len(title) > 5:
                    score += 25
                if meta_desc:
                    score += 25
                
                return score, "SEO elements analyzed successfully"
                
        except Exception as e:
            return 0, f"SEO analysis failed: {str(e)}"
    
    @staticmethod
    async def perform_performance_check(url: str) -> Tuple[float, str]:
        """
        Check website performance metrics
        Returns: (score, description)
        """
        # Placeholder for actual implementation
        try:
            async with httpx.AsyncClient() as client:
                start_time = datetime.now()
                response = await client.get(url)
                load_time = (datetime.now() - start_time).total_seconds()
                
                # Simple scoring based on load time
                if load_time < 1:
                    score = 100
                elif load_time < 2:
                    score = 75
                elif load_time < 3:
                    score = 50
                else:
                    score = 25
                    
                return score, f"Site load time: {load_time:.2f}s"
                
        except Exception as e:
            return 0, f"Performance check failed: {str(e)}"
    
    @staticmethod
    async def check_accessibility(url: str) -> Tuple[float, str]:
        """
        Analyze website accessibility
        Returns: (score, description)
        """
        # Placeholder for actual implementation
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Example: Check for alt attributes on images
                images = soup.find_all('img')
                images_with_alt = [img for img in images if img.get('alt')]
                
                if not images:
                    score = 50
                    message = "No images found to check for alt text"
                else:
                    alt_percentage = len(images_with_alt) / len(images) * 100
                    score = alt_percentage
                    message = f"{alt_percentage:.1f}% of images have alt text"
                
                return score, message
                
        except Exception as e:
            return 0, f"Accessibility check failed: {str(e)}"
    
    @staticmethod
    async def check_mobile_friendly(url: str) -> Tuple[float, str]:
        """
        Check if website is mobile-friendly
        Returns: (score, description)
        """
        # Placeholder for actual implementation
        try:
            async with httpx.AsyncClient() as client:
                # Set a mobile user agent
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
                }
                response = await client.get(url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check for viewport meta tag
                viewport = soup.find('meta', attrs={'name': 'viewport'})
                
                score = 75 if viewport else 25
                message = "Viewport meta tag found" if viewport else "No viewport meta tag"
                
                return score, message
                
        except Exception as e:
            return 0, f"Mobile-friendly check failed: {str(e)}"
    
    @classmethod
    async def analyze_website(cls, url: str, user_id: str) -> Dict[str, Any]:
        """
        Perform full website analysis
        """
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create a job record in Firestore
        job_ref = db.collection("analysis_jobs").document(job_id)
        job_ref.set({
            "url": url,
            "user_id": user_id,
            "status": "processing",
            "created_at": datetime.now(),
            "progress": 0
        })
        
        try:
            # Perform all analysis tasks
            seo_score, seo_result = await cls.perform_seo_analysis(url)
            job_ref.update({"progress": 0.25})
            
            perf_score, perf_result = await cls.perform_performance_check(url)
            job_ref.update({"progress": 0.5})
            
            acc_score, acc_result = await cls.check_accessibility(url)
            job_ref.update({"progress": 0.75})
            
            mobile_score, mobile_result = await cls.check_mobile_friendly(url)
            
            # Calculate overall score (equal weights for simplicity)
            overall_score = (seo_score + perf_score + acc_score + mobile_score) / 4
            
            # Prepare the result object
            tasks = [
                {"id": "seo", "description": "SEO Analysis", "result": seo_result, "completed": True},
                {"id": "performance", "description": "Performance Check", "result": perf_result, "completed": True},
                {"id": "accessibility", "description": "Accessibility", "result": acc_result, "completed": True},
                {"id": "mobile", "description": "Mobile Friendly", "result": mobile_result, "completed": True},
            ]
            
            result = {
                "url": url,
                "score": overall_score,
                "tasks": tasks,
                "created_at": datetime.now()
            }
            
            # Update the job with the final result
            job_ref.update({
                "status": "completed",
                "progress": 1.0,
                "result": result,
                "completed_at": datetime.now()
            })
            
            # Deduct a credit from the user
            user_ref = db.collection("users").document(user_id)
            user_ref.update({"credits": firestore.Increment(-1)})
            
            # Save the report to the user's reports collection
            report_ref = db.collection("users").document(user_id).collection("reports").document(job_id)
            report_ref.set(result)
            
            return {"job_id": job_id, "status": "completed", "result": result}
            
        except Exception as e:
            # Update job with error status
            job_ref.update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now()
            })
            return {"job_id": job_id, "status": "failed", "error": str(e)}
    
    @staticmethod
    async def get_job_status(job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get the status of an analysis job
        """
        job_ref = db.collection("analysis_jobs").document(job_id)
        job = job_ref.get()
        
        if not job.exists:
            return {"status": "not_found"}
        
        job_data = job.to_dict()
        
        # Check if the job belongs to the user
        if job_data.get("user_id") != user_id:
            return {"status": "forbidden"}
        
        return {
            "job_id": job_id,
            "status": job_data.get("status"),
            "progress": job_data.get("progress", 0)
        }
    
    @staticmethod
    async def get_job_report(job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get the complete analysis report for a job
        """
        job_ref = db.collection("analysis_jobs").document(job_id)
        job = job_ref.get()
        
        if not job.exists:
            return {"status": "not_found"}
        
        job_data = job.to_dict()
        
        # Check if the job belongs to the user
        if job_data.get("user_id") != user_id:
            return {"status": "forbidden"}
            
        # Check if job is completed
        if job_data.get("status") != "completed":
            return {
                "status": job_data.get("status"),
                "progress": job_data.get("progress", 0)
            }
        
        # Return the full result if job is completed
        return {
            "status": "completed",
            "result": job_data.get("result")
        } 