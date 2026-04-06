from src.collectors.scraper import ContentScraper
import json
import os

scraper = ContentScraper()

# Load config
with open("config/agencies.json", "r", encoding="utf-8") as f:
    config = json.load(f)

targets = [a for a in config['agencies'] if a['id'] in ['FSS', 'BOK']]

print("=== Testing HTML List Scraping ===")
for agency in targets:
    print(f"\n[{agency['id']}] Scraping list from {agency.get('source_url')}...")
    items = scraper.fetch_list_items(agency)
    print(f"  Found {len(items)} items")
    if items:
        print(f"  First item: {items[0]}")
