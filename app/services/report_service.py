from __future__ import annotations
import json
import secrets
from typing import Dict, Any, Optional
from datetime import datetime

from firebase_admin import firestore

from app.core.firebase import db
from app.core.constants import AnalysisStatus as AnalysisStatusConstants
from app.services.analysis.utils.response import generate_dummy_report
from app.services.analysis.utils.subscription_utils import has_active_subscription


class ReportService:
    """Service for managing analysis reports"""

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
        result = ReportService._migrate_old_report_format(result)

        user_ref = db.collection("users").document(user_id)
        user = user_ref.get()
        user_data = user.to_dict()

        if not has_active_subscription(user_data):
            result = generate_dummy_report(result)

        sharing_metadata = ReportService._build_sharing_metadata(job_data)

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
        result = ReportService._migrate_old_report_format(result)

        should_show_dummy = True

        if user:
            user_ref = db.collection("users").document(user["uid"])
            user_doc = user_ref.get()

            if user_doc.exists:
                user_data = user_doc.to_dict()
                should_show_dummy = not has_active_subscription(user_data)

        if should_show_dummy:
            result = generate_dummy_report(result)

        sharing_metadata = ReportService._build_sharing_metadata(job_data)

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
            try:
                # Ensure camelCase conversion for IDs
                if item.get("id") == "ai_presence":
                    item["id"] = "aiPresence"
                elif item.get("id") == "competitor_landscape":
                    item["id"] = "competitorLandscape"
                elif item.get("id") == "strategy_review":
                    item["id"] = "strategyReview"

                # Handle AI Presence migration
                if item.get("id") == "aiPresence":
                    if "result" in item:
                        # Ensure the result has a score field at the root level
                        if "score" not in item.get("result", {}):
                            item["result"]["score"] = item.get("score", 0.0)

                        # Handle old flat provider structure vs new nested structure
                        result_data = item["result"]
                        for provider in ["openai", "anthropic", "gemini", "perplexity"]:
                            if provider in result_data and isinstance(result_data[provider], dict):
                                provider_data = result_data[provider]

                                # Check if this is old flat structure (has direct fields like name, product, industry)
                                if any(key in provider_data for key in ["name", "product", "industry", "uncertainty"]) and "score" not in provider_data:
                                    # Old flat structure - migrate to new nested structure
                                    # Create default nested structure for this provider
                                    result_data[provider] = {
                                        "score": 0.0,
                                        # Add default model results (we can't reconstruct the original model results)
                                    }
                                elif isinstance(provider_data, dict) and "score" not in provider_data:
                                    # Add missing score field
                                    provider_data["score"] = 0.0
                    migrated_items.append(item)

                # Handle Competitor Landscape migration
                elif item.get("id") == "competitorLandscape":
                    if "result" in item:
                        result_data = item["result"]

                        # Ensure root-level score exists
                        if "score" not in result_data:
                            result_data["score"] = item.get("score", 0.0)

                        # Handle each provider
                        for provider in ["openai", "anthropic", "gemini", "perplexity"]:
                            if provider in result_data and isinstance(result_data[provider], dict):
                                provider_data = result_data[provider]

                                # Check if this is old flat structure
                                if "competitors" in provider_data and "score" in provider_data and "included" in provider_data:
                                    # This looks like old flat structure where provider had direct competitors/score/included
                                    # Need to migrate to new nested structure with models
                                    old_competitors = provider_data.get("competitors", [])
                                    old_score = provider_data.get("score", 0.0)
                                    old_included = provider_data.get("included", False)

                                    # Create new nested structure with dummy model data
                                    result_data[provider] = {
                                        "score": old_score,
                                        "competitors": [],  # Keep empty for backward compatibility
                                        "included": False   # Keep false for backward compatibility
                                    }
                                elif "score" not in provider_data:
                                    # Add missing score field
                                    provider_data["score"] = 0.0

                                # Ensure required fields exist
                                if "competitors" not in provider_data:
                                    provider_data["competitors"] = []
                                if "included" not in provider_data:
                                    provider_data["included"] = False
                    migrated_items.append(item)

                # Handle Strategy Review migration (most complex)
                elif item.get("id") == "strategyReview":
                    if "result" in item:
                        old_result = item["result"]

                        # Check if this is completely wrong data (like competitor data in strategy review)
                        if all(key in old_result for key in ["openai", "anthropic", "gemini", "perplexity"]) and all(
                            isinstance(old_result[key], dict) and "competitors" in old_result[key]
                            for key in ["openai", "anthropic", "gemini", "perplexity"]
                            if old_result[key] is not None
                        ):
                            # This looks like competitor data was stored in strategy review - create default structure
                            new_result = ReportService._create_default_strategy_result()
                        else:
                            new_result = {}

                            # Migrate knowledge_base to web_presence (camelCase for API)
                            if "knowledge_base" in old_result:
                                kb = old_result["knowledge_base"]
                                new_result["webPresence"] = {
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
                                new_result["webPresence"] = old_result["web_presence"]
                            elif "webPresence" in old_result:
                                new_result["webPresence"] = old_result["webPresence"]
                            else:
                                new_result["webPresence"] = ReportService._create_default_web_presence()

                            # Handle answerability
                            if "answerability" in old_result:
                                new_result["answerability"] = old_result["answerability"]
                            else:
                                new_result["answerability"] = ReportService._create_default_answerability()

                            # Handle structured_data -> structuredData
                            if "structured_data" in old_result:
                                structured_data = old_result["structured_data"].copy()
                                if "specific_schemas" in structured_data:
                                    old_specific = structured_data["specific_schemas"]
                                    new_specific = {
                                        "faq_page": old_specific.get("FAQPage", old_specific.get("faq_page", False)),
                                        "article": old_specific.get("Article", old_specific.get("article", False)),
                                        "review": old_specific.get("Review", old_specific.get("review", False))
                                    }
                                    structured_data["specific_schemas"] = new_specific
                                new_result["structuredData"] = structured_data
                            elif "structuredData" in old_result:
                                new_result["structuredData"] = old_result["structuredData"]
                            else:
                                new_result["structuredData"] = ReportService._create_default_structured_data()

                            # Handle ai_crawler_accessibility -> aiCrawlerAccessibility
                            if "ai_crawler_accessibility" in old_result:
                                new_result["aiCrawlerAccessibility"] = old_result["ai_crawler_accessibility"]
                            elif "aiCrawlerAccessibility" in old_result:
                                new_result["aiCrawlerAccessibility"] = old_result["aiCrawlerAccessibility"]
                            else:
                                new_result["aiCrawlerAccessibility"] = ReportService._create_default_ai_crawler_accessibility()

                        # Update the item with the new result structure
                        item["result"] = new_result
                    else:
                        # No result data - create completely default structure
                        item["result"] = ReportService._create_default_strategy_result()

                    migrated_items.append(item)
                else:
                    # For any other items, keep as-is
                    migrated_items.append(item)

            except Exception as e:
                # If migration fails for any item, create a safe default
                print(f"Migration failed for item {item.get('id', 'unknown')}: {str(e)}")

                if item.get("id") == "aiPresence":
                    item["result"] = {"score": item.get("score", 0.0)}
                elif item.get("id") == "competitorLandscape":
                    item["result"] = {
                        "score": item.get("score", 0.0),
                        "openai": {"score": 0.0, "competitors": [], "included": False},
                        "anthropic": {"score": 0.0, "competitors": [], "included": False},
                        "gemini": {"score": 0.0, "competitors": [], "included": False},
                        "perplexity": {"score": 0.0, "competitors": [], "included": False}
                    }
                elif item.get("id") == "strategyReview":
                    item["result"] = ReportService._create_default_strategy_result()

                migrated_items.append(item)

        # Update the result with migrated items
        result["analysis_items"] = migrated_items
        return result

    @staticmethod
    def _create_default_strategy_result() -> dict:
        """Create a default strategy review result structure."""
        return {
            "webPresence": ReportService._create_default_web_presence(),
            "answerability": ReportService._create_default_answerability(),
            "structuredData": ReportService._create_default_structured_data(),
            "aiCrawlerAccessibility": ReportService._create_default_ai_crawler_accessibility()
        }

    @staticmethod
    def _create_default_web_presence() -> dict:
        """Create a default web presence structure."""
        return {
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

    @staticmethod
    def _create_default_answerability() -> dict:
        """Create a default answerability structure."""
        return {
            "total_phrases": 0,
            "is_good_length_phrase": 0,
            "is_conversational_phrase": 0,
            "has_statistics_phrase": 0,
            "has_citation_phrase": 0,
            "has_citations_section": False,
            "score": 0.0
        }

    @staticmethod
    def _create_default_structured_data() -> dict:
        """Create a default structured data structure."""
        return {
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

    @staticmethod
    def _create_default_ai_crawler_accessibility() -> dict:
        """Create a default AI crawler accessibility structure."""
        return {
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