"""
Reanalyze articles with NULL analysis_result.
This script ONLY updates analysis_result for articles that have NULL.
It does NOT touch any other fields or articles.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Path setup
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Load env
load_dotenv(os.path.join(project_root, 'web', '.env.local'))
load_dotenv(os.path.join(project_root, '.env'))

from supabase import create_client
from src.services.analyzer import HybridAnalyzer
from src.utils.logger import setup_logger

logger = setup_logger("ReanalyzeNull")

def reanalyze_null_articles(agency_filter=None, dry_run=False):
    """
    Find and reanalyze articles with NULL analysis_result.
    
    Args:
        agency_filter: Optional agency code to filter (e.g., 'MOEF')
        dry_run: If True, only print what would be done without actually updating
    """
    # Init DB
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL_V2") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY_V2") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        logger.error("Missing Supabase credentials")
        return

    supabase = create_client(url, key)
    
    # Init Analyzer (uses existing production logic)
    try:
        analyzer = HybridAnalyzer()
        logger.info("Analyzer initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to init Analyzer: {e}")
        return

    # Query articles with NULL analysis_result
    query = supabase.table('articles').select('id, title, content, agency, category, link').is_('analysis_result', 'null')
    
    if agency_filter:
        query = query.eq('agency', agency_filter)
        logger.info(f"Filtering by agency: {agency_filter}")
    
    res = query.order('created_at', desc=True).limit(100).execute()
    
    articles = res.data
    logger.info(f"Found {len(articles)} articles with NULL analysis_result.")
    
    if dry_run:
        logger.info("=== DRY RUN MODE - No changes will be made ===")
        for article in articles:
            logger.info(f"  Would reanalyze: [{article['agency']}] {article['title'][:50]}...")
        return
    
    # Reanalyze each article
    success_count = 0
    for i, article in enumerate(articles):
        logger.info(f"[{i+1}/{len(articles)}] Analyzing: {article['title'][:40]}...")
        
        try:
            # Call the existing analyzer logic
            analysis = analyzer.process(
                {'title': article['title'], 'content': article.get('content') or ''},
                article['agency'],
                category=article.get('category', 'press_release')
            )
            
            if analysis:
                # Update ONLY the analysis_result field
                supabase.table('articles').update({
                    'analysis_result': analysis
                }).eq('id', article['id']).execute()
                
                logger.info(f"  -> Success (Score: {analysis.get('importance_score')}, Status: {analysis.get('analysis_status')})")
                success_count += 1
            else:
                logger.warning(f"  -> Analyzer returned None")
                
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"  -> Failed: {e}")
    
    logger.info(f"Completed. Successfully reanalyzed {success_count}/{len(articles)} articles.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Reanalyze articles with NULL analysis_result')
    parser.add_argument('--agency', type=str, help='Filter by agency code (e.g., MOEF)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be done without executing')
    
    args = parser.parse_args()
    
    reanalyze_null_articles(agency_filter=args.agency, dry_run=args.dry_run)
