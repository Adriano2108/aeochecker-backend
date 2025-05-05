import asyncio
from app.services.analysis.competitor_landscape import CompetitorLandscapeAnalyzer
from app.services.analysis.ai_presence import AiPresenceAnalyzer
from app.services.analysis.strategy_review import StrategyReviewAnalyzer
import json
from app.services.analysis.scrape_utils import scrape_website, _validate_and_get_best_url

async def main():
    url = "https://pickpocketalert.com/"
    validated_url = await _validate_and_get_best_url(url)

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

    soup, all_text = await scrape_website(validated_url)

    # accessibility_score, accessibility_results = await strategy_review_analyzer._analyze_crawler_accessibility(validated_url, soup)
    # print("Accessibility Score:", accessibility_score)
    # print("Accessibility Results:", json.dumps(accessibility_results, indent=4))

    score, strategy_review_result = await strategy_review_analyzer.analyze(dummy_company_facts["name"], validated_url, soup, all_text)
    print("Strategy Review Score:", score)
    print("Strategy Review Results:", json.dumps(strategy_review_result, indent=4))

if __name__ == "__main__":
    asyncio.run(main())