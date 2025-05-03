"""
AI Presence Analyzer module.
This module contains functionality to check how well large language models know about a company.
"""

import httpx
from bs4 import BeautifulSoup
import json
from typing import Dict, Any, Tuple
import asyncio
import re
from urllib.parse import urljoin, urlparse

from app.services.analysis.base import BaseAnalyzer
from app.core.config import settings

import openai
from anthropic import AsyncAnthropic
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

class AiPresenceAnalyzer(BaseAnalyzer):
    """Analyzer for checking AI presence of a company (how well AI models know about it)."""
    
    @staticmethod
    async def _scrape_company_facts(url: str) -> dict:
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
            url = alt_url

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
          tasks.append(AiPresenceAnalyzer._query_openai(prompt))
        else:
          responses["openai"] = "API key not configured"
            
        if settings.ANTHROPIC_API_KEY:
          tasks.append(AiPresenceAnalyzer._query_anthropic(prompt))
        else:
          responses["anthropic"] = "API key not configured"
            
        if settings.GEMINI_API_KEY:
          tasks.append(AiPresenceAnalyzer._query_gemini(prompt))
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
    async def _query_openai(prompt: str) -> Tuple[str, str]:
        """Query OpenAI API and return the response."""
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = await client.responses.create(
                model="gpt-4.1-mini-2025-04-14",
                tools=[{ 
                  "type": "web_search_preview",
                  "search_context_size": "low",
                }],
                input=prompt,
            )
            return "openai", response.output_text
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    @staticmethod
    async def _query_anthropic(prompt: str) -> Tuple[str, str]:
        """Query Anthropic API and return the response."""
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        try:
            response = await client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=150,
                system="You are a helpful assistant that provides factual information about companies. Please do not invent facts, you are allowed to say you don't know.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return "anthropic", response.content[0].text
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
    @staticmethod
    async def _query_gemini(prompt: str) -> Tuple[str, str]:
        """Query Google Gemini API and return the response."""
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            google_search_tool = Tool(
               google_search = GoogleSearch()
            )
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=GenerateContentConfig(
                   tools=[google_search_tool],
                   response_modalities=["TEXT"],
                )
            )
            return "gemini", response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

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

    async def analyze(self, url: str) -> Tuple[float, str]:
        """
        Analyze AI presence of a company website.
        """
        # 1. Scrape facts
        company_facts = await self._scrape_company_facts(url)

        if company_facts["name"] == "":
          return 0, "No information found about your website. You need to add name tags, meta tags, and other basic structured data to your website to run this analysis."
        
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
        return avg_score, summary 