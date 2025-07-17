"""
Scraping utility functions.
This module contains utilities for scraping websites.
"""

import json
import httpx
from bs4 import BeautifulSoup
import re
import random
import asyncio
from typing import Tuple, Dict, List, Any
from urllib.parse import urljoin, urlparse, urlunparse
from app.services.analysis.utils.llm_utils import query_openai
import gzip
import io
from bs4 import Comment

# Add brotli import for decompression
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False

CRAWLER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
}

def _get_random_headers() -> Dict[str, str]:
    """
    Generate randomized browser headers to avoid detection.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    
    accept_languages = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9",
        "en-US,en;q=0.8,es;q=0.7",
        "en-US,en;q=0.9,fr;q=0.8",
        "en-US,en;q=0.9,de;q=0.8"
    ]
    
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": random.choice(accept_languages),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

def _get_conservative_headers() -> Dict[str, str]:
    """
    Generate very conservative headers that mimic a regular browser session.
    Used for sites with aggressive bot detection.
    """
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

async def scrape_website_conservative(url: str) -> Tuple[BeautifulSoup, str]:
    """
    Conservative scraping approach for heavily protected websites.
    Uses minimal headers and longer delays.
    """
    print(f"Attempting conservative scraping for {url}")
    
    # Very conservative timeout settings
    timeout_config = httpx.Timeout(
        connect=15.0,   
        read=20.0,      
        write=15.0,     
        pool=10.0       
    )
    
    try:
        headers = _get_conservative_headers()
        
        async with httpx.AsyncClient(
            timeout=timeout_config,
            follow_redirects=True,
            verify=True
        ) as client:
            # Add a longer initial delay
            await asyncio.sleep(random.uniform(3.0, 6.0))
            
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            all_text = _extract_clean_text(soup)
            
            return soup, all_text
            
    except Exception as e:
        print(f"Conservative scraping also failed: {str(e)}")
        raise

async def scrape_website(url: str, max_retries: int = 3) -> Tuple[BeautifulSoup, str]:
    """
    Scrape a website and return the BeautifulSoup object and extracted text.
    Handles redirects, www vs non-www variations, and includes anti-bot detection measures.
    
    Args:
        url: The URL of the website to scrape
        max_retries: Maximum number of retry attempts for 403 errors
        
    Returns:
        Tuple containing:
        - soup: BeautifulSoup object of the parsed HTML
        - all_text: Extracted text content from the website
    """
    
    # Extended timeout settings for better stability
    timeout_config = httpx.Timeout(
        connect=10.0,   # Time to establish connection
        read=15.0,      # Time to read response
        write=10.0,     # Time to write request
        pool=8.0        # Time to get connection from pool
    )
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            # Get fresh headers for each attempt
            headers = _get_random_headers()
            
            # Add random delay between attempts (except first attempt)
            if attempt > 0:
                delay = random.uniform(2.0, 5.0)
                print(f"Waiting {delay:.1f} seconds before retry {attempt + 1}")
                await asyncio.sleep(delay)
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                follow_redirects=True,
                verify=True,  # SSL verification
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                print(f"Attempting to scrape {url} (attempt {attempt + 1}/{max_retries})")
                
                response = await client.get(url, headers=headers)
                response.raise_for_status()  # Raise an exception for bad status codes
                
                soup = BeautifulSoup(response.text, "html.parser")

                # Handle meta-refresh redirects
                meta = soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)})
                if meta:
                    content = meta.get("content", "")
                    match = re.search(r'url=(.+)', content, re.IGNORECASE)
                    if match:
                        redirect_url = match.group(1).strip()
                        redirect_url = urljoin(str(response.url), redirect_url)
                        # Add small delay before following redirect
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        response = await client.get(redirect_url, headers=headers)
                        soup = BeautifulSoup(response.text, "html.parser")

                # Check for 'Redirecting...' or empty content, and try alternative www/non-www
                def is_redirecting_only(soup):
                    body = soup.body
                    if body and body.get_text(strip=True).lower() in ["redirecting...", "redirecting", ""]:
                        return True
                    return False

                tried_alternative = False
                while is_redirecting_only(soup) and not tried_alternative:
                    parsed = urlparse(url)
                    netloc = parsed.netloc
                    if netloc.startswith("www."):
                        alt_netloc = netloc[4:]
                    else:
                        alt_netloc = "www." + netloc
                    alt_url = parsed._replace(netloc=alt_netloc).geturl()
                    # Add small delay before trying alternative
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    response = await client.get(alt_url, headers=headers)
                    soup = BeautifulSoup(response.text, "html.parser")
                    tried_alternative = True
                
                # Extract clean text content for analysis
                all_text = _extract_clean_text(soup)
                
                # Success! Return the results
                return soup, all_text
                        
        except httpx.TimeoutException as e:
            last_exception = e
            print(f"Timeout error while scraping {url} (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                raise Exception(f"Website took too long to respond after {max_retries} attempts: {url}")
            
        except httpx.HTTPStatusError as e:
            last_exception = e
            print(f"HTTP error while scraping {url} (attempt {attempt + 1}): {e.response.status_code}")
            
            if e.response.status_code == 403:
                # For 403 errors, try different strategies
                if attempt < max_retries - 1:
                    print(f"Got 403 error, will retry with different headers and delay")
                    continue
                else:
                    # Last attempt - try conservative approach
                    print(f"All standard attempts failed, trying conservative approach...")
                    try:
                        return await scrape_website_conservative(url)
                    except Exception as conservative_error:
                        print(f"Conservative approach also failed: {conservative_error}")
                        raise Exception(f"Access forbidden (403) - website is blocking automated requests after {max_retries} attempts and conservative fallback: {url}")
            elif e.response.status_code == 429:
                # Rate limiting - wait longer before retry
                if attempt < max_retries - 1:
                    delay = random.uniform(5.0, 10.0)
                    print(f"Rate limited, waiting {delay:.1f} seconds before retry")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise Exception(f"Rate limited (429) - website is blocking requests after {max_retries} attempts: {url}")
            elif e.response.status_code == 404:
                raise Exception(f"Page not found (404): {url}")
            else:
                if attempt == max_retries - 1:
                    raise Exception(f"HTTP error {e.response.status_code} after {max_retries} attempts: {url}")
                
        except httpx.RequestError as e:
            last_exception = e
            print(f"Request error while scraping {url} (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                raise Exception(f"Failed to connect to website after {max_retries} attempts: {url}")
                
        except Exception as e:
            last_exception = e
            print(f"Unexpected error while scraping {url} (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                raise
    
    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    else:
        raise Exception(f"Failed to scrape {url} after {max_retries} attempts")

def _extract_clean_text(soup: BeautifulSoup) -> str:
    """
    Extract clean, readable text from BeautifulSoup object.
    Filters out binary content, scripts, and non-printable characters.
    """
    # Remove problematic elements that often contain binary/encoded content
    for element in soup(['script', 'style', 'noscript', 'meta', 'link', 'head']):
        element.decompose()
    
    # Remove HTML comments
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()
    
    # Remove elements with data URIs (often contain base64 encoded binary data)
    for element in soup.find_all(attrs={'src': re.compile(r'^data:', re.I)}):
        element.decompose()
    for element in soup.find_all(attrs={'href': re.compile(r'^data:', re.I)}):
        element.decompose()
    
    # Extract text from remaining elements
    all_text = soup.get_text(separator=' ', strip=True)
    
    # More robust character filtering
    # Remove control characters and other problematic characters, but keep Unicode letters/digits
    # This pattern removes characters below space (0x20) except tabs and newlines which we'll convert to spaces
    clean_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', all_text)
    
    # Replace any remaining tabs and newlines with spaces
    clean_text = re.sub(r'[\t\n\r]', ' ', clean_text)
    
    # Remove excessive whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Additional check: if we still have a high ratio of suspicious characters, 
    # fall back to extracting only from content elements
    if len(clean_text) > 100:
        # Count characters that are clearly problematic (non-printable and not normal Unicode)
        suspicious_chars = sum(1 for c in clean_text if not c.isprintable() and ord(c) not in [9, 10, 13])  # Exclude tab, newline, carriage return
        
        # If more than 5% of characters are suspicious, extract from specific elements only
        if suspicious_chars / len(clean_text) > 0.05:
            print(f"[DEBUG] High ratio of suspicious characters ({suspicious_chars}/{len(clean_text)}),"
                 + " falling back to content-only extraction")
            
            # Try to extract only from common content elements
            content_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'div', 'span', 'article', 'section', 'main', 'nav', 'footer', 'header'])
            if content_elements:
                content_texts = []
                for element in content_elements:
                    element_text = element.get_text(strip=True)
                    # Apply same cleaning to element text
                    element_text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', element_text)
                    element_text = re.sub(r'[\t\n\r]', ' ', element_text)
                    element_text = re.sub(r'\s+', ' ', element_text).strip()
                    
                    # Only include meaningful text chunks
                    if element_text and len(element_text) > 3:
                        content_texts.append(element_text)
                
                if content_texts:
                    clean_text = ' '.join(content_texts)
    
    return clean_text

def _extract_industry_and_products(soup: BeautifulSoup, all_text: str) -> Dict[str, Any]:
    """
    Extracts industry and key products/services from BeautifulSoup object and text.
    """
    industry = ""
    key_products_services = []
    potential_industries = []

    # 1. JSON-LD Processing
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            entries = data if isinstance(data, list) else [data]  # Handle both list and dict

            for entry in entries:
                if not isinstance(entry, dict):
                    continue  # Skip if entry is not a dictionary

                entry_type = entry.get("@type", "")
                # Ensure entry_types is always a list for consistent processing
                entry_types = [entry_type] if isinstance(entry_type, str) else (entry_type if isinstance(entry_type, list) else [])


                # Industry extraction
                if any(t in ["Organization", "Corporation", "LocalBusiness"] for t in entry_types):
                    if entry.get("industry"):
                        raw_industry = entry.get("industry")
                        if isinstance(raw_industry, str):
                            potential_industries.append(raw_industry)
                        elif isinstance(raw_industry, list): # Sometimes industry is a list
                            potential_industries.extend(filter(None, raw_industry))
                    if entry.get("knowsAbout"):  # Can be string, dict, or list of strings/dicts
                        knows_about = entry.get("knowsAbout")
                        if isinstance(knows_about, list):
                            for item in knows_about:
                                if isinstance(item, dict) and item.get("name"):
                                    potential_industries.append(item["name"])
                                elif isinstance(item, str):
                                    potential_industries.append(item)
                        elif isinstance(knows_about, dict) and knows_about.get("name"):
                            potential_industries.append(knows_about["name"])
                        elif isinstance(knows_about, str):
                            potential_industries.append(knows_about)
                
                if "Service" in entry_types and entry.get("serviceType"):
                    service_type = entry.get("serviceType")
                    if isinstance(service_type, str):
                        potential_industries.append(service_type)
                    elif isinstance(service_type, list):
                        potential_industries.extend(filter(None, service_type))
                
                if "Product" in entry_types and entry.get("category"):
                    # Product category might sometimes be an industry or broader classification
                    category = entry.get("category")
                    if isinstance(category, str):
                        potential_industries.append(category)
                    elif isinstance(category, dict) and category.get("name"):
                        potential_industries.append(category["name"])


                # Key Products/Services extraction
                if any(t in ["Organization", "Corporation", "LocalBusiness", "Product", "Service"] for t in entry_types):
                    if entry.get("department"): # Typically list of department objects
                        departments = entry.get("department", [])
                        if isinstance(departments, list):
                            key_products_services.extend([d.get("name", "") for d in departments if isinstance(d, dict) and d.get("name")])
                    
                    if entry.get("makesOffer"): # Typically list of Offer objects
                        offers = entry.get("makesOffer", [])
                        if isinstance(offers, list):
                            for o in offers:
                                if isinstance(o, dict) and o.get("itemOffered"):
                                    item = o.get("itemOffered")
                                    if isinstance(item, dict) and item.get("name"):
                                        key_products_services.append(item["name"])
                                    elif isinstance(item, str): # Less common, itemOffered might be a string
                                        key_products_services.append(item)
                    
                    # If entry itself is a Product or Service
                    if any(t in ["Product", "Service"] for t in entry_types) and entry.get("name"):
                        key_products_services.append(entry.get("name"))
                    
                    # Product category can sometimes be a specific product line or service type
                    if "Product" in entry_types and entry.get("category"):
                        category = entry.get("category")
                        if isinstance(category, str):
                             key_products_services.append(category)
                        elif isinstance(category, dict) and category.get("name"):
                             key_products_services.append(category["name"])


        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            continue

    # Consolidate and choose industry
    # Simple strategy: first non-empty, reasonably specific candidate
    for ind_candidate in potential_industries:
        if isinstance(ind_candidate, str) and ind_candidate.strip() and len(ind_candidate.strip()) > 2 : # Avoid very short/generic
            industry = ind_candidate.strip()
            break
    
    # 2. Meta Keywords
    meta_keywords_tag = soup.find("meta", attrs={"name": "keywords"})
    keywords_to_add = [] # Initialize list for keywords to add to KPS
    if meta_keywords_tag and meta_keywords_tag.get("content"):
        keywords = [k.strip() for k in meta_keywords_tag["content"].split(',') if k.strip()]
        used_keyword_for_industry = False
        if not industry and keywords: # Check if industry is empty and keywords exist
            industry = keywords[0] # Assign the first keyword to industry
            used_keyword_for_industry = True
        
        # Add keywords to KPS, skipping the first if it was used for industry
        if used_keyword_for_industry:
            keywords_to_add = keywords[1:] 
        elif keywords: # Only add if keywords were found
            keywords_to_add = keywords
            
    key_products_services.extend(keywords_to_add) # Extend KPS list

    # Deduplicate and clean key_products_services
    cleaned_kps = []
    seen_kps = set()
    for kps_item in key_products_services:
        if isinstance(kps_item, str):
            item_stripped = kps_item.strip()
            if item_stripped and len(item_stripped) > 1 and item_stripped.lower() not in seen_kps:
                cleaned_kps.append(item_stripped)
                seen_kps.add(item_stripped.lower())
    
    final_kps = cleaned_kps[:4] # Limit to first 4 items

    return {
        "industry": industry,
        "key_products_services": final_kps,
    }

def extract_company_name(soup: BeautifulSoup, url: str) -> str:
    """
    Extract the company name from various sources using frequency analysis and priority rules.
    
    Args:
        soup: BeautifulSoup object of the parsed HTML
        url: The URL of the website
        
    Returns:
        The most likely company name
    """
    
    def _remove_domain_extension(name: str) -> str:
        """
        Remove common domain extensions from a company name.
        E.g., 'Amazon.com' becomes 'Amazon'
        """
        if not name:
            return name
            
        # Common domain extensions to remove
        domain_extensions = [
            '.com', '.net', '.org', '.io', '.co', '.ai', '.app', '.dev', 
            '.tech', '.biz', '.info', '.me', '.tv', '.cc', '.ly', '.to',
            '.us', '.uk', '.ca', '.de', '.fr', '.jp', '.au', '.in'
        ]
        
        name_lower = name.lower()
        for extension in domain_extensions:
            if name_lower.endswith(extension):
                # Remove the extension and return the cleaned name
                # Preserve original case from the beginning
                return name[:len(name) - len(extension)]
        
        return name
    
    print(f"\n[DEBUG] Starting company name extraction for URL: {url}")
    
    potential_names = []
    separators = [' - ', ' | ', ' • ', ' : ', ' · ', ' – ', ': ', ' — ', ' . ']  # Added '. ' for period + space
    
    # 1. Check for og:site_name and similar clear site identifiers (HIGHEST PRIORITY)
    site_name_selectors = [
        ("meta", {"property": "og:site_name"}),
        ("meta", {"name": "application-name"}),
        ("meta", {"name": "apple-mobile-web-app-title"}),
        ("meta", {"property": "twitter:site"}),
    ]
    
    high_priority_names = []  # Track high-priority names separately
    print(f"[DEBUG] Checking high-priority sources (og:site_name, etc.)...")
    for tag_name, attrs in site_name_selectors:
        element = soup.find(tag_name, attrs)
        if element and element.get("content"):
            content = element["content"].strip()
            # Clean up Twitter handle format
            if content.startswith("@"):
                content = content[1:]
            if content and len(content.split()) <= 3:  # Site names should be short
                print(f"[DEBUG] Found high-priority name: '{content}' from {attrs}")
                potential_names.append(content)
                high_priority_names.append(content)
    
    print(f"[DEBUG] High-priority names found: {high_priority_names}")
    
    # 2. Check title tag (MEDIUM-HIGH PRIORITY)
    title_based_names = []  # Track title-based names separately
    print(f"[DEBUG] Checking <title> tag...")
    if soup.title and soup.title.string:
        title_text = soup.title.string.strip()
        print(f"[DEBUG] Title text: '{title_text}'")
        found_separator = False
        
        for separator in separators:
            if separator in title_text:
                print(f"[DEBUG] Found separator '{separator}' in title")
                parts = title_text.split(separator, 1)  # Split only on first occurrence
                left_part = parts[0].strip()
                right_part = parts[1].strip() if len(parts) > 1 else ""
                
                print(f"[DEBUG] Title parts - Left: '{left_part}', Right: '{right_part}'")
                
                # Add both parts if they're 3 words or less
                if left_part and len(left_part.split()) <= 3:
                    print(f"[DEBUG] Adding left part from title: '{left_part}'")
                    potential_names.append(left_part)
                    title_based_names.append(left_part)
                if right_part and len(right_part.split()) <= 3:
                    print(f"[DEBUG] Adding right part from title: '{right_part}'")
                    potential_names.append(right_part)
                    title_based_names.append(right_part)
                
                found_separator = True
                break
        
        if not found_separator:
            word_count = len(title_text.split())
            print(f"[DEBUG] No separator found in title, word count: {word_count}")
            if word_count <= 3:
                print(f"[DEBUG] Adding whole title: '{title_text}'")
                potential_names.append(title_text)
                title_based_names.append(title_text)
    
    # 3. Check og:title (MEDIUM-HIGH PRIORITY)
    print(f"[DEBUG] Checking og:title...")
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title_text = og_title["content"].strip()
        print(f"[DEBUG] OG title text: '{title_text}'")
        found_separator = False
        
        for separator in separators:
            if separator in title_text:
                print(f"[DEBUG] Found separator '{separator}' in og:title")
                parts = title_text.split(separator, 1)  # Split only on first occurrence
                left_part = parts[0].strip()
                right_part = parts[1].strip() if len(parts) > 1 else ""
                
                print(f"[DEBUG] OG title parts - Left: '{left_part}', Right: '{right_part}'")
                
                # Add both parts if they're 3 words or less
                if left_part and len(left_part.split()) <= 3:
                    print(f"[DEBUG] Adding left part from og:title: '{left_part}'")
                    potential_names.append(left_part)
                    title_based_names.append(left_part)
                if right_part and len(right_part.split()) <= 3:
                    print(f"[DEBUG] Adding right part from og:title: '{right_part}'")
                    potential_names.append(right_part)
                    title_based_names.append(right_part)
                
                found_separator = True
                break
        
        if not found_separator:
            word_count = len(title_text.split())
            print(f"[DEBUG] No separator found in og:title, word count: {word_count}")
            if word_count <= 3:
                print(f"[DEBUG] Adding whole og:title: '{title_text}'")
                potential_names.append(title_text)
                title_based_names.append(title_text)
    
    print(f"[DEBUG] Title-based names found: {title_based_names}")
    
    # 4. Get domain name as fallback (LOWEST PRIORITY)
    print(f"[DEBUG] Extracting domain name...")
    domain_name = get_domain_name(url)
    domain_based_names = []
    if domain_name:
        print(f"[DEBUG] Domain name extracted: '{domain_name}'")
        potential_names.append(domain_name)
        domain_based_names.append(domain_name)
    
    print(f"[DEBUG] Domain-based names found: {domain_based_names}")
    
    # Remove empty strings and duplicates while preserving order for priority
    # Also apply domain extension removal during cleaning
    cleaned_names = []
    seen = set()
    for name in potential_names:
        if name:
            # Remove domain extension first
            cleaned_name = _remove_domain_extension(name)
            if cleaned_name and cleaned_name not in seen:
                cleaned_names.append(cleaned_name)
                seen.add(cleaned_name)
    
    print(f"[DEBUG] All potential names (deduplicated and domain-cleaned): {cleaned_names}")
    
    if not cleaned_names:
        print(f"[DEBUG] No names found, returning empty string")
        return ""
    
    # If we only have one name, return it (already domain-cleaned)
    if len(cleaned_names) == 1:
        print(f"[DEBUG] Only one name found, returning: '{cleaned_names[0]}'")
        return cleaned_names[0]
    
    # Count frequency of each name (case-insensitive)
    name_counts = {}
    for name in cleaned_names:
        name_lower = name.lower()
        name_counts[name_lower] = name_counts.get(name_lower, 0) + 1
    
    print(f"[DEBUG] Name frequency counts: {name_counts}")
    
    # Find the most frequent name(s)
    max_count = max(name_counts.values())
    most_frequent_names = [name for name in cleaned_names if name_counts[name.lower()] == max_count]
    
    print(f"[DEBUG] Most frequent names (count={max_count}): {most_frequent_names}")
    
    # If there's a clear winner by frequency (and it appears more than once), return it
    if len(most_frequent_names) == 1 and max_count > 1:
        print(f"[DEBUG] Clear frequency winner found: '{most_frequent_names[0]}'")
        return most_frequent_names[0]
    
    # Apply priority rules when there's no clear frequency winner
    print(f"[DEBUG] Applying priority rules...")
    
    # For priority checking, we need to match against the cleaned names
    cleaned_high_priority = [_remove_domain_extension(name) for name in high_priority_names]
    cleaned_title_based = [_remove_domain_extension(name) for name in title_based_names]
    cleaned_domain_based = [_remove_domain_extension(name) for name in domain_based_names]
    
    # Check for high-priority names first
    print(f"[DEBUG] Checking cleaned high-priority names: {cleaned_high_priority}")
    for name in cleaned_high_priority:
        if name in most_frequent_names:
            print(f"[DEBUG] Selected high-priority name: '{name}'")
            return name
    
    # Then check for title-based names
    print(f"[DEBUG] Checking cleaned title-based names: {cleaned_title_based}")
    for name in cleaned_title_based:
        if name in most_frequent_names:
            print(f"[DEBUG] Selected title-based name: '{name}'")
            return name
    
    # Finally check domain-based names
    print(f"[DEBUG] Checking cleaned domain-based names: {cleaned_domain_based}")
    for name in cleaned_domain_based:
        if name in most_frequent_names:
            print(f"[DEBUG] Selected domain-based name: '{name}'")
            return name
    
    # Return the first name as fallback (already domain-cleaned)
    print(f"[DEBUG] Using fallback - returning first name: '{cleaned_names[0]}'")
    return cleaned_names[0]

async def scrape_company_facts(url: str, soup: BeautifulSoup, all_text: str) -> dict:
    # Extract name using the new dedicated function
    name = extract_company_name(soup, url)

    # Extract description from meta or og:description
    description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        description = og_desc["content"].strip()

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if not isinstance(entry, dict): 
                    continue
                
                entry_type = entry.get("@type", "")
                entry_types = [entry_type] if isinstance(entry_type, str) else (entry_type if isinstance(entry_type, list) else [])

                if any(t in ["Organization", "Corporation", "LocalBusiness"] for t in entry_types):
                    if not name and entry.get("name"):
                        name = entry.get("name", "").strip()
                    # Prefer longer, more descriptive descriptions if multiple are found
                    json_ld_desc = entry.get("description", "").strip()
                    if json_ld_desc and len(json_ld_desc) > len(description):
                        description = json_ld_desc
                    
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            continue

    extracted_data = _extract_industry_and_products(soup, all_text)
    industry = extracted_data["industry"]
    key_products_services = extracted_data["key_products_services"]

    # 3. LLM Fallback if industry and KPS are still missing
    if not industry and not key_products_services:
        print(f"Attempting LLM fallback for URL: {url}")
        try:
            text_snippet = all_text[:1000].strip()
            prompt = f"""Analyze the following website information to determine its primary industry and up to 4 key products or services.

