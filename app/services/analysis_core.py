import uuid
import json
from typing import Dict, Any
from datetime import datetime
from app.core.firebase import db
from firebase_admin import firestore
from app.core.constants import AnalysisStatus as AnalysisStatusConstants
from app.services.analysis import AiPresenceAnalyzer, CompetitorLandscapeAnalyzer, StrategyReviewAnalyzer
from app.services.analysis.utils.scrape_utils import scrape_website, scrape_company_facts, _validate_and_get_best_url
from app.services.analysis.utils.response import generate_analysis_synthesis

class AnalysisService:
    """Service for analyzing websites and generating reports"""
    
    @classmethod
    async def analyze_website(cls, url: str, user_id: str) -> Dict[str, Any]:
        """
        Perform full website analysis
        """
        job_id = str(uuid.uuid4())
        
        job_ref = db.collection("analysis_jobs").document(job_id)
        job_ref.set({
            "url": url,
            "user_id": user_id,
            "status": AnalysisStatusConstants.PROCESSING,
            "created_at": datetime.now().isoformat(),
            "progress": 0
        })

        print(f"Analyzing website: {url}")

        try:
            validated_url = await _validate_and_get_best_url(url)
            if validated_url != url:
                url = validated_url
        except Exception as e:
            print(f"Error validating URL: {str(e)}")
            return {"job_id": job_id, "status": AnalysisStatusConstants.FAILED, "error": str(e)}
        
        print(f"Validated URL: {url}")
        
        try:
            # Instantiate analyzers
            ai_presence_analyzer = AiPresenceAnalyzer()
            competitor_landscape_analyzer = CompetitorLandscapeAnalyzer()
            strategy_review_analyzer = StrategyReviewAnalyzer()

            # Scrape website
            print("Scraping website...")
            soup, all_text = await scrape_website(url)
            print(f"Scraped website")
            if soup is None:
                print("Failed to scrape website. Please try again later.")
                return {"job_id": job_id, "status": AnalysisStatusConstants.FAILED, "error": "Failed to scrape website. Please try again later."}
            
            print("Scraping company facts...")
            company_facts = await scrape_company_facts(soup)
            print(f"Company facts: {company_facts}")
            if company_facts["name"] == "":
                print("No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis.")
                return {"job_id": job_id, "status": AnalysisStatusConstants.FAILED, "error": "No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis."}
                
            # Run analyses
            print("Running AI Presence analysis...")
            ai_presence_score, ai_presence_result = await ai_presence_analyzer.analyze(company_facts)
            job_ref.update({"progress": 0.5})
            print(f"ai_presence_score: {ai_presence_score}")

            print("Running Competitor Landscape analysis...")
            competitor_landscape_score, competitors_result = await competitor_landscape_analyzer.analyze(company_facts)
            job_ref.update({"progress": 0.75})
            print(f"competitor_landscape_score: {competitor_landscape_score}")

            print("Running Strategy Review analysis...")
            strategy_review_score, strategy_review_result = await strategy_review_analyzer.analyze(company_facts["name"], url, soup, all_text)
            job_ref.update({"progress": 1.0})
            print(f"strategy_review_score: {strategy_review_score}")
            
            overall_score = (ai_presence_score + competitor_landscape_score + strategy_review_score) / 3

            print(f"Overall score: {overall_score}")
            
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
            
            result = {
                "url": url,
                "score": overall_score,
                "title": f"{company_facts['name']} Report",
                "analysis_synthesis": generate_analysis_synthesis(company_facts['name'], overall_score),
                "analysis_items": analysis_items,
                "created_at": datetime.now().isoformat(),
                "job_id": job_id
            }

            print(f"Analysis items: {analysis_items}")
            
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
            report_ref.set(result)

            print(json.dumps(result, indent=4))
            
            return {"job_id": job_id, "status": AnalysisStatusConstants.COMPLETED, "result": result}
            
        except Exception as e:
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
            print(f"Error analyzing website: {str(e)}")
            return {"job_id": job_id, "status": AnalysisStatusConstants.FAILED, "error": str(e)}
    
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
        
        print(json.dumps(report.to_dict(), indent=4))
            
        result = report.to_dict()
        return {"status": AnalysisStatusConstants.COMPLETED, "result": result}