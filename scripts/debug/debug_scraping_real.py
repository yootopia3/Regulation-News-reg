import logging
import json
import os
from src.collectors.scraper import ContentScraper

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scraper():
    # Load Config
    with open('config/agencies.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    agencies = {a['code']: a for a in config['agencies']}
    scraper = ContentScraper()

    # Test BOK
    print("\n--- Testing BOK ---")
    bok_config = agencies.get('BOK')
    if bok_config:
        print(f"URL: {bok_config['url']}")
        items = scraper.fetch_list_items(bok_config)
        print(f"Found {len(items)} items.")
        if items:
            print(f"First item: {items[0]}")
            # Try fetching content for first item
            print("Fetching content for first item...")
            content = scraper.fetch_content(items[0]['link'], bok_config)
            print(f"Content Length: {len(content) if content else 0}")
            print(f"Content Preview: {content[:100] if content else 'None'}")
    else:
        print("BOK config not found")

if __name__ == "__main__":
    test_scraper()