URL: {url}
Company Name: {name or 'Unknown'}
Description: {description or 'Not found'}
Website Text Snippet:
\"\"\"
{text_snippet}
\"\"\"

Provide the output strictly in the following format, with no extra explanation:
Industry: [The Industry]
Products: [Product/Service 1], [Product/Service 2], [Product/Service 3], [Product/Service 4]

If you cannot confidently determine the industry or products, write "Unknown" for that field.
"""
            llm_provider, llm_response_text = await query_openai(prompt)
            print(f"LLM ({llm_provider}) response:\n{llm_response_text}") # Log response

            industry_match = re.search(r"Industry:\s*(.*)", llm_response_text, re.IGNORECASE)
            products_match = re.search(r"Products:\s*(.*)", llm_response_text, re.IGNORECASE)

            if industry_match:
                llm_industry = industry_match.group(1).strip()
                if llm_industry.lower() != "unknown" and llm_industry:
                    industry = llm_industry

            if products_match:
                llm_products_str = products_match.group(1).strip()
                if llm_products_str.lower() != "unknown" and llm_products_str:
                    llm_products_list = [p.strip() for p in llm_products_str.split(',') if p.strip()]
                    key_products_services = llm_products_list[:4]

        except Exception as e:
            print(f"Error during LLM fallback for {url}: {e}")

    return {
        "name": name,
        "industry": industry,
        "key_products_services": key_products_services,
        "description": description,
    }

async def check_robots_txt(url: str) -> Tuple[bool, List[str]]:
    """
    Check for robots.txt file and extract sitemap URLs.
    
    Args:
        url: The base URL to check
        
    Returns:
        Tuple containing:
        - exists: Boolean indicating if robots.txt exists
        - sitemaps: List of sitemap URLs found in robots.txt
    """
    # Parse the base URL
    parsed_url = urlparse(url)
    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, '', '', '', ''))
    
    robots_url = urljoin(base_url, '/robots.txt')
    sitemap_urls = []
    exists = False
    
    # Use randomized headers for better bot avoidance
    headers = _get_random_headers()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(robots_url, headers=headers, timeout=10, follow_redirects=True)
            if response.status_code == 200:
                exists = True
                
                # Check if content is compressed
                content_type = response.headers.get('content-type', '').lower()
                content_encoding = response.headers.get('content-encoding', '').lower()
                
                # Get the content
                content = response.content
                
                # Check for different compression types
                is_gzipped = (
                    'gzip' in content_type or 
                    'gzip' in content_encoding or
                    'application/x-gzip' in content_type
                )
                
                is_brotli = (
                    'br' in content_encoding or
                    'brotli' in content_encoding
                )
                
                # Decompress if compressed
                if is_brotli and BROTLI_AVAILABLE:
                    try:
                        content = brotli.decompress(content)
                    except Exception as e:
                        print(f"Warning: Failed to decompress brotli robots.txt: {e}")
                        # Try to use response.text as fallback
                        robots_text = response.text
                elif is_gzipped:
                    try:
                        content = gzip.decompress(content)
                    except Exception as e:
                        print(f"Warning: Failed to decompress gzipped robots.txt: {e}")
                        # Try to use response.text as fallback
                        robots_text = response.text
                
                # Convert decompressed content to text
                if (is_brotli and BROTLI_AVAILABLE) or is_gzipped:
                    if isinstance(content, bytes):
                        try:
                            robots_text = content.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                robots_text = content.decode('latin-1')
                            except UnicodeDecodeError:
                                print(f"Warning: Could not decode robots.txt content")
                                robots_text = response.text  # Fallback
                    else:
                        robots_text = response.text  # Already text
                else:
                    # No compression or no brotli support - use response.text or decode manually
                    if is_brotli and not BROTLI_AVAILABLE:
                        print(f"Warning: Brotli compression detected but brotli module not available")
                    
                    # Convert to text
                    try:
                        robots_text = content.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            robots_text = content.decode('latin-1')
                        except UnicodeDecodeError:
                            robots_text = response.text  # Fallback to response.text
                
                # Extract Sitemap directives
                robots_content = robots_text.splitlines()
                
                # Method 1: Standard sitemap parsing
                for line in robots_content:
                    line_clean = line.strip()
                    if line_clean.lower().startswith('sitemap:'):
                        # Use line_clean instead of line for splitting
                        sitemap_url = line_clean.split(':', 1)[1].strip()
                        sitemap_urls.append(sitemap_url)
                
                # Method 2: Look for any line containing .xml (fallback)
                for line in robots_content:
                    line_clean = line.strip()
                    if '.xml' in line_clean.lower():
                        # Try to extract URL-like patterns
                        # Look for http/https URLs containing .xml
                        import re
                        url_pattern = r'https?://[^\s]+\.xml[^\s]*'
                        matches = re.findall(url_pattern, line_clean, re.IGNORECASE)
                        for match in matches:
                            if match not in sitemap_urls:
                                sitemap_urls.append(match)
                
    except Exception as e:
        print(f"Warning: Could not fetch robots.txt: {e}")
    
    return exists, sitemap_urls

async def is_valid_sitemap(url: str) -> bool:
    """
    Check if a URL points to a valid sitemap XML file.
    
    Args:
        url: The URL to check
        
    Returns:
        Boolean indicating if the URL is a valid sitemap
    """
    try:
        # Use randomized headers for better bot avoidance
        headers = _get_random_headers()
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
            
            # Check if the response is successful
            if response.status_code < 400:
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                
                # Get the content
                content = response.content
                
                # Check if the content is gzipped (either by content-type or URL extension)
                is_gzipped = (
                    'gzip' in content_type or 
                    'application/x-gzip' in content_type or
                    url.lower().endswith('.gz')
                )
                
                # Decompress if gzipped
                if is_gzipped:
                    try:
                        content = gzip.decompress(content)
                    except Exception as e:
                        print(f"Warning: Failed to decompress gzipped content for {url}: {e}")
                        return False
                
                # Convert to text
                try:
                    content_text = content.decode('utf-8')
                except UnicodeDecodeError:
                    # Try other encodings
                    try:
                        content_text = content.decode('latin-1')
                    except UnicodeDecodeError:
                        print(f"Warning: Could not decode content for {url}")
                        return False
                
                # Check if it's valid XML content type (after decompression)
                if any(x in content_type for x in ['application/xml', 'text/xml']) or is_gzipped:
                    # Verify that it contains sitemap-specific elements
                    is_sitemap = bool(re.search(r'<\s*(urlset|sitemapindex)[^>]*>', content_text))
                    
                    # Additional check for URL entries
                    has_urls = bool(re.search(r'<\s*url\s*>|<\s*sitemap\s*>', content_text))
                    
                    return is_sitemap and has_urls
                    
            return False
    except Exception as e:
        print(f"Warning: Failed to validate sitemap at {url}: {e}")
        return False

async def get_potential_sitemap_urls(url: str) -> List[str]:
    """
    Get a list of potential sitemap URLs for a website.
    
    Args:
        url: The base URL of the website
        
    Returns:
        A list of potential sitemap URLs
    """
    # Parse the base URL
    parsed_url = urlparse(url)
    base_url = urlunparse((parsed_url.scheme, parsed_url.netloc, '', '', '', ''))
    
    # Check common sitemap locations
    potential_urls = set()
    potential_urls.add(urljoin(base_url, '/sitemap.xml'))
    potential_urls.add(urljoin(base_url, '/sitemap_index.xml'))
    potential_urls.add(urljoin(base_url, '/sitemap-index.xml'))
    
    # Add sitemaps from robots.txt
    _, robot_sitemaps = await check_robots_txt(url)
    potential_urls.update(robot_sitemaps)
    
    return sorted(list(potential_urls))

async def _validate_and_get_best_url(url: str) -> str:
    """
    Validates a URL and determines the best working version by testing multiple variations:
    1. Original URL
    2. www vs non-www versions
    3. Common retail subdomains (www2, shop, store, etc.)
    
    Returns the best URL to use for analysis.
    """
    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
    # Create variations to test
    urls_to_check = []
    
    # Original URL first
    urls_to_check.append(url)
    
    # www vs non-www variations
    if domain.startswith('www.'):
        base_domain = domain[4:]
        non_www_url = urlunparse((parsed_url.scheme, base_domain, parsed_url.path, 
                                parsed_url.params, parsed_url.query, parsed_url.fragment))
        urls_to_check.append(non_www_url)
    else:
        www_url = urlunparse((parsed_url.scheme, f"www.{domain}", parsed_url.path, 
                            parsed_url.params, parsed_url.query, parsed_url.fragment))
        urls_to_check.append(www_url)
    
    # Common retail/e-commerce subdomains
    base_domain = domain[4:] if domain.startswith('www.') else domain
    common_subdomains = ['www2', 'shop', 'store', 'en', 'us', 'global']
    
    for subdomain in common_subdomains:
        subdomain_url = urlunparse((parsed_url.scheme, f"{subdomain}.{base_domain}", parsed_url.path, 
                                  parsed_url.params, parsed_url.query, parsed_url.fragment))
        urls_to_check.append(subdomain_url)
    
    best_url = url  # Default to original URL
    best_score = -1
    all_403_errors = True  # Track if all URLs return 403
    
    # Extended timeout for validation with better headers
    timeout_config = httpx.Timeout(connect=8.0, read=12.0, write=8.0, pool=5.0)
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_config) as client:
        for check_url in urls_to_check:
            try:
                # Use randomized headers for each check
                headers = _get_random_headers()
                response = await client.get(check_url, headers=headers)
                
                # If we got any non-403 response, the site isn't completely blocked
                if response.status_code != 403:
                    all_403_errors = False
                
                # Calculate a score based on status code and response size
                score = 0
                
                # Prefer 200 status codes
                if response.status_code == 200:
                    score += 100
                elif response.status_code >= 300 and response.status_code < 400:
                    score += 50  # Redirects are okay but not ideal
                elif response.status_code == 403:
                    score -= 25  # 403 is bad but still a valid response (bot blocking)
                elif response.status_code >= 400:
                    score -= 50  # Other error codes are worse
                
                # Prefer responses with more content (only for successful responses)
                if response.status_code < 400:
                    content_length = len(response.content)
                    score += min(content_length // 1000, 50)  # Up to 50 points for content
                
                # Check if this URL is better than our current best
                if score > best_score:
                    best_score = score
                    best_url = check_url
                    
                    # If we got a perfect score (200 status + content), no need to check further
                    if response.status_code == 200 and len(response.content) > 5000:
                        break
                        
            except Exception as e:
                all_403_errors = False  # Other errors mean it's not just 403s
                error_msg = str(e)
                # Show HTTP status codes specifically
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    error_msg = f"HTTP {e.response.status_code}"
                    if e.response.status_code == 403:
                        all_403_errors = True  # This was actually a 403
                print(f"Error checking URL {check_url}: {error_msg}")
                # Skip this URL if it errors out
    
    # If all URLs returned 403, the site is bot-blocked
    if all_403_errors and best_score < 0:
        print(f"Website appears to be blocking all automated requests (403 Forbidden)")
    
    return best_url

def get_domain_name(url: str) -> str:
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        # Remove 'www.' prefix if exists
        if domain.startswith('www.'):
            domain = domain[4:]
        # Extract the main part before the first dot (e.g., 'github' from 'github.com')
        name_from_domain = domain.split('.')[0]
        # Capitalize the first letter
        if name_from_domain:
            return name_from_domain[0].upper() + name_from_domain[1:]
    except Exception: 
        pass
    return ""