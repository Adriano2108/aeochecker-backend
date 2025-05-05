from app.core.config import settings

async def query_openai(prompt: str):
    import openai
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.responses.create(
        model="gpt-4.1-mini-2025-04-14",
        tools=[{"type": "web_search_preview", "search_context_size": "low"}],
        input=prompt,
    )
    return "openai", response.output_text

async def query_anthropic(prompt: str):
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=150,
        system="You are a helpful assistant that provides factual information about companies. Please do not invent facts, you are allowed to say you don't know.",
        messages=[{"role": "user", "content": prompt}]
    )
    return "anthropic", response.content[0].text

async def query_gemini(prompt: str):
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
        )
    )
    return "gemini", response.text 