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

    def _calculate_score(self, competitor_counter: Counter, company_name: str) -> tuple:
        """Calculate score based on whether company is included in competitor lists."""
        score = 0
        included = False
        normalized_company_name = company_name.lower()

        # Find the company in the counter, considering case-insensitivity for keys
        company_count = 0
        found_company_key = None
        for key, count in competitor_counter.items():
            if key.lower() == normalized_company_name:
                company_count = count
                found_company_key = key # Keep the original casing for potential use
                included = True
                break
        
        if not included:
            return 0, False

        score += 50

        # Ranking score
        if found_company_key:
            unique_sorted_counts = sorted(list(set(competitor_counter.values())), reverse=True)
            try:
                rank = unique_sorted_counts.index(company_count) + 1
            except ValueError:
                rank = float('inf') 
            if rank == 1:
                score += 50
            elif rank == 2:
                score += 40
            elif rank == 3:
                score += 30
            elif rank == 4:
                score += 20
            elif rank == 5:
                score += 10

        print(f"Score: {score}")
            
        return score, included

    async def analyze(self, company_facts: dict) -> tuple:
        """
        Analyze the competitive landscape for a company website.
        """
        # 1. Query LLMs for competitors
        llm_responses = await self._query_llms_competitors(company_facts)

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