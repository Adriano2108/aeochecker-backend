"""
Scraping utility functions.
This module contains utilities for scraping websites.
"""

import httpx
from bs4 import BeautifulSoup
import re
from typing import Tuple
from urllib.parse import urljoin, urlparse
import json
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
