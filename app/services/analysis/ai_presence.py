"""
AI Presence Analyzer module.
This module contains functionality to check how well large language models know about a company.
"""

import httpx
from bs4 import BeautifulSoup
import json
from typing import Tuple
import asyncio
import re
from urllib.parse import urljoin, urlparse

from app.services.analysis.base import BaseAnalyzer
from app.core.config import settings
from app.services.analysis.utils.llm_utils import query_openai, query_anthropic, query_gemini

class AiPresenceAnalyzer(BaseAnalyzer):
    """Analyzer for checking AI presence of a company (how well AI models know about it)."""
    
    @staticmethod
    async def _query_llms(company_facts: dict) -> dict:
        prompt = (
            f"Do not invent information. IF YOU HAVE NO KNOWLEDGE of this company, ONLY RESPOND WITH 'I Don't Know'."
            f"Please provide a brief 3-4 sentence summary of the company '{company_facts['name']}'. "
            f"Include its industry and primary product/service"
            f"Accuracy is crucial. If you lack specific information or are uncertain about any detail, **explicitly state \\'I don\\'t know\\' for that specific piece of information** rather than guessing or providing potentially inaccurate details. "
            f"Do not invent information. IF YOU HAVE NO KNOWLEDGE of this company, ONLY RESPOND WITH 'I Don't Know'."
        )
        
        responses = {}
        tasks = []
        
        if settings.OPENAI_API_KEY:
          tasks.append(query_openai(prompt))
        else:
          responses["openai"] = "API key not configured"
            
        if settings.ANTHROPIC_API_KEY:
          tasks.append(query_anthropic(prompt))
        else:
          responses["anthropic"] = "API key not configured"
            
        if settings.GEMINI_API_KEY:
          tasks.append(query_gemini(prompt))
        else:
          responses["gemini"] = "API key not configured"
        
        if tasks:
          results = await asyncio.gather(*tasks, return_exceptions=True)
          
          for i, result in enumerate(results):
            if isinstance(result, Exception):
              if i == 0 and "openai" not in responses:
                responses["openai"] = f"Error: {str(result)}"
              elif i == 1 and "anthropic" not in responses:
                responses["anthropic"] = f"Error: {str(result)}"
              elif i == 2 and "gemini" not in responses:
                responses["gemini"] = f"Error: {str(result)}"
            else:
              model_name, response_text = result
              responses[model_name] = response_text
        
        return responses
    
    @staticmethod
    def _score_llm_response(company_facts: dict, response: str) -> Tuple[float, dict]:
        score = 0
        details = {}
        response_lower = response.lower()

        if company_facts['name'] and company_facts['name'].lower() in response_lower:
            score += 25
            details['name'] = True
        else:
            details['name'] = False

        if any(prod and prod.lower() in response_lower for prod in company_facts['key_products_services']):
            score += 25
            details['product'] = True
        else:
            details['product'] = False

        industry_keywords = ["industry"]
        industry_found = (company_facts['industry'] and company_facts['industry'].lower() in response_lower) or \
                            any(keyword in response_lower for keyword in industry_keywords)
        if industry_found:
            score += 25
            details['industry'] = True
        else:
            details['industry'] = False

        if any(x in response_lower for x in ["don't know", "unable to", "unknown", "cannot confidently", "i apologize", "i don't have", "cannot find", "cannot tell", "can't tell", "can't find"]):
            if score > 0:
              score -= 2
            details['uncertainty'] = True
        else:
            details['uncertainty'] = False
        return score, details

    async def analyze(self, company_facts: dict) -> Tuple[float, dict]:
        """
        Analyze AI presence of a company website.
        """
        # 1. Query LLMs
        llm_responses = await self._query_llms(company_facts)
        # 2. Score each response
        scores = {}
        details = {}
        for model, response in llm_responses.items():
            score, detail = self._score_llm_response(company_facts, response)
            scores[model] = score
            details[model] = detail
        # 3. Aggregate
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        
        # Create object-based result structure
        analysis_result = {}
        
        for model in scores.keys():
            # For each model, add its details and score
            if model not in analysis_result:
                analysis_result[model] = {}
            
            analysis_result[model].update(details[model])
            analysis_result[model]['score'] = scores[model]
        
        return avg_score, analysis_result