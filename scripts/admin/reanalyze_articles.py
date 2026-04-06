import sys
import os
import json
import logging
import asyncio
from typing import List

# Setup path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.db.client import supabase
from src.services.analyzer import HybridAnalyzer
from config.settings import MODEL_ANALYZER_ID, MODEL_ANALYZER_FALLBACK
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def reanalyze_all():
    # API Keys loaded by load_dotenv() above
    
    analyzer = HybridAnalyzer()
    
    logger.info("Fetching all articles for re-analysis...")
    
    # 1. Fetch all articles (simple pagination or fetch all if count is manageable)
    # Using fetch all for now (assuming < 1000 articles for 1 month)
    # If huge, need cursor pagination.
    
    # We select ID, Title, Content, Agency to re-analyze
    res = supabase.table('articles').select('id, title, content, agency').execute()
    articles = res.data
    
    if not articles:
        logger.info("No articles found.")
        return

    logger.info(f"Found {len(articles)} articles. Starting re-analysis...")

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for idx, article in enumerate(articles):
        try:
            # Skip if content is empty
            if not article.get('content'):
                continue

            logger.info(f"[{idx+1}/{len(articles)}] Re-analyzing: {article['title'][:30]}...")

            # 2. Re-run Analysis using process() which handles Filter -> Analyze pipeline
            result = analyzer.process(article, article['agency'])
            
            if result:
                # 3. Update DB (updated_at removed as column likely missing)
                update_data = {
                    "analysis_result": result
                }
                
                supabase.table('articles').update(update_data).eq('id', article['id']).execute()
                updated_count += 1
                
                # Log status
                risk = result.get('risk_level', 'Low')
                logger.info(f"  -> Updated. Risk: {risk}, Status: {result.get('analysis_status', 'OK')}")
            else:
                logger.warning("  -> Analysis returned None.")
                error_count += 1
                
        except Exception as e:
            logger.error(f"Error re-analyzing article {article['id']}: {e}")
            error_count += 1
            
        # Rate limit friendly sleep
        await asyncio.sleep(1.0) 

    logger.info("=== Re-analysis Complete ===")
    logger.info(f"Total: {len(articles)}")
    logger.info(f"Updated: {updated_count}")
    logger.info(f"Errors: {error_count}")

if __name__ == "__main__":
    asyncio.run(reanalyze_all())
