from app.core.config import settings
import asyncio
import httpx
from typing import Tuple
import logging

# Configure logging
logger = logging.getLogger(__name__)

async def query_openai(prompt: str, temperature: float = 0.1):
    import openai
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.responses.create(
        model="gpt-4.1-mini-2025-04-14",
        tools=[{"type": "web_search_preview", "search_context_size": "low"}],
        input=prompt,
        temperature=temperature
    )
    return "openai", response.output_text

async def query_anthropic(prompt: str, temperature: float = 0.1) -> Tuple[str, str]:
    from anthropic import AsyncAnthropic
    
    # Configure client with explicit timeout and retry settings from config
    client = AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=httpx.Timeout(
            timeout=settings.LLM_TIMEOUT_SECONDS, 
            connect=settings.LLM_CONNECT_TIMEOUT_SECONDS
        ),
        max_retries=settings.LLM_MAX_RETRIES,
        default_headers={
            "anthropic-version": "2023-06-01",
            "User-Agent": "AEOChecker/1.0"
        }
    )
    
    max_attempts = settings.LLM_MAX_RETRIES
    base_delay = settings.LLM_RETRY_BASE_DELAY
    
    for attempt in range(max_attempts):
        try:
            response = await client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=150,
                system="You are a helpful assistant that provides factual information about companies. Please do not invent facts, you are allowed to say you don't know.",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return "anthropic", response.content[0].text
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a retryable error
            if any(keyword in error_str for keyword in [
                "connection error", "timeout", "connection refused", 
                "connection aborted", "connection reset", "network",
                "overloaded", "rate limit", "resource exhausted", "429"
            ]):
                if attempt < max_attempts - 1:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + (0.1 * attempt)
                    logger.warning(f"Anthropic API attempt {attempt + 1} failed with retryable error: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Anthropic API failed after {max_attempts} attempts: {e}")
                    raise Exception(f"Connection error after {max_attempts} retries: {e}")
            else:
                # Non-retryable error, fail immediately
                logger.error(f"Anthropic API non-retryable error: {e}")
                raise Exception(f"API error: {e}")
    
    # This should not be reached, but just in case
    raise Exception("Maximum retry attempts exceeded")

async def query_gemini(prompt: str, temperature: float = 0.1):
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    google_search_tool = Tool(google_search=GoogleSearch())
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            response_modalities=["TEXT"],
            temperature=temperature
        )
    )
    return "gemini", response.text

async def query_perplexity(prompt: str, temperature: float = 0.1):
    import httpx
    
    headers = {
        "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that provides factual information about companies. Please do not invent facts, you are allowed to say you don't know."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": 150
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        return "perplexity", result["choices"][0]["message"]["content"] 