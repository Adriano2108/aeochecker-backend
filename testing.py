import json
import asyncio
import datetime
from app.services.analysis.competitor_landscape import CompetitorLandscapeAnalyzer
from app.services.analysis.ai_presence import AiPresenceAnalyzer
from app.services.analysis.strategy_review import StrategyReviewAnalyzer
from app.services.analysis.utils.response import generate_analysis_synthesis
from app.services.analysis.utils.scrape_utils import scrape_website, _validate_and_get_best_url, scrape_company_facts
from app.services import AnalysisService

async def main():
    url = "https://www.nationalityguesser.com/"
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
    company_facts = await scrape_company_facts(validated_url, soup, all_text)
    ai_presence_score, ai_presence_result = await ai_presence_analyzer.analyze(company_facts)
    print(company_facts)
    print(ai_presence_score)
    print(json.dumps(ai_presence_result, indent=4))

    # accessibility_score, accessibility_results = await strategy_review_analyzer._analyze_crawler_accessibility(validated_url, soup)
    # print("Accessibility Score:", accessibility_score)
    # print("Accessibility Results:", json.dumps(accessibility_results, indent=4))

    # score, strategy_review_result = await strategy_review_analyzer.analyze(dummy_company_facts["name"], validated_url, soup, all_text)
    # print("Strategy Review Score:", score)
    # print("Strategy Review Results:", json.dumps(strategy_review_result, indent=4))

    # result = await AnalysisService.analyze_website(validated_url, "test_user")

    # Custom function to handle non-serializable types
    # def json_serial(obj):
    #     """JSON serializer for objects not serializable by default json code"""
    #     if isinstance(obj, datetime.datetime):
    #         return obj.isoformat()
    #     raise TypeError(f"Type {type(obj)} not serializable")

    # print("Results:", json.dumps(result, indent=4, default=json_serial))

if __name__ == "__main__":
    asyncio.run(main())