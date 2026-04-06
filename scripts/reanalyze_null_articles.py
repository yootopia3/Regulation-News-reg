"""
Re-analyze articles with null analysis_result.
Run this script to fix articles that were saved without analysis due to errors.
"""
import os
import sys
import json
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web', '.env.local'))

# Set environment variables for V2 DB
os.environ['SUPABASE_URL'] = os.environ.get('NEXT_PUBLIC_SUPABASE_URL_V2', '')
os.environ['SUPABASE_ANON_KEY'] = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2', '')

from supabase import create_client
from src.services.analyzer import HybridAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Agency code to name mapping
AGENCY_NAMES = {
    'FSC': '금융위원회',
    'FSS': '금융감독원',
    'MOEF': '기획재정부',
    'BOK': '한국은행'
}

def main():
    # Initialize
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_ANON_KEY')
    
    if not url or not key:
        logger.error("Supabase credentials not found!")
        return
    
    supabase = create_client(url, key)
    analyzer = HybridAnalyzer()
    
    # Find articles with null analysis_result
    logger.info("Finding articles with null analysis_result...")
    
    response = supabase.table('articles').select('id, title, content, agency, link').is_('analysis_result', 'null').execute()
    
    articles = response.data
    logger.info(f"Found {len(articles)} articles to re-analyze")
    
    if not articles:
        logger.info("No articles need re-analysis!")
        return
    
    # Process each article
    success_count = 0
    fail_count = 0
    
    for i, article in enumerate(articles):
        title = article['title']
        content = article.get('content') or title
        agency_id = article['agency']
        agency_name = AGENCY_NAMES.get(agency_id, agency_id)
        
        logger.info(f"[{i+1}/{len(articles)}] Re-analyzing: [{agency_id}] {title[:50]}...")
        
        try:
            # Run analysis
            result = analyzer.process(
                {'title': title, 'content': content, 'description': content[:200]},
                agency_name
            )
            
            if result:
                # Update database
                supabase.table('articles').update({
                    'analysis_result': result
                }).eq('id', article['id']).execute()
                
                score = result.get('importance_score', 0)
                status = result.get('analysis_status', 'UNKNOWN')
                logger.info(f"  > Success! Score: {score}, Status: {status}")
                success_count += 1
            else:
                logger.warning(f"  > Analysis returned None")
                fail_count += 1
                
        except Exception as e:
            logger.error(f"  > Error: {e}")
            fail_count += 1
        
        # Rate limiting
        time.sleep(1)
    
    logger.info(f"\n=== Re-analysis Complete ===")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {fail_count}")

if __name__ == "__main__":
    main()
