import asyncio
from app.services.analysis.ai_presence import AiPresenceAnalyzer
import json
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

async def main():
    url = "https://www.pickpocketalert.com/"
    analyzer = AiPresenceAnalyzer()

    score, details = await analyzer.analyze(url)
    print("Score:", score)
    print("Details:", json.dumps(details, indent=4))

if __name__ == "__main__":
    asyncio.run(main())