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
import asyncio

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
            StatsService.increment_job_created_count()
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
        
        try:
            # Step 1: Validate URL (progress 0.10)
            validated_url = await cls._validate_url(job_id, url, job_ref)
            if not validated_url:
                return
            
            # Step 2: Scrape website & company facts (progress 0.20)
            soup, all_text, company_facts = await cls._scrape_website_data(job_id, validated_url, job_ref)
            if not company_facts:
                return
            
            # Step 3: Run analyses in parallel (progress +0.20 each)
            analysis_scores, analysis_results = await cls._run_parallel_analyses(job_id, company_facts, validated_url, soup, all_text, job_ref)
            if not analysis_scores:
                return
            
            # Step 4: Calculate overall score
            overall_score = cls._calculate_overall_score(analysis_scores)
            
            # Step 5: Build analysis items
            analysis_items = cls._build_analysis_items(analysis_scores, analysis_results)
            
            # Step 6: Finalize report (deduct credit & save)
            await cls._finalize_report(job_id, user_id, validated_url, overall_score, company_facts, analysis_items, job_ref)
            
        except Exception as e:
            print(f"DEBUG: Exception caught in perform_analysis_task for job {job_id}: {str(e)}")
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
            print(f"Error analyzing website for job {job_id}: {str(e)}")

    @classmethod
    async def _validate_url(cls, job_id: str, url: str, job_ref) -> str:
        """Validate and get the best URL for analysis."""
        try:
            validated_url = await _validate_and_get_best_url(url)
            job_ref.update({"progress": 0.10})
            print(f"Validated URL for job {job_id}: {validated_url}")
            return validated_url
        except Exception as e:
            print(f"Error validating URL for job {job_id}: {str(e)}")
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            })
            return None

    @classmethod
    async def _scrape_website_data(cls, job_id: str, url: str, job_ref) -> tuple:
        """Scrape website content and extract company facts."""
        # Scrape website
        soup, all_text = await scrape_website(url)
        print(f"Scraped website for job {job_id}")
        
        if soup is None:
            print(f"Failed to scrape website for job {job_id}.")
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": "Failed to scrape website. Please try again later.",
                "completed_at": datetime.now().isoformat()
            })
            return None, None, None
        
        # Extract company facts
        company_facts = await scrape_company_facts(url, soup, all_text)
        print(f"Company facts for job {job_id}: {company_facts}")
        
        if company_facts["name"] == "":
            print(f"No information found for website in job {job_id}.")
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": "No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis.",
                "completed_at": datetime.now().isoformat()
            })
            return None, None, None
        
        job_ref.update({"progress": 0.20})
        print(f"Progress updated to 0.20 for job {job_id}")
        
        return soup, all_text, company_facts

    @classmethod
    async def _run_parallel_analyses(cls, job_id: str, company_facts: dict, url: str, soup, all_text: str, job_ref) -> tuple:
        """Run all three analyses in parallel and track progress."""
        # Instantiate analyzers
        ai_presence_analyzer = AiPresenceAnalyzer()
        competitor_landscape_analyzer = CompetitorLandscapeAnalyzer()
        strategy_review_analyzer = StrategyReviewAnalyzer()

        # Create tasks for each analysis
        ai_task = asyncio.create_task(ai_presence_analyzer.analyze(company_facts))
        competitor_task = asyncio.create_task(competitor_landscape_analyzer.analyze(company_facts))
        strategy_task = asyncio.create_task(
            strategy_review_analyzer.analyze(company_facts["name"], url, soup, all_text)
        )

        try:
            results = await asyncio.gather(ai_task, competitor_task, strategy_task, return_exceptions=True)
            
            task_names = ["ai_presence", "competitor_landscape", "strategy_review"]
            analysis_scores: Dict[str, float] = {}
            analysis_results: Dict[str, Any] = {}
            
            for i, result in enumerate(results):
                analysis_name = task_names[i]
                
                if isinstance(result, Exception):
                    job_ref.update({
                        "status": AnalysisStatusConstants.FAILED,
                        "error": f"{analysis_name} analysis failed: {str(result)}",
                        "completed_at": datetime.now().isoformat(),
                    })
                    print(f"Error during {analysis_name} analysis for job {job_id}: {str(result)}")
                    return None, None
                
                score, analysis_result = result
                analysis_scores[analysis_name] = score
                analysis_results[analysis_name] = analysis_result
                
                # Update progress (+0.20 for each completed analysis)
                progress = 0.20 + (i + 1) * 0.20
                job_ref.update({"progress": min(progress, 0.80)})
                print(f"Progress updated to {min(progress, 0.80)} for job {job_id} - {analysis_name} completed")
                
        except Exception as e:
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": f"Analysis execution failed: {str(e)}",
                "completed_at": datetime.now().isoformat(),
            })
            print(f"Error during analysis execution for job {job_id}: {str(e)}")
            return None, None

        return analysis_scores, analysis_results

    @classmethod
    def _calculate_overall_score(cls, analysis_scores: Dict[str, float]) -> float:
        """Calculate the overall analysis score."""
        return sum(analysis_scores.values()) / len(analysis_scores)

    @classmethod
    def _build_analysis_items(cls, analysis_scores: Dict[str, float], analysis_results: Dict[str, Any]) -> list:
        """Build the analysis items structure for the report."""
        analysis_items = [
            {
                "id": "ai_presence",
                "title": "AI Presence",
                "score": analysis_scores["ai_presence"],
                "result": analysis_results["ai_presence"],
                "completed": True
            },
            {
                "id": "competitor_landscape",
                "title": "Competitor Landscape",
                "score": analysis_scores["competitor_landscape"],
                "result": analysis_results["competitor_landscape"].model_dump() if hasattr(analysis_results["competitor_landscape"], 'model_dump') else analysis_results["competitor_landscape"],
                "completed": True
            },
            {
                "id": "strategy_review",
                "title": "Strategy Review",
                "score": analysis_scores["strategy_review"],
                "result": analysis_results["strategy_review"],
                "completed": True
            },
        ]
        
        # Serialize to ensure all nested Pydantic models are properly converted
        return json.loads(json.dumps(analysis_items, default=str))

    @classmethod
    async def _finalize_report(cls, job_id: str, user_id: str, url: str, overall_score: float, company_facts: dict, analysis_items: list, job_ref):
        """Deduct credit and save the final report."""
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

        # Update job status to completed
        job_ref.update({
            "status": AnalysisStatusConstants.COMPLETED,
            "progress": 1.0,
            "completed_at": datetime.now().isoformat(),
        })
        print(f"Analysis completed for job {job_id}")
        
        # Deduct credit from user
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"credits": firestore.Increment(-1)})
        print(f"Credit deducted for job {job_id}")
        
        # Save report to user's reports collection
        report_ref = db.collection("users").document(user_id).collection("reports").document(job_id)
        report_ref.set(result_data)
        print(f"Report saved for job {job_id}")

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