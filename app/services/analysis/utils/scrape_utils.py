"""
Scraping utility functions.
This module contains utilities for scraping websites.
"""

import httpx
from bs4 import BeautifulSoup
import re
from typing import Tuple, Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse
import json
from urllib.parse import urljoin, urlparse, urlunparse

# Common user-agent for crawler detection
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
        response = await client.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Handle meta-refresh redirects
        meta = soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)})
        if meta:
            content = meta.get("content", "")
            match = re.search(r'url=(.+)', content, re.IGNORECASE)
            if match:
                redirect_url = match.group(1).strip()
                redirect_url = urljoin(str(response.url), redirect_url)
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
            response = await client.get(alt_url, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            tried_alternative = True
            
    # Extract all text content for analysis
    all_text = soup.get_text(separator=' ', strip=True)
    
    return soup, all_text

async def scrape_company_facts(soup: BeautifulSoup = None) -> dict:
    # Extract name from <title> or og:title
    name = ""
    if soup.title and soup.title.string:
        title_text = soup.title.string.strip()
        for separator in [' - ', ' | ', ' • ', ' : ', ' · ', ' – ', ': ', ' — ']:
            if separator in title_text:
                name = title_text.split(separator)[0].strip()
                break
        else:
            name = title_text
    
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title_text = og_title["content"].strip()
        for separator in [' - ', ' | ', ' • ', ' : ', ' · ', ' – ', ': ', ' — ']:
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

    # Try to extract structured data (JSON-LD)
    industry = ""
    founded = ""
    hq = ""
    key_products_services = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for entry in data:
                    if entry.get("@type") in ["Organization", "Corporation", "LocalBusiness"]:
                        if not name and entry.get("name"):
                            name = entry["name"]
                        if entry.get("description"):
                            description = entry["description"]
                        if entry.get("founder"):
                            founded = entry["founder"]
                        if entry.get("foundingDate"):
                            founded = entry["foundingDate"]
                        if entry.get("address"):
                            hq = entry["address"].get("addressLocality", "")
                        if entry.get("department"):
                            key_products_services.extend([d.get("name", "") for d in entry["department"] if d.get("name")])
                        if entry.get("makesOffer"):
                            offers = entry["makesOffer"]
                            if isinstance(offers, list):
                                key_products_services.extend([o.get("itemOffered", {}).get("name", "") for o in offers if o.get("itemOffered")])
                        elif isinstance(data, dict) and data.get("@type") in ["Organization", "Corporation", "LocalBusiness"]:
                            if not name and data.get("name"):
                                name = data["name"]
                            if data.get("description"):
                                description = data["description"]
                            if data.get("founder"):
                                founded = data["founder"]
                            if data.get("foundingDate"):
                                founded = data["foundingDate"]
                            if data.get("address"):
                                hq = data["address"].get("addressLocality", "")
                            if data.get("department"):
                                key_products_services.extend([d.get("name", "") for d in data["department"] if d.get("name")])
                            if data.get("makesOffer"):
                                offers = data["makesOffer"]
                                if isinstance(offers, list):
                                    key_products_services.extend([o.get("itemOffered", {}).get("name", "") for o in offers if o.get("itemOffered")])
        except Exception:
            continue

    # Remove empty strings and deduplicate
    key_products_services = list({k for k in key_products_services if k})

    return {
    "name": name,
    "industry": industry,
    "key_products_services": key_products_services,
    "founded": founded,
    "hq": hq,
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
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(robots_url, headers=CRAWLER_HEADERS, timeout=10)
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
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=CRAWLER_HEADERS, timeout=10, follow_redirects=True)
            
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