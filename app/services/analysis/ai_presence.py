"""
AI Presence Analyzer module.
This module contains functionality to check how well large language models know about a company.
"""

import httpx
from bs4 import BeautifulSoup
import json
from typing import Dict, Any, Tuple
from app.services.analysis.base import BaseAnalyzer

class AiPresenceAnalyzer(BaseAnalyzer):
    """Analyzer for checking AI presence of a company (how well AI models know about it)."""
    
    @staticmethod
    async def _scrape_company_facts(url: str) -> dict:
      async with httpx.AsyncClient() as client:
        response = await client.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract name from <title> or og:title
        name = ""
        if soup.title and soup.title.string:
            name = soup.title.string.strip()
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            name = og_title["content"].strip()

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
        # Mocked LLM responses for now
        prompt = (
            f"In 3-4 sentences, tell me about the company '{company_facts['name']}'. "
            f"Mention its industry, flagship product/service, headquarters city, and founding year if known."
        )
        return {
            "openai": f"{company_facts['name']} is a company in the {company_facts['industry']} sector. Its flagship product is {company_facts['key_products_services'][0]}. The company is headquartered in {company_facts['hq']} and was founded in {company_facts['founded']}.",
            "anthropic": f"{company_facts['name']} operates in {company_facts['industry']}, known for products like {company_facts['key_products_services'][1]}. Based in {company_facts['hq']}, it was established in {company_facts['founded']}.",
            "gemini": f"Founded in {company_facts['founded']}, {company_facts['name']} is based in {company_facts['hq']} and specializes in {company_facts['industry']}. Their main product is {company_facts['key_products_services'][0]}."
        }

    @staticmethod
    def _score_llm_response(company_facts: dict, response: str) -> Tuple[float, dict]:
        score = 0
        details = {}
        # Awareness
        if company_facts['name'] in response:
            score += 10
            details['name'] = True
        else:
            details['name'] = False
        if any(prod in response for prod in company_facts['key_products_services']):
            score += 10
            details['product'] = True
        else:
            details['product'] = False
        if company_facts['hq'] in response:
            score += 3
            details['hq'] = True
        else:
            details['hq'] = False
        if company_facts['founded'] in response:
            score += 3
            details['founded'] = True
        else:
            details['founded'] = False
        if company_facts['industry'] in response:
            score += 3
            details['industry'] = True
        else:
            details['industry'] = False
        # Accuracy (mocked as always accurate)
        score += 5
        details['accuracy'] = True
        # Check for uncertainty phrases
        if any(x in response.lower() for x in ["i don't know", "i can't tell", "i can't find"]):
            score -= 2
            details['uncertainty'] = True
        else:
            details['uncertainty'] = False
        # Depth (mocked as always deep)
        score += 5
        details['depth'] = True
        # Hallucination (mocked as no hallucination)
        details['hallucination'] = False
        return score, details

    async def analyze(self, url: str) -> Tuple[float, str]:
        """
        Analyze AI presence of a company website.
        """
        # 1. Scrape facts
        company_facts = await self._scrape_company_facts(url)
        print(company_facts)
        # 2. Query LLMs (mocked)
        llm_responses = await self._query_llms(company_facts)
        print(llm_responses)
        # 3. Score each response
        scores = {}
        details = {}
        for model, response in llm_responses.items():
            score, detail = self._score_llm_response(company_facts, response)
            scores[model] = score
            details[model] = detail
        # 4. Aggregate
        avg_score = sum(scores.values()) / len(scores)
        summary = (
            f"AI Presence Analysis (mocked):\n"
            f"OpenAI: {scores['openai']}\n"
            f"Anthropic: {scores['anthropic']}\n"
            f"Gemini: {scores['gemini']}\n"
            f"Average: {avg_score:.2f}"
        )
        return avg_score, summary 