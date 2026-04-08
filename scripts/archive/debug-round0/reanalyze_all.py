"""
Re-analyze all articles with 2-Tier Hybrid Analyzer.
"""

import os
import time
import logging
from dotenv import load_dotenv
from supabase import create_client
from src.services.analyzer import HybridAnalyzer
from src.collectors.rss_parser import load_agencies

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(url, key)
analyzer = HybridAnalyzer()
agencies = load_agencies()
agency_map = {a['id']: a for a in agencies}


def reanalyze():
    logger.info("Fetching articles...")
    response = supabase.table("articles").select("*").execute()
    articles = response.data
    
    logger.info(f"Found {len(articles)} articles. Starting 2-tier re-analysis...")
    
    analyzed_count = 0
    filtered_count = 0
    error_count = 0
    
    for i, article in enumerate(articles, 1):
        logger.info(f"[{i}/{len(articles)}] Processing: {article['title'][:40]}...")
        
        agency_id = article['agency']
        agency_config = agency_map.get(agency_id)
        agency_name = agency_config['name'] if agency_config else agency_id
        
        # Use the new process() method
        result = analyzer.process(article, agency_name)
        
        if result:
            # Update DB with combined filter + analysis result
            try:
                supabase.table("articles").update({
                    "analysis_result": result
                }).eq("id", article['id']).execute()
                
                if result.get('analysis_status') == 'ANALYZED':
                    analyzed_count += 1
                elif result.get('analysis_status') == 'SKIPPED':
                    filtered_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"DB Update Error: {e}")
                error_count += 1
        else:
            error_count += 1
    
    logger.info("=" * 50)
    logger.info(f"Re-analysis complete!")
    logger.info(f"  - Tier 2 Analyzed: {analyzed_count}")
    logger.info(f"  - Tier 1 Filtered (Skipped): {filtered_count}")
    logger.info(f"  - Errors: {error_count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    reanalyze()
