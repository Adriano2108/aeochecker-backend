import asyncio
from app.services.analysis.ai_presence import AiPresenceAnalyzer

async def main():
    url = "https://aeochecker.ai/"
    analyzer = AiPresenceAnalyzer()
    # Directly test _scrape_company_facts
    facts = await analyzer._scrape_company_facts(url)
    print("Scraped facts:", facts)
    # Or test the full analyze method
    # score, summary = await analyzer.analyze(url)
    # print("Score:", score)
    # print("Summary:", summary)

if __name__ == "__main__":
    asyncio.run(main())