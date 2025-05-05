import asyncio
from app.services.analysis.competitor_landscape import CompetitorLandscapeAnalyzer
from app.services.analysis.ai_presence import AiPresenceAnalyzer
from app.services.analysis.strategy_review import StrategyReviewAnalyzer
import json
from app.services.analysis.scrape_utils import scrape_website

async def main():
    url = "https://www.pickpocketalert.com/"

    ai_presence_analyzer = AiPresenceAnalyzer()
    competitor_landscape_analyzer = CompetitorLandscapeAnalyzer()
    strategy_review_analyzer = StrategyReviewAnalyzer()

    dummy_company_facts = {
        'name': 'Pickpocket Alert', 
        'industry': 'Anti - Pickpocket', 
        'key_products_services': ['App'], 
        'founded': '', 
        'hq': '', 
        'description': 'Stay safe from pickpockets around you with real-time alerts and community-driven advice.'
    }

    soup, all_text = await scrape_website(url)

    # score, strategy_review_result = await strategy_review_analyzer.analyze(url, soup, all_text)
    # score, kb_results = await strategy_review_analyzer._analyze_knowledge_base_presence("Github")

    # Test the structured data analysis
    score, structured_data_results = strategy_review_analyzer._analyze_structured_data(soup)
    print("Structured Data Score:", score)
    print("Structured Data Results:", json.dumps(structured_data_results, indent=4))
    

if __name__ == "__main__":
    asyncio.run(main())