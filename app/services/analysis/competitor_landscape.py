"""
Competitor Landscape Analyzer module.
This module contains functionality to analyze the competitive landscape for a company.
"""

from app.services.analysis.base import BaseAnalyzer
from app.core.config import settings
import asyncio
import ast
from app.services.analysis.utils.llm_utils import query_openai, query_anthropic, query_gemini, query_perplexity
from collections import Counter
import re
from app.schemas.analysis import CompetitorLandscapeResult, LLMCompetitorResult
import json

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
                f"List the top 5 companies in the {industry} industry for {products_string}. "
                "Return only a Python array of company names, e.g., ['Company1', 'Company2', 'Company3', 'Company4', 'Company5']. Only return the list, no other text. Do not provide any reasononing for your choices, do not provide any thought process, ONLY provide the array"
            )
        elif industry and not products_string: 
            prompt = (
                f"List the top 5 companies in the {industry} industry. "
                "Return only a Python array of company names, e.g., ['Company1', 'Company2', 'Company3', 'Company4', 'Company5']. Only return the list, no other text. Do not provide any reasononing for your choices, do not provide any thought process, ONLY provide the array"
            )
        elif not industry and products_string: 
            prompt = (
                f"List the top 5 companies in the {products_string} product. "
                "Return only a Python array of company names, e.g., ['Company1', 'Company2', 'Company3', 'Company4', 'Company5']. Only return the list, no other text. Do not provide any reasononing for your choices, do not provide any thought process, ONLY provide the array"
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
        if settings.PERPLEXITY_API_KEY:
            tasks.append(query_perplexity(prompt))
        else:
            print("Perplexity API key not configured")
            responses["perplexity"] = "API key not configured"
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
                    elif i == 3 and "perplexity" not in responses:
                        responses["perplexity"] = f"Error: {str(result)}"
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
                    # Post-process to handle malformed entries even in clean lists
                    cleaned_competitors = []
                    for comp in competitors:
                        if isinstance(comp, str):
                            # Check if this entry contains multiple companies separated by quotes
                            if "', '" in comp or '", "' in comp:
                                # Split on quote-comma-quote patterns and clean each part
                                parts = re.split(r"['\"]\s*,\s*['\"]", comp)
                                for part in parts:
                                    clean_part = part.strip().strip('\'"')
                                    if clean_part:
                                        cleaned_competitors.append(clean_part)
                            else:
                                cleaned_competitors.append(comp.strip())
                    return cleaned_competitors
            except (SyntaxError, ValueError):
                pass
            
            # Look for backtick-enclosed lists first (common in Gemini markdown outputs)
            backtick_pattern = r'```(?:python)?\s*(\[.*?\])\s*```'
            matches = re.search(backtick_pattern, response, re.DOTALL)
            if matches:
                try:
                    # Extract the complete list structure and parse it directly
                    list_text = matches.group(1).strip()
                    competitors = ast.literal_eval(list_text)
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
                        # Post-process to handle malformed entries
                        cleaned_competitors = []
                        for comp in competitors:
                            if isinstance(comp, str):
                                # If a competitor contains quotes and commas, try to split it
                                if "', '" in comp or '", "' in comp:
                                    # Split on quote-comma-quote patterns
                                    split_comps = re.split(r"['\"],\s*['\"]", comp)
                                    for split_comp in split_comps:
                                        # Clean up any remaining quotes
                                        clean_comp = split_comp.strip().strip('\'"')
                                        if clean_comp:
                                            cleaned_competitors.append(clean_comp)
                                else:
                                    cleaned_competitors.append(comp.strip())
                        return cleaned_competitors
                except (SyntaxError, ValueError):
                    pass
                    
            # If all else fails, try to extract company names from comma-separated text
            # Look for patterns like: Company1, Company2, Company3
            comma_pattern = r'([A-Z][^,]+(?:\([^)]+\))?)'
            matches = re.findall(comma_pattern, response)
            if matches and len(matches) >= 3:
                return [match.strip() for match in matches[:5]]  # Limit to top 5
                
        except Exception as e:
            print(f"Error parsing competitor response: {str(e)}")
        
        return []

    def _normalize_company_name(self, name: str) -> str:
        """
        Normalize company name for comparison by:
        - Converting to lowercase
        - Removing spaces, dashes, periods, and special characters
        - Removing common suffixes like Inc, Corp, Group, etc.
        """
        if not name:
            return ""
            
        # Convert to lowercase
        normalized = name.lower()
        
        # Remove common domain extensions
        normalized = re.sub(r'\.com$|\.org$|\.net$|\.co$', '', normalized)
        
        # Remove common business suffixes (must be at the end of the name)
        suffixes = [
            r'\s+inc\.?$', r'\s+corp\.?$', r'\s+corporation$', r'\s+company$',
            r'\s+group$', r'\s+holding$', r'\s+holdings$', r'\s+ltd\.?$',
            r'\s+limited$', r'\s+llc$', r'\s+co\.?$', r'\s+&\s+co\.?$', r'\s+original$', r'\s+originals$'
        ]
        for suffix in suffixes:
            normalized = re.sub(suffix, '', normalized)
        
        # Remove all spaces, dashes, periods, and special characters
        normalized = re.sub(r'[\s\-\.\,\'\"\(\)\&]', '', normalized)
        
        return normalized.strip()

    def _should_group_companies(self, name1: str, name2: str) -> bool:
        """
        Determine if two company names should be grouped together.
        Uses normalized names and checks if one is a substring of the other.
        """
        norm1 = self._normalize_company_name(name1)
        norm2 = self._normalize_company_name(name2)
        
        if not norm1 or not norm2:
            return False
            
        # Exact match after normalization
        if norm1 == norm2:
            return True
            
        # Check if one is a substring of the other (minimum 3 characters to avoid issues)
        if len(norm1) >= 3 and len(norm2) >= 3:
            if norm1 in norm2 or norm2 in norm1:
                return True
        
        return False

    def _count_and_rank_competitors(self, competitors_lists: list) -> list:
        """Count and rank competitors based on frequency of mentions, grouping similar names."""
        # First pass: collect all competitors and group similar ones
        competitor_groups = []  # List of lists, each sublist contains similar company names
        all_competitors = []
        
        # Flatten all competitor lists
        for lst in competitors_lists:
            all_competitors.extend(lst)
        
        # Group similar competitors
        for comp in all_competitors:
            comp = comp.strip()
            if not comp:
                continue
                
            # Find if this competitor should be grouped with an existing group
            grouped = False
            for group in competitor_groups:
                # Check if current competitor should be grouped with any competitor in this group
                if any(self._should_group_companies(comp, existing_comp) for existing_comp in group):
                    group.append(comp)
                    grouped = True
                    break
            
            # If not grouped, create a new group
            if not grouped:
                competitor_groups.append([comp])
        
        # Second pass: count occurrences and select representative name for each group
        group_counts = []
        for group in competitor_groups:
            count = len(group)
            
            # Select the most common original name in the group, or shortest if tied
            name_counter = Counter(group)
            most_common_names = name_counter.most_common()
            
            # If there's a tie in frequency, prefer the shortest name
            max_count = most_common_names[0][1]
            candidates = [name for name, freq in most_common_names if freq == max_count]
            representative_name = min(candidates, key=len)  # Shortest name among most frequent
            
            group_counts.append((representative_name, count))
        
        # Sort by count (descending)
        ranked_competitors = sorted(group_counts, key=lambda x: x[1], reverse=True)
        
        return ranked_competitors

    def _calculate_score(self, competitors_list: list, company_name: str) -> tuple:
        """Calculate score based on company's position in the competitor list."""
        score = 0
        included = False
        normalized_company_name = company_name.lower()

        # Find the company in the list and get its position
        for position, competitor in enumerate(competitors_list):
            if competitor.lower() == normalized_company_name or normalized_company_name in competitor.lower():
                included = True
                # Position-based scoring (0-indexed, so add 1 for actual position)
                actual_position = position + 1
                if actual_position == 1:
                    score = 25
                elif actual_position == 2:
                    score = 20
                elif actual_position == 3:
                    score = 15
                elif actual_position == 4:
                    score = 10
                elif actual_position == 5:
                    score = 5
                else:
                    score = 2  # Some points for being mentioned even if not in top 5
                break
        
        return score, included

    def _analyze_single_llm_response(self, response: str, company_facts: dict) -> tuple:
        """
        Analyze a single LLM response for competitors.
        Returns (score, LLMCompetitorResult) tuple.
        """
        # 1. Extract competitors from this response
        parsed_competitors = self._parse_competitor_list(response)
        
        if not parsed_competitors:
            # If no competitors found, return empty result
            return 0, LLMCompetitorResult(competitors=[], included=False, score=0)
        
        # 2. Calculate score based on position (no need to count/rank since we preserve order)
        company_name = company_facts.get("name", "")
        score, included = self._calculate_score(parsed_competitors, company_name)

        # Keep the original order from LLM
        llm_result = LLMCompetitorResult(
            competitors=parsed_competitors,
            included=included,
            score=score
        )

        return score, llm_result

    async def analyze(self, company_facts: dict) -> tuple:
        """
        Analyze the competitive landscape for a company website.
        Now processes each LLM response individually.
        """
        # 1. Query LLMs for competitors
        llm_responses = await self._query_llms_competitors(company_facts)

        print(json.dumps(llm_responses, indent=4))

        # 2. Process each LLM response individually
        competitor_results = {}
        total_score = 0
        valid_responses = 0

        for model_name, response in llm_responses.items():
            if isinstance(response, str) and not response.startswith("Error:") and not response.startswith("API key not configured"):
                score, llm_result = self._analyze_single_llm_response(response, company_facts)
                competitor_results[model_name] = llm_result
                total_score += score  # Sum the scores instead of averaging
                valid_responses += 1
            else:
                # For errors or missing API keys, set to None
                competitor_results[model_name] = None

        # Use total score (sum) instead of average
        final_score = total_score

        # Create final result with individual LLM results
        final_result = CompetitorLandscapeResult(
            openai=competitor_results.get("openai"),
            anthropic=competitor_results.get("anthropic"),
            gemini=competitor_results.get("gemini"),
            perplexity=competitor_results.get("perplexity")
        )

        return final_score, final_result