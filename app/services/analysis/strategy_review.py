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
from urllib.parse import urlparse, urlunparse, urljoin
from app.services.analysis.base import BaseAnalyzer
from langdetect import detect, LangDetectException
from app.services.analysis.scrape_utils import ( check_robots_txt, get_potential_sitemap_urls, is_valid_sitemap )

class StrategyReviewAnalyzer(BaseAnalyzer):
    """Analyzer for evaluating strategic positioning of a company."""
    
    async def analyze(self, name: str, url: str, soup: BeautifulSoup = None, all_text: str = None) -> Tuple[float, Dict[str, Any]]:
        """
        Analyze various aspects of a company's website.
        
        Args:
            name: The name of the company
            url: The URL of the company's website
            soup: The BeautifulSoup object of the website (optional)
            all_text: The extracted text content from the website (optional)
            
        Returns:
            Tuple containing:
            - score: A float score representing the overall strategic positioning
            - results: A dictionary with detailed results of the analysis
        """
        strategy_review_result = {}
        
        # 1. Content Answerability
        answerability_score, answerability_results = await self._analyze_content_answerability(all_text, soup)
        
        # 2. Knowledge Base Presence 
        kb_score, kb_results = await self._analyze_knowledge_base_presence(name)
        
        # 3. Structured Data Implementation
        structured_data_score, structured_data_results = self._analyze_structured_data(soup)
        
        # 4. Accessibility to AI Crawlers
        accessibility_score, accessibility_results = await self._analyze_crawler_accessibility(url, soup)
        
        strategy_review_result["answerability"] = answerability_results
        strategy_review_result["knowledge_base"] = kb_results
        strategy_review_result["structured_data"] = structured_data_results
        strategy_review_result["ai_crawler_accessibility"] = accessibility_results
        
        # Calculate the overall score as the average of all component scores
        score = (answerability_score + kb_score + structured_data_score + accessibility_score) / 4
        
        return score, strategy_review_result
    
    def _calculate_structured_data_score(self, results: Dict[str, Any]) -> float:
        """Calculate a score for structured data implementation quality."""
        score = 0.0
        
        # 1. Schema markup presence (30 points max)
        if results["schema_markup_present"]:
            score += 15.0  # Basic presence
            
            # Additional points for variety of schemas
            schema_count = len(results["schema_types_found"])
            if schema_count >= 3:
                score += 15.0
            else:
                score += schema_count * 5.0
                
        # 2. Specific important schemas (30 points max)
        specific_schemas = results["specific_schemas"]
        if specific_schemas["FAQPage"]:
            score += 10.0
        if specific_schemas["Article"]:
            score += 10.0
        if specific_schemas["Review"]:
            score += 10.0
            
        # 3. Semantic HTML elements (40 points max)
        semantic_elements = results["semantic_elements"]
        if semantic_elements["present"]:
            # Points for variety of semantic elements
            unique_types_count = semantic_elements["count_unique_types"]
            if unique_types_count >= 10:
                score += 20.0
            else:
                score += unique_types_count * 2.0
                
            # Points for semantic ratio
            ratio = semantic_elements["semantic_ratio"]
            if ratio >= 0.6:  # 60% or more semantic tags
                score += 20.0
            elif ratio >= 0.4:  # 40-60% semantic tags
                score += 15.0
            elif ratio >= 0.2:  # 20-40% semantic tags
                score += 10.0
            else:
                score += 5.0
                
        return min(100.0, score)
    
    def _analyze_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Analyzes a BeautifulSoup object for structured data implementation and
        HTML semantics.

        Args:
            soup: A BeautifulSoup object representing the parsed HTML page.

        Returns:
            A dictionary containing the analysis results:
            {
                "schema_markup_present": bool,
                "schema_types_found": list[str],
                "specific_schemas": {
                    "FAQPage": bool,
                    "Article": bool, # Includes subtypes like NewsArticle, BlogPosting
                    "Review": bool   # Includes subtypes like AggregateRating
                },
                "semantic_elements": {
                    "present": bool,
                    "unique_types_found": list[str],
                    "count_unique_types": int,
                    "all_tags_count": int,
                    "semantic_tags_count": int,
                    "non_semantic_tags_count": int, # Primarily divs and spans
                    "semantic_ratio": float # Ratio of semantic tags to total tags
                }
            }
        """
        results = {
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
                "semantic_ratio": 0.0
            }
        }
        schema_types_set = set()

        # 1. Check for JSON-LD (<script type="application/ld+json">) - Most common
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                # Ignore empty scripts
                if script.string:
                    data = json.loads(script.string)
                    results["schema_markup_present"] = True

                    # Data can be a single dictionary or a list of dictionaries
                    items_to_check = []
                    if isinstance(data, dict):
                        items_to_check.append(data)
                    elif isinstance(data, list):
                        items_to_check.extend(data)

                    for item in items_to_check:
                        # Check if it's a dictionary and has a '@type'
                        if isinstance(item, dict) and '@type' in item:
                            schema_type = item['@type']
                            # @type can be a string or a list of strings
                            if isinstance(schema_type, str):
                                schema_types_set.add(schema_type)
                            elif isinstance(schema_type, list):
                                schema_types_set.update(schema_type)  # Use update for lists

            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON-LD content: {script.string[:100]}...")
            except Exception as e:
                print(f"Warning: Error processing script tag: {e}")

        # 2. Check for Microdata (itemscope, itemtype) - Less common now
        microdata_items = soup.find_all(attrs={'itemscope': True})
        if microdata_items:
            results["schema_markup_present"] = True  # Mark as present if found
            for item in microdata_items:
                # Check if the element itself or a direct child has 'itemtype'
                itemtype = item.get('itemtype')
                if itemtype:
                    # Extract the type (often the last part of the URL)
                    schema_name = itemtype.split('/')[-1]
                    schema_types_set.add(schema_name)

        # 3. Check for RDFa (typeof) - Even less common for general schema
        rdfa_items = soup.find_all(attrs={'typeof': True})
        if rdfa_items:
            results["schema_markup_present"] = True
            for item in rdfa_items:
                type_val = item.get('typeof')
                if type_val:
                    # RDFa types can be prefixed (e.g., schema:Article)
                    # or just the name (e.g., Article)
                    schema_name = type_val.split(':')[-1]  # Basic extraction
                    schema_types_set.add(schema_name)

        # Finalize schema types list
        results["schema_types_found"] = sorted(list(schema_types_set))

        # Check for specific schema types (case-insensitive check might be safer)
        article_types = {"Article", "NewsArticle", "BlogPosting", "TechArticle", "Report"}  # Add more as needed
        review_types = {"Review", "AggregateRating", "Rating", "Product"}  # Product often contains reviews/ratings

        for schema_type in schema_types_set:
            st_lower = schema_type.lower()
            if st_lower == "faqpage":
                results["specific_schemas"]["FAQPage"] = True
            # Check against sets for broader matching
            if schema_type in article_types or st_lower in {a.lower() for a in article_types}:
                results["specific_schemas"]["Article"] = True
            if schema_type in review_types or st_lower in {r.lower() for r in review_types}:
                results["specific_schemas"]["Review"] = True

        # --- 3c: HTML Semantics and Elements ---
        semantic_tags_list = [
            'header', 'footer', 'nav', 'main', 'article', 'aside', 'section',
            'details', 'summary', 'figure', 'figcaption', 'time', 'mark',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',  # Headings have semantic meaning
            'address', 'blockquote', 'cite', 'q', 'ul', 'ol', 'li', 'dl', 'dt', 'dd'  # Lists & definition lists
        ]
        non_semantic_tags = {'div', 'span'}  # Primary non-semantic containers

        all_elements = soup.find_all(True)  # Get all tags
        results["semantic_elements"]["all_tags_count"] = len(all_elements)

        found_semantic_tag_names = set()
        semantic_count = 0
        non_semantic_count = 0

        for element in all_elements:
            tag_name = element.name.lower()
            if tag_name in semantic_tags_list:
                found_semantic_tag_names.add(tag_name)
                semantic_count += 1
            elif tag_name in non_semantic_tags:
                non_semantic_count += 1

        results["semantic_elements"]["present"] = bool(found_semantic_tag_names)
        results["semantic_elements"]["unique_types_found"] = sorted(list(found_semantic_tag_names))
        results["semantic_elements"]["count_unique_types"] = len(found_semantic_tag_names)
        results["semantic_elements"]["semantic_tags_count"] = semantic_count
        results["semantic_elements"]["non_semantic_tags_count"] = non_semantic_count

        if results["semantic_elements"]["all_tags_count"] > 0:
            # Calculate ratio based on semantic vs (semantic + non-semantic)
            total_structural_tags = semantic_count + non_semantic_count
            if total_structural_tags > 0:
                results["semantic_elements"]["semantic_ratio"] = round(semantic_count / total_structural_tags, 3)

        score = self._calculate_structured_data_score(results)
        results["score"] = score
        
        return score, results
    
    async def _analyze_knowledge_base_presence(self, company_name: str) -> Tuple[float, Dict[str, Any]]:
        results = {
            "has_wikipedia_page": False,
            "wikipedia_url": None,
            "score": 0.0
        }
        
        try:
            async with httpx.AsyncClient() as client:
                api_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "format": "json",
                    "titles": company_name,
                    "redirects": True
                }
                
                response = await client.get(api_url, params=params)
                data = response.json()
                
                if "query" in data and "pages" in data["query"]:
                    pages = data["query"]["pages"]
                    if "-1" not in pages:
                        page_id = next(iter(pages.keys()))
                        page_data = pages[page_id]
                        title = page_data.get("title", "")
                        
                        results["has_wikipedia_page"] = True
                        results["wikipedia_url"] = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        except Exception as e:
            print(f"Error checking Wikipedia presence: {str(e)}")
            results["error"] = str(e)
        
        results["score"] = 100.0 if results["has_wikipedia_page"] else 0.0
        
        return results["score"], results
    
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

    async def _analyze_crawler_accessibility(self, url: str, soup: BeautifulSoup) -> Tuple[float, Dict[str, Any]]:
        """
        Checks website accessibility for AI crawlers based on URL and soup.

        Args:
            url: The original URL of the website.
            soup: The BeautifulSoup object of the fetched HTML content.

        Returns:
            A dictionary containing accessibility checks:
            {
                "sitemap_found": bool,
                "robots_txt_found": bool,
                "pre_rendered_content": bool,
                },
                "pre_rendered_content": {
                    "likely_pre_rendered": bool, # Heuristic assessment
                    "text_length": int,
                    "js_framework_hint": bool # Indication if common JS frameworks detected
                },
                "language": {
                    "detected_language": str | None,
                    "is_english": bool | None,
                    "english_version_url": str | None # Found via hreflang
                },
                "score": float # 0-100 score based on the checks
            }
        """

        results = {
            "sitemap_found": False,
            "robots_txt_found": False,
            "pre_rendered_content": {
                "likely_pre_rendered": False,
                "text_length": 0,
                "js_framework_hint": False
            },
            "language": {
                "detected_language": None,
                "is_english": None,
                "english_version_url": None
            },
            "score": 0.0
        }

        # --- Prepare Base URL ---
        parsed_url = urlparse(url)
        base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, '', '', '', ''))
        if not base_url:
            print("Warning: Could not determine base URL.")
            return 0.0, results  # Cannot proceed with reliable checks

        # --- Check for robots.txt ---
        robots_found, _ = await check_robots_txt(url)
        results["robots_txt_found"] = robots_found

        # --- Check for sitemaps ---
        potential_sitemap_urls = await get_potential_sitemap_urls(url)
        
        # Check if any sitemap URL is actually a valid sitemap
        for s_url in potential_sitemap_urls:
            if await is_valid_sitemap(s_url):
                results["sitemap_found"] = True
                break

        # --- Check for Pre-rendered Content (Heuristic) ---
        body_text = ""
        if soup.body:
            # Remove script and style content before getting text
            for element in soup.body(["script", "style", "noscript"]):
                element.decompose()
            body_text = soup.body.get_text(separator=' ', strip=True)

        results["pre_rendered_content"]["text_length"] = len(body_text)

        # Heuristic: If body text length is reasonably long, assume some pre-rendering
        MIN_TEXT_LENGTH_THRESHOLD = 500
        if len(body_text) > MIN_TEXT_LENGTH_THRESHOLD:
            results["pre_rendered_content"]["likely_pre_rendered"] = True
        else:
            # Check for JS framework hints as another indicator
            scripts = soup.find_all('script', src=True)
            js_framework_patterns = re.compile(r'(react|angular|vue|next|nuxt|svelte)', re.IGNORECASE)
            for script in scripts:
                if script.get('src') and js_framework_patterns.search(script['src']):
                    results["pre_rendered_content"]["js_framework_hint"] = True
                    break  # Found one hint, that's enough

        # --- Check Language and English Version ---
        if body_text:  # Only detect if there is text
            try:
                # Use a sample for potentially very long text to speed up detection
                sample_text = body_text[:2000] if len(body_text) > 2000 else body_text
                lang = detect(sample_text)
                results["language"]["detected_language"] = lang
                results["language"]["is_english"] = (lang == 'en')

                if lang != 'en':
                    # Look for <link rel="alternate" hreflang="en" href="...">
                    alternate_links = soup.select('link[rel="alternate"][hreflang="en"]')
                    if alternate_links:
                        en_url = alternate_links[0].get('href')
                        if en_url:
                            # Resolve relative URLs
                            absolute_en_url = urljoin(base_url, en_url)
                            results["language"]["english_version_url"] = absolute_en_url
            except LangDetectException:
                print("Warning: Could not reliably detect language.")
            except Exception as e:
                print(f"Warning: An error occurred during language detection: {e}")

        # Calculate the score for crawler accessibility
        score = self._calculate_crawler_accessibility_score(results)
        results["score"] = score

        return score, results

    def _calculate_crawler_accessibility_score(self, results: Dict[str, Any]) -> float:
        """Calculate a score from 0-100 for crawler accessibility."""
        score = 0.0
        
        # 1. Sitemap availability (25 points)
        if results["sitemap_found"]:
            score += 25.0
        
        # 2. Robots.txt availability (15 points)
        if results["robots_txt_found"]:
            score += 15.0
        
        # 3. Pre-rendered content (30 points)
        if results["pre_rendered_content"]["likely_pre_rendered"]:
            score += 30.0
        elif not results["pre_rendered_content"]["js_framework_hint"]:
            # If no JS framework hint detected and reasonable text, give partial points
            if results["pre_rendered_content"]["text_length"] > 200:
                score += 15.0
        
        # 4. Language accessibility (30 points)
        if results["language"]["is_english"] is True:
            score += 30.0
        elif results["language"]["english_version_url"]:
            score += 20.0  # Partial credit for having an English version
        
        return min(100.0, score)
