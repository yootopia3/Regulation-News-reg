import sys
sys.path.append('.')
from src.pipeline import Pipeline

print('Re-collecting sanction notices with correct dates...')
pipeline = Pipeline('config/agencies.json')

sanction_codes = ['FSS_SANCTION', 'FSS_MGMT_NOTICE']
for code in sanction_codes:
    if code in pipeline.agency_map:
        agency = pipeline.agency_map[code]
        print(f'Collecting {code}...')
        items = pipeline.scraper.fetch_sanction_items(agency)
        print(f'  Found {len(items)} items')
        
        # Show date samples
        for item in items[:3]:
            title = item.get('title', '')[:20]
            pub = item.get('published_at', '')
            print(f'    Sample: {title}... | {pub}')
        
        for item in items:
            pipeline._process_single_item(item)
        print(f'  Saved to DB')

print('Done!')
