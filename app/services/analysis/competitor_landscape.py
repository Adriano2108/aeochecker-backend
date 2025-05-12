"""
Competitor Landscape Analyzer module.
This module contains functionality to analyze the competitive landscape for a company.
"""

from app.services.analysis.base import BaseAnalyzer
from app.core.config import settings
import asyncio
import ast
from app.services.analysis.utils.llm_utils import query_openai, query_anthropic, query_gemini
from collections import Counter
import re
from app.schemas.analysis import CompetitorLandscapeAnalysisResult, CompetitorEntry

class CompetitorLandscapeAnalyzer(BaseAnalyzer):
    """Analyzer for evaluating competitive landscape of a company."""
    
    @staticmethod
    async def _query_llms_competitors(company_facts: dict) -> dict:
        """
        Query multiple LLMs for the top 3 competitors in the given industry/product.
        Returns a dict of model_name -> list of competitors (or error string).
        """
        industry = company_facts.get("industry", "") or ""
        products = company_facts.get("key_products_services", [])
        products_string = ", ".join(products)

        responses = {}

        if industry and products_string:
            prompt = (
                f"List the top 3 companies in the {industry} industry for {products_string}. "
                "Return only a Python list of company names, e.g., ['Company1', 'Company2', 'Company3']. Only return the list, no other text."
            )
        elif industry and not products_string: 
            prompt = (
                f"List the top 3 companies in the {industry} industry. "
                "Return only a Python list of company names, e.g., ['Company1', 'Company2', 'Company3']. Only return the list, no other text."
            )
        elif not industry and products_string: 
            prompt = (
                f"List the top 3 companies in the {products_string} product. "
                "Return only a Python list of company names, e.g., ['Company1', 'Company2', 'Company3']. Only return the list, no other text."
            )
        else: 
            print("No industry or product found/provided, skipping competitor analysis")
            return {}

        tasks = []
        if settings.OPENAI_API_KEY:
            tasks.append(query_openai(prompt))
        else:
            print("OpenAI API key not configured")
            responses["openai"] = "API key not configured"
        if settings.ANTHROPIC_API_KEY:
            tasks.append(query_anthropic(prompt))
        else:
            print("Anthropic API key not configured")
            responses["anthropic"] = "API key not configured"
        if settings.GEMINI_API_KEY:
            tasks.append(query_gemini(prompt))
        else:
            print("Gemini API key not configured")
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
    def _parse_competitor_list(response: str) -> list:
        """Parse various formats of competitor lists from LLM responses."""
        try:
            # First try literal_eval (for clean Python lists)
            try:
                competitors = ast.literal_eval(response.strip())
                if isinstance(competitors, list):
                    return [comp.strip() for comp in competitors if isinstance(comp, str)]
            except (SyntaxError, ValueError):
                pass
            
            # Then try to find any list-like structure with regex
            list_pattern = r'\[[\'\"](.+?)[\'\"],\s*[\'\"](.+?)[\'\"],\s*[\'\"](.+?)[\'\"]\]'
            matches = re.search(list_pattern, response)
            if matches:
                competitors = [matches.group(1), matches.group(2), matches.group(3)]
                return [comp.strip() for comp in competitors]
            
            # Try a simpler approach to find list-like structures
            simple_list_pattern = r'\[([\'\"].*?[\'\"](?:,\s*[\'\"].*?[\'\"])*)\]'
            matches = re.search(simple_list_pattern, response, re.DOTALL)
            if matches:
                try:
                    items_text = '[' + matches.group(1) + ']'
                    competitors = ast.literal_eval(items_text)
                    if isinstance(competitors, list):
                        return [comp.strip() for comp in competitors if isinstance(comp, str)]
                except (SyntaxError, ValueError):
                    pass
            
            # Finally look for backtick-enclosed lists (common in markdown outputs)
            backtick_pattern = r'```(?:python)?\s*\[(.*?)\]\s*```'
            matches = re.search(backtick_pattern, response, re.DOTALL)
            if matches:
                try:
                    items_text = '[' + matches.group(1) + ']'
                    competitors = ast.literal_eval(items_text)
                    if isinstance(competitors, list):
                        return [comp.strip() for comp in competitors if isinstance(comp, str)]
                except (SyntaxError, ValueError):
                    pass
        except Exception as e:
            print(f"Error parsing competitor response: {str(e)}")
        
        return []

    def _extract_all_competitors(self, llm_responses: dict) -> list:
        """Extract and parse all competitor lists from LLM responses."""
        competitors_lists = []
        for model, response in llm_responses.items():
            parsed_list = self._parse_competitor_list(response)
            if parsed_list:
                competitors_lists.append(parsed_list)
        return competitors_lists

    def _count_and_rank_competitors(self, competitors_lists: list) -> list:
        """Count and rank competitors based on frequency of mentions."""
        competitor_counter = Counter()
        for lst in competitors_lists:
            for comp in lst:
                competitor_counter[comp] += 1
                
        # Get sorted competitors by count
        return competitor_counter.most_common()

    def _calculate_score(self, competitor_counter: Counter, company_name: str) -> tuple:
        """Calculate score based on whether company is included in competitor lists."""
        included = company_name in competitor_counter.keys()
        score = 10 if included else 0
        return score, included

    async def analyze(self, company_facts: dict) -> tuple:
        """
        Analyze the competitive landscape for a company website.
        """
        # 1. Query LLMs for competitors
        llm_responses = await self._query_llms_competitors(company_facts)

        print(f"LLM responses: {llm_responses}")
        
        # 2. Extract competitor lists from responses
        competitors_lists = self._extract_all_competitors(llm_responses)
        
        # 3. Count and rank competitors
        sorted_competitors_tuples = self._count_and_rank_competitors(competitors_lists)
        
        # 4. Calculate score
        company_name = company_facts.get("name", "")
        competitor_counter = Counter(dict(sorted_competitors_tuples))
        score, included = self._calculate_score(competitor_counter, company_name)

        # Convert list of tuples to list of CompetitorEntry objects
        sorted_competitors_objects = [CompetitorEntry(name=name, count=count) for name, count in sorted_competitors_tuples]

        competitors_result = CompetitorLandscapeAnalysisResult(
            sorted_competitors=sorted_competitors_objects,
            included=included
        )

        # Return top competitors as tuples of (name, count)
        return score, competitors_result