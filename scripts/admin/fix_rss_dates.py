
import os
import sys
import json
import logging
from dotenv import load_dotenv

# Path setup
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Load env
load_dotenv(os.path.join(project_root, 'web', '.env.local'))

from src.collectors.rss_parser import fetch_rss_feed
from src.utils.logger import setup_logger
from supabase import create_client

logger = setup_logger("FixRSS")

def fix_rss_dates():
    # 1. Init DB
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL_V2") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY_V2") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        logger.error("Missing Supabase credentials")
        return

    supabase = create_client(url, key)

    # 2. Load Config
    config_path = os.path.join(project_root, 'config', 'agencies.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 3. Target Agencies (RSS only)
    targets = [a for a in config['agencies'] if a.get('collection_method') == 'rss']
    
    logger.info(f"Targets to fix: {[t['code'] for t in targets]}")

    for agency in targets:
        logger.info(f"Fetching correct data for {agency['code']}...")
        try:
            # Fetch using the ROBUST parser
            items = fetch_rss_feed(agency)
            logger.info(f"  > Got {len(items)} items from RSS.")
            
            updated_count = 0
            for item in items:
                link = item['link']
                real_date = item['published_at']
                
                # UPDATE published_at only (preserve analysis)
                try:
                    res = supabase.table('articles').update({
                        'published_at': real_date
                    }).eq('link', link).execute()
                    
                    if res.data:
                        updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update {link}: {e}")
            
            logger.info(f"  > Fixed {updated_count} records for {agency['code']}.")
            
        except Exception as e:
            logger.error(f"Error processing {agency['code']}: {e}")

if __name__ == "__main__":
    fix_rss_dates()
