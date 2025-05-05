"""
Scraping utility functions.
This module contains utilities for scraping websites.
"""

import httpx
from bs4 import BeautifulSoup
import re
from typing import Tuple
from urllib.parse import urljoin, urlparse

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
