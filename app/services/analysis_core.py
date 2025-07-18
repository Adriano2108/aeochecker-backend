import uuid
import json
import secrets
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.firebase import db
from firebase_admin import firestore
from app.core.constants import AnalysisStatus as AnalysisStatusConstants
from app.services.analysis import AiPresenceAnalyzer, CompetitorLandscapeAnalyzer, StrategyReviewAnalyzer
from app.services.analysis.utils.scrape_utils import scrape_website, scrape_company_facts, _validate_and_get_best_url
from app.services.analysis.utils.response import generate_analysis_synthesis, generate_dummy_report
from app.services.analysis.utils.subscription_utils import has_active_subscription
from app.services.stats_service import StatsService
from app.core.config import settings
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
        try:
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
                
        except Exception as e:
            error_message = str(e)
            user_friendly_error = ""
            
            print(f"Error scraping website for job {job_id}: {error_message}")
            
            # Provide specific error messages based on the type of error
            if "403" in error_message or "Access forbidden" in error_message:
                user_friendly_error = (
                    "The website is blocking automated access. This is common with large e-commerce sites "
                    "that have strict bot protection. Please try again later, or contact support if this "
                    "issue persists with your website."
                )
            elif "404" in error_message or "Page not found" in error_message:
                user_friendly_error = (
                    "The website could not be found. Please check that the URL is correct and the website "
                    "is accessible."
                )
            elif "429" in error_message or "Rate limited" in error_message:
                user_friendly_error = (
                    "The website is rate limiting requests. Please wait a few minutes and try again."
                )
            elif "timeout" in error_message.lower() or "took too long" in error_message:
                user_friendly_error = (
                    "The website took too long to respond. This might be due to server issues or slow "
                    "internet connection. Please try again in a few minutes."
                )
            elif "SSL" in error_message or "certificate" in error_message:
                user_friendly_error = (
                    "There's an SSL certificate issue with the website. This might be a temporary problem "
                    "with the website's security configuration. Please try again later."
                )
            elif "Failed to connect" in error_message or "connection" in error_message.lower():
                user_friendly_error = (
                    "Unable to connect to the website. Please check that the URL is correct and the website "
                    "is online and accessible."
                )
            elif "nodename nor servname provided" in error_message:
                user_friendly_error = (
                    "The website address could not be resolved. Please check that the URL is correct and "
                    "the website exists."
                )
            else:
                user_friendly_error = (
                    "An unexpected error occurred while trying to access the website. Please check that "
                    "the URL is correct and try again. If the problem persists, contact support."
                )
            
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": user_friendly_error,
                "error_details": error_message,  # Keep technical details for debugging
                "completed_at": datetime.now().isoformat()
            })
            return None, None, None
        
        try:
            # Extract company facts
            company_facts = await scrape_company_facts(url, soup, all_text)
            print(f"Company facts for job {job_id}: {json.dumps(company_facts, indent=4)}")
            
            if company_facts["name"] == "":
                print(f"No information found for website in job {job_id}.")
                job_ref.update({
                    "status": AnalysisStatusConstants.FAILED,
                    "error": "No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis.",
                    "completed_at": datetime.now().isoformat()
                })
                return None, None, None
            
        except Exception as e:
            print(f"Error extracting company facts for job {job_id}: {str(e)}")
            job_ref.update({
                "status": AnalysisStatusConstants.FAILED,
                "error": "Failed to extract information from the website. The website might be missing important metadata or have an unusual structure.",
                "error_details": str(e),
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
        
        # Add overall score to AI presence result
        ai_presence_result = analysis_results["ai_presence"].copy()
        ai_presence_result["score"] = analysis_scores["ai_presence"]
        
        analysis_items = [
            {
                "id": "ai_presence",
                "title": "AI Presence",
                "score": analysis_scores["ai_presence"],
                "result": ai_presence_result,
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
            "dummy": False,
            "deleted": False,
            "company_info": {
                "name": company_facts.get('name', ''),
                "industry": company_facts.get('industry', ''),
                "key_products_services": company_facts.get('key_products_services', []),
                "description": company_facts.get('description', '')
            }
        }

        # Update job status to completed
        job_ref.update({
            "status": AnalysisStatusConstants.COMPLETED,
            "progress": 1.0,
            "completed_at": datetime.now().isoformat(),
        })
        print(f"Analysis completed for job {job_id}")
        
        # Check if user has active subscription before deducting credit
        user_ref = db.collection("users").document(user_id)
        user = user_ref.get()
        
        if user.exists:
            user_data = user.to_dict()
            subscription = user_data.get("subscription")
            
            # Only deduct credit if user doesn't have an active subscription
            if not (subscription and subscription.get("status") == "active" and subscription.get("type") in ["starter", "developer"]):
                user_ref.update({"credits": firestore.Increment(-1)})
                print(f"Credit deducted for job {job_id}")
            else:
                print(f"Credit deduction skipped for job {job_id} - user has active subscription")
        else:
            print(f"Warning: User {user_id} not found when trying to deduct credit for job {job_id}")
        
        # Save report to user's reports collection
        report_ref = db.collection("users").document(user_id).collection("reports").document(job_id)
        report_ref.set(result_data)
        print(f"Report saved for job {job_id}")

    @staticmethod
    def _build_sharing_metadata(job_data: dict) -> dict:
        """
        Build sharing metadata from job data
        """
        return {
            "sharing": {
                "is_public": job_data.get("public", False),
                "share_token": job_data.get("share_token"),
                "shared_at": job_data.get("shared_at"),
                "view_count": job_data.get("view_count", 0),
                "share_url": f"results?share={job_data.get('share_token')}" if job_data.get("share_token") else None
            }
        }

    @staticmethod
    def _migrate_old_report_format(result: dict) -> dict:
        """
        Migrate old report formats to the current expected schema format.
        This handles backward compatibility for reports created before schema changes.
        """
        if not result.get("analysis_items"):
            return result
        
        migrated_items = []
        
        for item in result["analysis_items"]:
            # Ensure camelCase conversion for IDs
            if item.get("id") == "ai_presence":
                item["id"] = "aiPresence"
            elif item.get("id") == "competitor_landscape":
                item["id"] = "competitorLandscape"
            elif item.get("id") == "strategy_review":
                item["id"] = "strategyReview"
            
            # Handle AI Presence migration
            if item.get("id") == "aiPresence":
                # Ensure the result has a score field at the root level
                if "result" in item and "score" not in item.get("result", {}):
                    item["result"]["score"] = item.get("score", 0.0)
                migrated_items.append(item)
                
            # Handle Competitor Landscape migration  
            elif item.get("id") == "competitorLandscape":
                # Ensure each LLM result has the required fields
                if "result" in item:
                    for llm_name in ["openai", "anthropic", "gemini", "perplexity"]:
                        if llm_name in item["result"] and item["result"][llm_name]:
                            llm_result = item["result"][llm_name]
                            # Add missing fields if they don't exist
                            if "competitors" not in llm_result:
                                llm_result["competitors"] = []
                            if "included" not in llm_result:
                                llm_result["included"] = False
                migrated_items.append(item)
                
            # Handle Strategy Review migration (most complex)
            elif item.get("id") == "strategyReview":
                if "result" in item:
                    old_result = item["result"]
                    new_result = {}
                    
                    # Migrate knowledge_base to web_presence
                    if "knowledge_base" in old_result:
                        kb = old_result["knowledge_base"]
                        new_result["web_presence"] = {
                            "wikipedia": {
                                "has_wikipedia_page": kb.get("has_wikipedia_page", False),
                                "wikipedia_url": kb.get("wikipedia_url"),
                                "score": kb.get("score", 0.0)
                            },
                            "reddit": {
                                "subreddit": {"label": "Subreddit ownership", "raw_value": False, "score": 0.0},
                                "members": {"label": "Members", "raw_value": 0, "score": 0.0},
                                "mention_volume": {"label": "30-day mentions", "raw_value": 0, "score": 0.0},
                                "engagement": {"label": "Avg karma+replies", "raw_value": 0.0, "score": 0.0},
                                "recency": {"label": "Latest mention hrs", "raw_value": None, "score": 0.0},
                                "diversity": {"label": "Unique subreddits", "raw_value": 0, "score": 0.0},
                                "total_score": 0.0
                            },
                            "total_score": kb.get("score", 0.0)
                        }
                    elif "web_presence" in old_result:
                        new_result["web_presence"] = old_result["web_presence"]
                    else:
                        # Create default web_presence
                        new_result["web_presence"] = {
                            "wikipedia": {
                                "has_wikipedia_page": False,
                                "wikipedia_url": None,
                                "score": 0.0
                            },
                            "reddit": {
                                "subreddit": {"label": "Subreddit ownership", "raw_value": False, "score": 0.0},
                                "members": {"label": "Members", "raw_value": 0, "score": 0.0},
                                "mention_volume": {"label": "30-day mentions", "raw_value": 0, "score": 0.0},
                                "engagement": {"label": "Avg karma+replies", "raw_value": 0.0, "score": 0.0},
                                "recency": {"label": "Latest mention hrs", "raw_value": None, "score": 0.0},
                                "diversity": {"label": "Unique subreddits", "raw_value": 0, "score": 0.0},
                                "total_score": 0.0
                            },
                            "total_score": 0.0
                        }
                    
                    # Add missing fields with defaults if they don't exist
                    if "answerability" not in old_result:
                        new_result["answerability"] = {
                            "total_phrases": 0,
                            "is_good_length_phrase": 0,
                            "is_conversational_phrase": 0,
                            "has_statistics_phrase": 0,
                            "has_citation_phrase": 0,
                            "has_citations_section": False,
                            "score": 0.0
                        }
                    else:
                        new_result["answerability"] = old_result["answerability"]
                    
                    if "structured_data" not in old_result:
                        new_result["structured_data"] = {
                            "schema_markup_present": False,
                            "schema_types_found": [],
                            "specific_schemas": {
                                "faq_page": False,
                                "article": False,
                                "review": False
                            },
                            "semantic_elements": {
                                "present": False,
                                "unique_types_found": [],
                                "count_unique_types": 0,
                                "all_tags_count": 0,
                                "semantic_tags_count": 0,
                                "non_semantic_tags_count": 0,
                                "semantic_ratio": 0.0
                            },
                            "score": 0.0
                        }
                    else:
                        # Handle potential old specific_schemas format
                        structured_data = old_result["structured_data"].copy()
                        if "specific_schemas" in structured_data:
                            old_specific = structured_data["specific_schemas"]
                            # Map old field names to new field names
                            new_specific = {
                                "faq_page": old_specific.get("FAQPage", old_specific.get("faq_page", False)),
                                "article": old_specific.get("Article", old_specific.get("article", False)),
                                "review": old_specific.get("Review", old_specific.get("review", False))
                            }
                            structured_data["specific_schemas"] = new_specific
                        new_result["structured_data"] = structured_data
                    
                    if "ai_crawler_accessibility" not in old_result:
                        new_result["ai_crawler_accessibility"] = {
                            "sitemap_found": False,
                            "robots_txt_found": False,
                            "llms_txt_found": False,
                            "llm_txt_found": False,
                            "pre_rendered_content": {
                                "likely_pre_rendered": False,
                                "text_length": 0,
                                "js_framework_hint": False
                            },
                            "language": {
                                "detected_languages": ["en"],
                                "is_english": False,
                                "english_version_url": None
                            },
                            "score": 0.0
                        }
                    else:
                        new_result["ai_crawler_accessibility"] = old_result["ai_crawler_accessibility"]
                    
                    # Update the item with the new result structure
                    item["result"] = new_result
                
                migrated_items.append(item)
            else:
                # For any other items, keep as-is
                migrated_items.append(item)
        
        # Update the result with migrated items
        result["analysis_items"] = migrated_items
        return result

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
        
        response = {
            "job_id": job_id,
            "error": job_data.get("error", None),
            "status": job_data.get("status"),
            "progress": job_data.get("progress", 0)
        }
        
        # Include error details if available (for debugging/logging)
        if job_data.get("error_details"):
            response["error_details"] = job_data.get("error_details")
        
        return response
    
    @staticmethod
    async def get_job_report(job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get the complete analysis report for a job with sharing metadata
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
        
        # Backward compatibility: ensure deleted field exists
        if "deleted" not in result:
            result["deleted"] = False
        
        # Check if report is deleted
        if result.get("deleted", False):
            return {"status": AnalysisStatusConstants.NOT_FOUND}

        # Apply migration for old report formats
        result = AnalysisService._migrate_old_report_format(result)

        user_ref = db.collection("users").document(user_id)
        user = user_ref.get()
        user_data = user.to_dict()
        
        if not has_active_subscription(user_data):
            result = generate_dummy_report(result)
        
        sharing_metadata = AnalysisService._build_sharing_metadata(job_data)
        
        enriched_result = {**result, **sharing_metadata}
            
        print(json.dumps(enriched_result, indent=4))
        return {"status": AnalysisStatusConstants.COMPLETED, "result": enriched_result}

    @staticmethod
    async def create_share_link(job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Create a shareable link for a job report
        """
        # Check if user owns the job
        job_ref = db.collection("analysis_jobs").document(job_id)
        job = job_ref.get()
        
        if not job.exists or job.to_dict().get("user_id") != user_id:
            return {"status": "forbidden"}
        
        job_data = job.to_dict()
        
        # Generate token only once
        if not job_data.get("public", False):
            token = secrets.token_urlsafe(16)  # 128 bits ~ 22 chars
            job_ref.update({
                "public": True, 
                "share_token": token,
                "shared_at": datetime.now().isoformat(),  # Track when it was shared
                "view_count": 0  # Initialize view counter
            })
        else:
            token = job_data["share_token"]
        
        # Return the share URL
        share_url = f"results?share={token}"
        return {"share_url": share_url}

    @staticmethod
    async def get_public_report(share_token: str, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get a report by its public share token.
        Returns dummy report if user is not authenticated or not persistent.
        """
        # Lookup job by token
        jobs_ref = db.collection("analysis_jobs")
        query = jobs_ref.where("share_token", "==", share_token).limit(1)
        docs = query.get()
        
        if not docs:
            return {"status": AnalysisStatusConstants.NOT_FOUND}
        
        job_snapshot = docs[0]
        job_data = job_snapshot.to_dict()
        
        # Make sure the job is really public and finished
        if not job_data.get("public"):
            return {"status": AnalysisStatusConstants.FORBIDDEN}
        
        if job_data.get("status") != AnalysisStatusConstants.COMPLETED:
            return {"status": "not_ready", "current_status": job_data.get("status")}
        
        # Increment view count for analytics
        try:
            job_snapshot.reference.update({"view_count": firestore.Increment(1)})
        except Exception as e:
            print(f"Warning: Could not update view count for {share_token}: {e}")
        
        # Pull the actual report out of the owner's sub-collection
        owner_uid = job_data["user_id"]
        report_ref = (
            db.collection("users")
            .document(owner_uid)
            .collection("reports")
            .document(job_snapshot.id)
        )
        report = report_ref.get()
        
        if not report.exists:
            return {"status": AnalysisStatusConstants.NOT_FOUND}
        
        result = report.to_dict()
        
        # Backward compatibility: ensure deleted field exists
        if "deleted" not in result:
            result["deleted"] = False
        
        # Check if report is deleted
        if result.get("deleted", False):
            return {"status": AnalysisStatusConstants.NOT_FOUND}
        
        # Apply migration for old report formats
        result = AnalysisService._migrate_old_report_format(result)
        
        should_show_dummy = True

        if user:
            user_ref = db.collection("users").document(user["uid"])
            user_doc = user_ref.get()
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                should_show_dummy = not has_active_subscription(user_data)
        
        if should_show_dummy:
            result = generate_dummy_report(result)
        
        sharing_metadata = AnalysisService._build_sharing_metadata(job_data)
        
        enriched_result = {**result, **sharing_metadata}
        
        return {"status": AnalysisStatusConstants.COMPLETED, "result": enriched_result}

    @staticmethod
    async def delete_report(job_id: str, user_id: str) -> Dict[str, Any]:
        """
        Soft delete an analysis report by setting deleted=True.
        Only the report owner can delete their report.
        """
        # Check if the report exists in user's reports collection
        report_ref = db.collection("users").document(user_id).collection("reports").document(job_id)
        report = report_ref.get()
        
        if not report.exists:
            return {"status": "not_found"}
        
        report_data = report.to_dict()
        
        # Check if report is already deleted
        if report_data.get("deleted", False):
            return {"status": "not_found"}
        
        # Soft delete the report by setting deleted=True
        report_ref.update({"deleted": True})
        
        return {"status": "success"}