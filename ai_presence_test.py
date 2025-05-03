import asyncio
from app.services.analysis.ai_presence import AiPresenceAnalyzer
import json
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

async def main():
    url = "https://www.pickpocketalert.com/"
    analyzer = AiPresenceAnalyzer()

    # facts = await analyzer._scrape_company_facts(url)
    # print("Scraped facts:", json.dumps(facts, indent=4))

    # if facts["name"] != "":
    #     llm_responses = await analyzer._query_llms(facts)
    #     print("LLM responses:", json.dumps(llm_responses, indent=4))

if __name__ == "__main__":
    asyncio.run(main())