
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.pipeline import Pipeline

# Initialize pipeline
pipeline = Pipeline('config/agencies.json')

# Check BOK config
bok_config = pipeline.agency_map.get('BOK')
print("=== BOK Config ===")
print(f"Code: {bok_config.get('code')}")
print(f"Method: {bok_config.get('collection_method')}")
print(f"URL: {bok_config.get('url')}")

# Get last crawled date
last_date = pipeline._get_last_crawled_date('BOK')
print(f"\n=== Last Crawled Date ===")
print(f"BOK last date: {last_date}")

# Collect BOK items
print(f"\n=== Collecting BOK ===")
scraped_items = pipeline.scraper.fetch_list_items(bok_config, last_crawled_date=last_date)
print(f"Collected {len(scraped_items)} items")

if scraped_items:
    print("\nFirst 5 items:")
    for i, item in enumerate(scraped_items[:5]):
        print(f"  {i+1}. {item['title'][:50]}... | {item['published_at'][:10]}")
    
    # Check if these would be duplicates
    print("\n=== Duplicate Check ===")
    dupe_count = 0
    for item in scraped_items[:10]:
        is_dupe = pipeline._is_duplicate(item['link'])
        if is_dupe:
            dupe_count += 1
            print(f"  DUPE: {item['title'][:40]}...")
    print(f"Duplicates in first 10: {dupe_count}")
else:
    print("No items collected!")
