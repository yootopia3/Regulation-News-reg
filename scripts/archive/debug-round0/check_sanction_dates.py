import sys
sys.path.append('.')
from src.collectors.scraper import ContentScraper
import json

with open('config/agencies.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

scraper = ContentScraper()

for agency in config['agencies']:
    if agency['code'] == 'FSS_SANCTION':
        items = scraper.fetch_sanction_items(agency)
        print(f'FSS_SANCTION: {len(items)} items')
        for item in items[:5]:
            title = item.get('title', '')
            pub = item.get('published_at', '')
            print(f'  {title} | {pub}')
        break
