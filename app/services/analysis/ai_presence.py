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
          f"In 3-4 sentences, tell me about the company {company_facts['name']}. "
          f"Mention its industry, flagship product/service, headquarters city, and founding year if known."
        )
        
        responses = {}
        tasks = []
        
        # if settings.OPENAI_API_KEY:
        #   tasks.append(query_openai(prompt))
        # else:
        #   responses["openai"] = "API key not configured"
            
        # if settings.ANTHROPIC_API_KEY:
        #   tasks.append(query_anthropic(prompt))
        # else:
        #   responses["anthropic"] = "API key not configured"
            
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
        # Awareness
        if company_facts['name']:
            if company_facts['name'] in response:
                score += 10
                details['name'] = True
            else:
                details['name'] = False
        else:
            details['name'] = False

        if company_facts['key_products_services']:
            if any(prod and prod in response for prod in company_facts['key_products_services']):
                score += 10
                details['product'] = True
            else:
                details['product'] = False
        else:
            details['product'] = False

        if company_facts['hq']:
            if company_facts['hq'] in response:
                score += 3
                details['hq'] = True
            else:
                details['hq'] = False
        else:
            details['hq'] = False

        if company_facts['founded']:
            if company_facts['founded'] in response:
                score += 3
                details['founded'] = True
            else:
                details['founded'] = False
        else:
            details['founded'] = False

        if company_facts['industry']:
            if company_facts['industry'] in response:
                score += 3
                details['industry'] = True
            else:
                details['industry'] = False
        else:
            details['industry'] = False

        # Check for uncertainty phrases
        if any(x in response.lower() for x in ["i don't know", "I cannot confidently", "I apologize", "I don't have", "I cannot find", "I cannot tell", "I cannot find", "I cannot tell", "i can't tell", "i can't find"]):
            score -= 2
            details['uncertainty'] = True
        else:
            details['uncertainty'] = False
        return score, details

    async def analyze(self, company_facts: dict) -> Tuple[float, str, dict]:
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
        summary_parts = ["AI Presence Analysis:"]
        if 'openai' in scores:
            summary_parts.append(f"OpenAI: {scores['openai']}")
        if 'anthropic' in scores:
            summary_parts.append(f"Anthropic: {scores['anthropic']}")
        if 'gemini' in scores:
            summary_parts.append(f"Gemini: {scores['gemini']}")
        summary_parts.append(f"Average: {avg_score:.2f}")
        analysis_result = ", ".join(summary_parts)
        return avg_score, analysis_result, details