"""
AI Presence Analyzer module.
This module contains functionality to check how well large language models know about a company.
"""

import httpx
from bs4 import BeautifulSoup
import json
from typing import Tuple
import asyncio
import re
from urllib.parse import urljoin, urlparse

from app.services.analysis.base import BaseAnalyzer
from app.core.config import settings
from app.services.analysis.scrape_utils import scrape_website

from app.services.analysis.llm_utils import query_openai, query_anthropic, query_gemini

class AiPresenceAnalyzer(BaseAnalyzer):
    """Analyzer for checking AI presence of a company (how well AI models know about it)."""
    
    @staticmethod
    async def _get_company_facts(url: str, soup: BeautifulSoup = None) -> dict:
      # Use the centralized scraping function if soup is None
      if soup is None:
          soup, _ = await scrape_website(url)

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

    @staticmethod
    async def _query_llms(company_facts: dict) -> dict:
        prompt = (
          f"In 3-4 sentences, tell me about the company {company_facts['name']}. "
          f"Mention its industry, flagship product/service, headquarters city, and founding year if known."
        )

        print(prompt)
        
        responses = {}
        tasks = []
        
        if settings.OPENAI_API_KEY:
          tasks.append(query_openai(prompt))
        else:
          responses["openai"] = "API key not configured"
            
        if settings.ANTHROPIC_API_KEY:
          tasks.append(query_anthropic(prompt))
        else:
          responses["anthropic"] = "API key not configured"
            
        if settings.GEMINI_API_KEY:
          tasks.append(query_gemini(prompt))
        else:
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
    def _score_llm_response(company_facts: dict, response: str) -> Tuple[float, dict]:
        score = 0
        details = {}
        print(response)
        # Awareness
        if company_facts['name']:
            if company_facts['name'] in response:
                score += 10
                details['name'] = True
                print(f"+10: Name '{company_facts['name']}' found in response.")
            else:
                details['name'] = False
                print(f"0: Name '{company_facts['name']}' NOT found in response.")
        else:
            details['name'] = False
            print("SKIP: No name to check.")

        if company_facts['key_products_services']:
            if any(prod and prod in response for prod in company_facts['key_products_services']):
                score += 10
                details['product'] = True
                print(f"+10: At least one key product/service found in response.")
            else:
                details['product'] = False
                print(f"0: No key product/service found in response.")
        else:
            details['product'] = False
            print("SKIP: No key products/services to check.")

        if company_facts['hq']:
            if company_facts['hq'] in response:
                score += 3
                details['hq'] = True
                print(f"+3: HQ '{company_facts['hq']}' found in response.")
            else:
                details['hq'] = False
                print(f"0: HQ '{company_facts['hq']}' NOT found in response.")
        else:
            details['hq'] = False
            print("SKIP: No HQ to check.")

        if company_facts['founded']:
            if company_facts['founded'] in response:
                score += 3
                details['founded'] = True
                print(f"+3: Founded '{company_facts['founded']}' found in response.")
            else:
                details['founded'] = False
                print(f"0: Founded '{company_facts['founded']}' NOT found in response.")
        else:
            details['founded'] = False
            print("SKIP: No founded year to check.")

        if company_facts['industry']:
            if company_facts['industry'] in response:
                score += 3
                details['industry'] = True
                print(f"+3: Industry '{company_facts['industry']}' found in response.")
            else:
                details['industry'] = False
                print(f"0: Industry '{company_facts['industry']}' NOT found in response.")
        else:
            details['industry'] = False
            print("SKIP: No industry to check.")

        # Check for uncertainty phrases
        if any(x in response.lower() for x in ["i don't know", "I cannot confidently", "I apologize", "I don't have", "I cannot find", "I cannot tell", "I cannot find", "I cannot tell", "i can't tell", "i can't find"]):
            score -= 2
            details['uncertainty'] = True
            print("-2: Uncertainty phrase found in response.")
        else:
            details['uncertainty'] = False
            print("0: No uncertainty phrase found in response.")
        return score, details

    async def analyze(self, url: str, soup: BeautifulSoup = None) -> Tuple[dict, float, str]:
        """
        Analyze AI presence of a company website.
        
        Args:
            url: The URL of the company website
            soup: The BeautifulSoup object (if already parsed)
            
        Returns:
            Tuple containing:
            - company_facts: Dictionary of extracted company information
            - avg_score: A float between 0 and 1 representing the AI presence score
            - summary: String summary of the analysis results
        """
        # 1. Scrape facts
        company_facts = await self._get_company_facts(url, soup)

        if company_facts["name"] == "":
          return company_facts, 0, "No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis."
        
        # 2. Query LLMs
        llm_responses = await self._query_llms(company_facts)
        # 3. Score each response
        scores = {}
        details = {}
        for model, response in llm_responses.items():
            score, detail = self._score_llm_response(company_facts, response)
            scores[model] = score
            details[model] = detail
            print(score, detail)
        # 4. Aggregate
        avg_score = sum(scores.values()) / len(scores)
        summary_parts = ["AI Presence Analysis:"]
        if 'openai' in scores:
            summary_parts.append(f"OpenAI: {scores['openai']}")
        if 'anthropic' in scores:
            summary_parts.append(f"Anthropic: {scores['anthropic']}")
        if 'gemini' in scores:
            summary_parts.append(f"Gemini: {scores['gemini']}")
        summary_parts.append(f"Average: {avg_score:.2f}")
        summary = ", ".join(summary_parts)
        return company_facts, avg_score, summary 