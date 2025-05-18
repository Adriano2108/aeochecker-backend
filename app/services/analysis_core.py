import uuid
import json
from typing import Dict, Any
from datetime import datetime
from app.core.firebase import db
from firebase_admin import firestore
from app.core.constants import AnalysisStatus as AnalysisStatusConstants
from app.services.analysis import AiPresenceAnalyzer, CompetitorLandscapeAnalyzer, StrategyReviewAnalyzer
from app.services.analysis.utils.scrape_utils import scrape_website, scrape_company_facts, _validate_and_get_best_url
from app.services.analysis.utils.response import generate_analysis_synthesis, generate_dummy_report
from app.services.stats_service import StatsService

class AnalysisService:
    """Service for analyzing websites and generating reports"""
    
    @classmethod
    async def create_analysis_job(cls, url: str, user_id: str) -> Dict[str, Any]:
        """
        Create an initial analysis job entry and return its details.
        """
        job_id = str(uuid.uuid4())
        job_ref = db.collection("analysis_jobs").document(job_id)

        try:
            await StatsService.increment_job_created_count()
        except Exception as e:
            print(f"Failed to log job creation for job {job_id}: {e}")
        
        initial_job_data = {
            "url": url,
            "user_id": user_id,
            "status": AnalysisStatusConstants.PROCESSING,
            "created_at": datetime.now().isoformat(),
            "progress": 0
        }
        job_ref.set(initial_job_data) 
        
        return {
            "job_id": job_id,
            "status": AnalysisStatusConstants.PROCESSING,
            "progress": 0
        }

    @classmethod
    async def perform_analysis_task(cls, job_id: str, url: str, user_id: str):
        """
        Perform full website analysis as a background task.
        Updates Firestore with progress and final status/result.
        """
        job_ref = db.collection("analysis_jobs").document(job_id)

        print(f"Background task started for job_id: {job_id}, url: {url}")
        
        try:
            validated_url = await _validate_and_get_best_url(url)
            if validated_url != url:
                url = validated_url
        except Exception as e:
            print(f"Error validating URL for job {job_id}: {str(e)}")
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
            return 
        
        print(f"Validated URL for job {job_id}: {url}")
        
        try:
            # Instantiate analyzers
            ai_presence_analyzer = AiPresenceAnalyzer()
            competitor_landscape_analyzer = CompetitorLandscapeAnalyzer()
            strategy_review_analyzer = StrategyReviewAnalyzer()

            # Scrape website
            print(f"Scraping website for job {job_id}...")
            soup, all_text = await scrape_website(url)
            print(f"Scraped website for job {job_id}")
            if soup is None:
                print(f"Failed to scrape website for job {job_id}.")
                job_ref.update({
                    "status": AnalysisStatusConstants.FAILED,
                    "error": "Failed to scrape website. Please try again later.",
                    "completed_at": datetime.now().isoformat()
                })
                return

            print(f"Scraping company facts for job {job_id}...")
            company_facts = await scrape_company_facts(url, soup, all_text)
            print(f"Company facts for job {job_id}: {company_facts}")
            if company_facts["name"] == "":
                print(f"No information found for website in job {job_id}.")
                job_ref.update({
                    "status": AnalysisStatusConstants.FAILED,
                    "error": "No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis.",
                    "completed_at": datetime.now().isoformat()
                })
                return
                
            # Run analyses
            ai_presence_score, ai_presence_result = await ai_presence_analyzer.analyze(company_facts)
            job_ref.update({"progress": 0.5})

            competitor_landscape_score, competitors_result = await competitor_landscape_analyzer.analyze(company_facts)
            job_ref.update({"progress": 0.75})

            strategy_review_score, strategy_review_result = await strategy_review_analyzer.analyze(company_facts["name"], url, soup, all_text)
            
            overall_score = (ai_presence_score + competitor_landscape_score + strategy_review_score) / 3

            analysis_items = [
                {
                    "id": "ai_presence",
                    "title": "AI Presence",
                    "score": ai_presence_score,
                    "result": ai_presence_result,
                    "completed": True
                },
                {
                    "id": "competitor_landscape",
                    "title": "Competitor Landscape",
                    "score": competitor_landscape_score,
                    "result": competitors_result.model_dump(),
                    "completed": True
                },
                {
                    "id": "strategy_review",
                    "title": "Strategy Review",
                    "score": strategy_review_score,
                    "result": strategy_review_result,
                    "completed": True
                },
            ]
            
            result_data = {
                "url": url,
                "score": overall_score,
                "title": company_facts['name'],
                "analysis_synthesis": generate_analysis_synthesis(company_facts['name'], overall_score),
                "analysis_items": analysis_items,
                "created_at": datetime.now().isoformat(),
                "job_id": job_id,
                "dummy": False
            }

            job_ref.update({
                "status": AnalysisStatusConstants.COMPLETED,
                "progress": 1.0,
                "completed_at": datetime.now().isoformat()
            })
            
            # Deduct a credit from the user
            user_ref = db.collection("users").document(user_id)
            user_ref.update({"credits": firestore.Increment(-1)})
            
            # Save the report to the user's reports collection
            report_ref = db.collection("users").document(user_id).collection("reports").document(job_id)
            report_ref.set(result_data)

            print(f"Analysis for job {job_id} completed. Report saved: {json.dumps(result_data, indent=4)}")
            
        except Exception as e:
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
            print(f"Error analyzing website for job {job_id}: {str(e)}")
    
    @staticmethod
    async def get_job_status(job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get the status of an analysis job
        """
        job_ref = db.collection("analysis_jobs").document(job_id)
        job = job_ref.get()
        
        if not job.exists:
            return {"status": AnalysisStatusConstants.NOT_FOUND}
        
        job_data = job.to_dict()
        
        # Check if the job belongs to the user
        if job_data.get("user_id") != user_id:
            return {"status": AnalysisStatusConstants.FORBIDDEN}
        
        return {
            "job_id": job_id,
            "error": job_data.get("error", None),
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
            return {"status": AnalysisStatusConstants.NOT_FOUND}
        
        job_data = job.to_dict()
        
        # Check if the job belongs to the user
        if job_data.get("user_id") != user_id:
            return {"status": AnalysisStatusConstants.FORBIDDEN}
            
        # Check if job is completed
        if job_data.get("status") != AnalysisStatusConstants.COMPLETED:
            return {
                "status": job_data.get("status"),
                "progress": job_data.get("progress", 0)
            }
        
        # Get the report from the user's reports collection
        report_ref = db.collection("users").document(user_id).collection("reports").document(job_id)
        report = report_ref.get()
        
        if not report.exists:
            return {"status": AnalysisStatusConstants.NOT_FOUND}
        
        result = report.to_dict()

        user_ref = db.collection("users").document(user_id)
        user = user_ref.get()
        user_data = user.to_dict()
        
        if not user_data.get("persistent", False):
            result = generate_dummy_report(result)
            
        print(json.dumps(result, indent=4))
        return {"status": AnalysisStatusConstants.COMPLETED, "result": result}