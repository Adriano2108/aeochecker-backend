"""Analysis utility functions."""

def generate_analysis_synthesis(company_name: str, score: float) -> str:
    """
    Generate an analysis synthesis based on the company's overall score.
    
    Args:
        company_name: The name of the company being analyzed
        score: The overall score from 0-100
        
    Returns:
        A synthesis statement customized to the score range
    """
    # Define score ranges and corresponding synthesis messages
    if score < 10:
        return f"{company_name}'s AEO report obtained a critically low score of {score:.1f}. Immediate action is needed as your brand is likely invisible to AI chatbots. Following our detailed recommendations is essential to establish any presence."
    
    elif score < 20:
        return f"{company_name}'s AEO report obtained a very low score of {score:.1f}. Your brand has minimal to no visibility to AI systems. Significant improvements are needed across all areas for AI chatbots to recognize and mention your company."
    
    elif score < 30:
        return f"{company_name}'s AEO report obtained a low score of {score:.1f}. There are many aspects missing that need to be reviewed if you want AI chatbots to mention your brand and its products. Focus on implementing our key recommendations."
    
    elif score < 40:
        return f"{company_name}'s AEO report obtained a below average score of {score:.1f}. While some elements are in place, your brand still lacks sufficient visibility to AI systems. Addressing our recommendations will help improve your AI visibility."
    
    elif score < 50:
        return f"{company_name}'s AEO report obtained a moderate score of {score:.1f}. Your brand has basic visibility to AI chatbots, but considerable improvements can be made to increase mentions and accuracy of information."
    
    elif score < 60:
        return f"{company_name}'s AEO report obtained a fair score of {score:.1f}. Your company has established a foundation for AI visibility. Implementing our suggested optimizations will significantly enhance your presence in AI responses."
    
    elif score < 70:
        return f"{company_name}'s AEO report obtained a good score of {score:.1f}. Your brand is being mentioned by AI chatbots, though there's still room for improvement. Follow our recommendations to enhance the frequency and context of mentions."
    
    elif score < 80:
        return f"{company_name}'s AEO report obtained a very good score of {score:.1f}. Your company has implemented many effective strategies and is regularly mentioned by AI systems. Our suggestions will help you refine your approach further."
    
    elif score < 90:
        return f"{company_name}'s AEO report obtained an excellent score of {score:.1f}. This shows that most strategies are correctly implemented and your company is frequently mentioned in AI chatbots. Follow our suggestions to maximize your AI visibility."
    
    else:
        return f"Exceptional! {company_name}'s AEO report obtained an outstanding score of {score:.1f}. Your company has mastered AI visibility strategies and is prominently featured in AI responses. Our minor suggestions will help maintain this exceptional performance." 

def generate_dummy_report(original_report: dict) -> dict:
    """
    Generate a dummy report by preserving only essential fields from the original report.
    
    Args:
        original_report: The complete report dictionary
        
    Returns:
        A sanitized report with dummy values for sensitive content
    """
    # Fields to preserve from the original report
    preserved_fields = ["url", "score", "title", "analysis_synthesis", "created_at", "job_id", "deleted"]
    
    # Create a new report with preserved fields
    dummy_report = {field: original_report.get(field) for field in preserved_fields if field in original_report}
    
    # Add dummy flag
    dummy_report["dummy"] = True
    
    # Ensure deleted field exists with default value
    if "deleted" not in dummy_report:
        dummy_report["deleted"] = False
    
    # Replace analysis_items with dummy entries
    dummy_report["analysis_items"] = [
        {
            "id": "ai_presence",
            "title": "AI Presence",
            "score": 0.0,
            "completed": True,
            "result": {
                "openai": {
                    "name": False,
                    "product": False,
                    "industry": False,
                    "uncertainty": False,
                    "score": 0
                },
                "anthropic": {
                    "name": False,
                    "product": False,
                    "industry": False,
                    "uncertainty": False,
                    "score": 0
                },
                "gemini": {
                    "name": False,
                    "product": False,
                    "industry": False,
                    "uncertainty": False,
                    "score": 0
                },
                "score": 0
            },
        },
        {
            "id": "competitor_landscape",
            "title": "Competitor Landscape",
            "score": 0.0,
            "completed": True,
            "result": {
                "included": False,
                "sorted_competitors": [
                    {
                        "name": "Company 1",
                        "count": 2
                    },
                    {
                        "name": "Company 2",
                        "count": 1
                    },
                    {
                        "name": "Company 3",
                        "count": 1
                    }
                ],
            },
        },
        {
            "id": "strategy_review",
            "title": "Strategy Review",
            "score": 0.0,
            "completed": True,
            "result": {
                "answerability": {
                    "total_phrases": 0,
                    "is_good_length_phrase": 0,
                    "is_conversational_phrase": 0,
                    "has_statistics_phrase": 0,
                    "has_citation_phrase": 0,
                    "has_citations_section": False,
                    "score": 0
                },
                "knowledge_base": {
                    "has_wikipedia_page": False,
                    "wikipedia_url": None,
                    "score": 0
                },
                "structured_data": {
                    "schema_markup_present": False,
                    "schema_types_found": [],
                    "specific_schemas": {
                        "FAQPage": False,
                        "Article": False,
                        "Review": False
                    },
                    "semantic_elements": {
                        "present": False,
                        "unique_types_found": [],
                        "count_unique_types": 0,
                        "all_tags_count": 0,
                        "semantic_tags_count": 0,
                        "non_semantic_tags_count": 0,
                        "semantic_ratio": 0
                    },
                    "score": 0
                },
                "ai_crawler_accessibility": {
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
                        "detected_languages": ['en'],
                        "is_english": False,
                        "english_version_url": None,
                        "score": 0
                    },
                    "score": 0
                },
            },
        }
    ]
    
    return dummy_report  