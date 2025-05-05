"""
Strategy Review Analyzer module.
This module contains functionality to analyze a company's strategic positioning.
"""

from typing import Dict, Any, Tuple, List
from bs4 import BeautifulSoup
import httpx
import json
import re
import asyncio
from app.services.analysis.base import BaseAnalyzer
from app.services.analysis.llm_utils import query_openai, query_anthropic, query_gemini
from app.core.config import settings
from app.services.analysis.scrape_utils import scrape_website

class StrategyReviewAnalyzer(BaseAnalyzer):
    """Analyzer for evaluating strategic positioning of a company."""
    
    async def analyze(self, url: str, soup: BeautifulSoup = None, all_text: str = None) -> Tuple[float, Dict[str, Any]]:
        """
        Analyze various aspects of a company's website.
        """
        # If soup or all_text is not provided, we need to scrape the website
        if soup is None or all_text is None:
            soup, all_text = await scrape_website(url)
        
        strategy_review_result = {}
        
        # 1. Content Answerability
        answerability_score, answerability_results = await self._analyze_content_answerability(all_text, soup)
        
        # 2. Knowedge Base presence 
            # Check if the company has a Wikipedia page through the wikipedia API
        # 3. Structured data Implementation
            # a. Is there and Which schema markup there is?
            # b. Mark FAQ, Articles, Review with schema
            # c. Have correct HTML semantic
        # 4. Accessibility to AI Crawlers
            # a. Is there a sitemap.xml?
            # b. Is there a robots.txt?
            # c. Is the content pre-rendered (LLM's don't index JS)
            # d. Is the content in english? If not, is there an english version of the website found?
        
        strategy_review_result["answerability"] = answerability_results    
        score = answerability_score
        
        return score, strategy_review_result
    
    async def _analyze_content_answerability(self, all_text: str, soup: BeautifulSoup = None) -> Tuple[float, Dict[str, Any]]:
        """
        Analyze the content answerability of a website.
        """
        results = {
            "total_phrases": 0,
            "is_good_length_phrase": 0,
            "is_conversational_phrase": 0,
            "has_statistics_phrase": 0,
            "has_citation_phrase": 0,
            "has_citations_section": False,
            "score": 0.0
        }
        
        # 1. Split content into phrases
        phrases = self._split_into_phrases(all_text)
        results["total_phrases"] = len(phrases)
        
        # 2. Analyze each phrase and directly update counters
        for phrase in phrases:
            self._analyze_and_count_phrase(phrase, results)
        
        # 3. Check if page has citations/references section
        if soup:
            results["has_citations_section"] = self._check_citations_section(soup)
        
        # Calculate the score
        score = self._calculate_answerability_score(results)
        results["score"] = score
        
        return score, results
    
    def _split_into_phrases(self, text: str) -> List[str]:
        punct_pattern = r'(?<=[.!?])\s+'
        
        # Split by punctuation
        phrases = re.split(punct_pattern, text)
        
        # Filter out empty phrases and normalize whitespace
        return [phrase.strip() for phrase in phrases if phrase.strip()]
    
    def _analyze_and_count_phrase(self, phrase: str, results: Dict[str, Any]) -> None:
        # Phrase length
        char_count = len(phrase)
        if 70 <= char_count <= 180:
            results["is_good_length_phrase"] += 1
            
        # Conversational language
        conversational_patterns = [
            r'\byes\b', r'\bno\b', 
            r'how do (i|you|we)', r'how can (i|you|we)', 
            r'what (is|are|should)', r'when (should|can|do)'
        ]
        if any(re.search(pattern, phrase.lower()) for pattern in conversational_patterns):
            results["is_conversational_phrase"] += 1
        
        # Check for statistics
        statistic_patterns = [
            r'\d+%', r'\d+ percent', r'£\d+', r'\$\d+', r'€\d+', r'¥\d+',
            r'\d+ million', r'\d+ billion', r'\d+ thousand',
            r'quarter', r'half', r'third'
        ]
        if any(re.search(pattern, phrase.lower()) for pattern in statistic_patterns):
            results["has_statistics_phrase"] += 1
        
        # Check for citations or quotes
        citation_patterns = [r'[\'"][^\'"]+[\'"]', r'\[[0-9]+\]', r'\([^)]*\d{4}[^)]*\)']
        if any(re.search(pattern, phrase) for pattern in citation_patterns):
            results["has_citation_phrase"] += 1

    def _check_citations_section(self, soup: BeautifulSoup) -> bool:
        citation_terms = ['citations', 'references', 'sources', 'bibliography', 'reference list', 'citation list', 'bibliography list']
        
        # Check headings
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            if heading.text and any(term in heading.text.lower() for term in citation_terms):
                return True
        
        # Check div/section IDs and classes
        for element in soup.find_all(['div', 'section']):
            element_id = element.get('id', '').lower()
            element_class = ' '.join(element.get('class', [])).lower()
            
            if any(term in element_id for term in citation_terms) or any(term in element_class for term in citation_terms):
                return True
        
        return False
    
    def _calculate_answerability_score(self, results: Dict[str, Any]) -> float:
        total_phrases = results["total_phrases"]
        if total_phrases == 0:
            return 0.0
        
        # Calculate length score - percentage of phrases with good length
        length_percentage = (results["is_good_length_phrase"] / total_phrases) * 100
        length_score = length_percentage * 0.3  # 30% weight
        
        # Calculate conversational score - target is at least 30% of phrases
        conversational_percentage = (results["is_conversational_phrase"] / total_phrases) * 100
        # If at least 30% are conversational, give full points, otherwise pro-rate
        conversational_score = min(30.0, (conversational_percentage / 30.0) * 30.0)
        
        # Calculate statistical score - target is at least 5% of phrases
        statistical_percentage = (results["has_statistics_phrase"] / total_phrases) * 100
        # If at least 5% have statistics, give full points, otherwise pro-rate
        statistical_score = min(20.0, (statistical_percentage / 5.0) * 20.0)
        
        # Calculate citation score - target is at least 15% of phrases
        citation_percentage = (results["has_citation_phrase"] / total_phrases) * 100
        # If at least 15% have citations, give full points, otherwise pro-rate
        citation_score = min(10.0, (citation_percentage / 15.0) * 10.0)
        
        # Add bonus for having a citations section
        citations_section_bonus = 10.0 if results["has_citations_section"] else 0.0
        
        # Calculate final score (normalized to 0-100)
        raw_score = length_score + conversational_score + statistical_score + citation_score + citations_section_bonus
        final_score = min(100.0, raw_score)
        
        return final_score