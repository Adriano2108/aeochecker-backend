"""
Scraping utility functions.
This module contains utilities for scraping websites.
"""

import json
import httpx
from bs4 import BeautifulSoup
import re
from typing import Tuple, Dict, List, Any
from urllib.parse import urljoin, urlparse, urlunparse
from app.services.analysis.utils.llm_utils import query_openai

CRAWLER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
}

async def scrape_website(url: str) -> Tuple[BeautifulSoup, str]:
    """
    Scrape a website and return the BeautifulSoup object and extracted text.
    Handles redirects and www vs non-www variations.
    
    Args:
        url: The URL of the website to scrape
        
    Returns:
        Tuple containing:
        - soup: BeautifulSoup object of the parsed HTML
        - all_text: Extracted text content from the website
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, follow_redirects=True)
        
        soup = BeautifulSoup(response.text, "html.parser")

        # Handle meta-refresh redirects
        meta = soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)})
        if meta:
            content = meta.get("content", "")
            match = re.search(r'url=(.+)', content, re.IGNORECASE)
            if match:
                redirect_url = match.group(1).strip()
                redirect_url = urljoin(str(response.url), redirect_url)
                response = await client.get(redirect_url, headers=headers, follow_redirects=True)
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
            response = await client.get(alt_url, headers=headers, follow_redirects=True)
            soup = BeautifulSoup(response.text, "html.parser")
            tried_alternative = True
            
    # Extract all text content for analysis
    all_text = soup.get_text(separator=' ', strip=True)
    
    return soup, all_text

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

async def scrape_company_facts(url: str, soup: BeautifulSoup, all_text: str) -> dict:
    # Extract name from <title> or og:title
    name = ""
    if soup.title and soup.title.string:
        title_text = soup.title.string.strip()
        for separator in [' - ', ' | ', ' • ', ' : ', ' · ', ' – ', ': ', ' — ', "."]:
            if separator in title_text:
                name = title_text.split(separator)[0].strip()
                break
        else:
            name = title_text
    
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title_text = og_title["content"].strip()
        for separator in [' - ', ' | ', ' • ', ' : ', ' · ', ' – ', ': ', ' — ', "."]:
            if separator in title_text:
                name = title_text.split(separator)[0].strip()
                break
        else:
            name = title_text

    # Extract description from meta or og:description
    description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        description = og_desc["content"].strip()

    # Initialize fields that will be extracted from JSON-LD or other means
    founded = ""
    
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
                    
                    # foundingDate is preferred for the 'founded' field
                    if entry.get("foundingDate"):
                        founded = entry.get("foundingDate", "").strip()
                    elif not founded and entry.get("founder"): # Fallback if foundingDate not present
                        # 'founder' might be a person/org, not a date. Less ideal for "founded year".
                        # This assignment is kept from original logic but might need review for semantic correctness.
                        # For now, if it's a string, assign. If dict/list, ignore for 'founded'.
                        founder_info = entry.get("founder")
                        if isinstance(founder_info, str):
                            founded = founder_info.strip() # Or perhaps log a warning: "Using founder name as founded date"

        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            continue

    # Fallback for name extraction: use domain name if still empty
    if not name:
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
                name = name_from_domain[0].upper() + name_from_domain[1:]
        except Exception: 
            pass

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
        "founded": founded,
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
    
    # Use the same headers as the main scraping function instead of Googlebot headers
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(robots_url, headers=headers, timeout=10, follow_redirects=True)
            if response.status_code == 200:
                exists = True
                # Extract Sitemap directives
                robots_content = response.text.splitlines()
                for line in robots_content:
                    if line.strip().lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemap_urls.append(sitemap_url)
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
        # Use the same headers as the main scraping function
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10, follow_redirects=True)
            
            # Check if the response is successful
            if response.status_code < 400:
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if any(x in content_type for x in ['application/xml', 'text/xml']):
                    # Verify that it contains sitemap-specific elements
                    content = response.text
                    is_sitemap = bool(re.search(r'<\s*(urlset|sitemapindex)[^>]*>', content))
                    
                    # Additional check for URL entries
                    has_urls = bool(re.search(r'<\s*url\s*>|<\s*sitemap\s*>', content))
                    
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
    Validates a URL and determines whether to use www or non-www version based on:
    1. HTTP status codes and redirects
    2. Content availability
    
    Returns the best URL to use for analysis.
    """
    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
    # Create www and non-www versions for testing
    www_domain = f"www.{domain}" if not domain.startswith('www.') else domain
    non_www_domain = domain[4:] if domain.startswith('www.') else domain
    
    www_url = urlunparse((parsed_url.scheme, www_domain, parsed_url.path, 
                            parsed_url.params, parsed_url.query, parsed_url.fragment))
    non_www_url = urlunparse((parsed_url.scheme, non_www_domain, parsed_url.path, 
                                parsed_url.params, parsed_url.query, parsed_url.fragment))
    
    urls_to_check = [www_url, non_www_url]
    best_url = url  # Default to original URL
    best_score = -1
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for check_url in urls_to_check:
            try:
                response = await client.get(check_url, timeout=10.0)
                
                # Calculate a score based on status code and response size
                score = 0
                
                # Prefer 200 status codes
                if response.status_code == 200:
                    score += 100
                elif response.status_code >= 300 and response.status_code < 400:
                    score += 50  # Redirects are okay but not ideal
                elif response.status_code >= 400:
                    score -= 50  # Error codes are bad
                
                # Prefer responses with more content
                content_length = len(response.content)
                score += min(content_length // 1000, 50)  # Up to 50 points for content
                
                # Check if this URL is better than our current best
                if score > best_score:
                    best_score = score
                    best_url = check_url
                    
                    # If we got a perfect score (200 status + content), no need to check further
                    if response.status_code == 200 and content_length > 5000:
                        break
                        
            except Exception as e:
                print(f"Error checking URL {check_url}: {str(e)}")
                # Skip this URL if it errors out
    
    return best_url