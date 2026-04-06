
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.collectors.scraper import ContentScraper
import json

# Load BOK config
with open('config/agencies.json', 'r', encoding='utf-8') as f:
    agencies = json.load(f)['agencies']

bok_config = next(a for a in agencies if a['code'] == 'BOK')

print("=== BOK Scraper Test ===")
print(f"URL: {bok_config['url']}")
print(f"Selector: {bok_config['selector']}")
print()

scraper = ContentScraper()

# Test with no last_crawled_date (full 7-day scan)
items = scraper.fetch_list_items(bok_config, last_crawled_date=None)

print(f"\n=== Result: {len(items)} items collected ===")
if items:
    for item in items[:5]:
        print(f"  - {item['published_at'][:10]}: {item['title'][:50]}...")
else:
    print("No items collected!")
