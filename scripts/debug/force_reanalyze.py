import json
import logging
from src.db.client import supabase
from src.services.analyzer import HybridAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForceReanalyze")

def force_reanalyze_latest():
    # 1. Fetch latest article (BOK or any)
    res = supabase.table('articles').select('*').order('published_at', desc=True).limit(1).execute()
    
    if not res.data:
        logger.error("No articles found in DB.")
        return

    article = res.data[0]
    logger.info(f"Re-analyzing: {article['title']} ({article['agency']})")

    # 2. Analyze with NEW Prompt
    analyzer = HybridAnalyzer()
    
    # Force analyze call directly
    # Need to simulate 'agency_name' for prompt
    # In main flow, agency_name comes from config map.
    # Let's map agency code to new name manually here or load from config
    import json
    with open('config/agencies.json', 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        agency_map = { a['code']: a['name'] for a in config_data['agencies'] }
    
    agency_name = agency_map.get(article['agency'], article['agency'])
    
    analysis_result = analyzer.analyze(article['title'], article['content'], agency_name)

    if analysis_result:
        analysis_result['analysis_status'] = 'ANALYZED'
        # 3. Update DB
        logger.info("Analysis complete. Updating DB...")
        supabase.table('articles').update({'analysis_result': analysis_result}).eq('id', article['id']).execute()
        logger.info("Done! Refresh the dashboard.")
        
        # Print new result for verification
        print("\n--- New Analysis Result ---")
        print(f"Summary: {analysis_result.get('summary')}")
        print(f"Impact: {analysis_result.get('impact_analysis')}")
    else:
        logger.error("Re-analysis failed.")

if __name__ == "__main__":
    force_reanalyze_latest()
