
import os
import sys
import json
from dotenv import load_dotenv
from supabase import create_client

# Load env variables
load_dotenv('web/.env.local')

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL_V2") or os.environ.get("SUPABASE_URL")
key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY_V2") or os.environ.get("SUPABASE_ANON_KEY")

if not url or not key:
    print("Error: Supabase credentials not found.")
    sys.exit(1)

supabase = create_client(url, key)

def inspect_moef_analysis():
    print("=== Inspecting MOEF (2026-01-05 / Actual 2025-12-XX) ===")
    
    # Fetch recent MOEF articles
    # Since dates might be fixed now (to Dec), let's just fetch latest 20 MOEF articles by ID or CreatedAt if possible
    # Or just fetch by agency 'MOEF' order by published_at desc
    
    res = supabase.table('articles')\
        .select('*')\
        .eq('agency', 'MOEF')\
        .order('published_at', desc=True)\
        .limit(10)\
        .execute()
        
    for item in res.data:
        print(f"\n[ID: {item['id']}] {item['title']}")
        print(f"  Date: {item['published_at']}")
        analysis = item.get('analysis_result')
        
        if not analysis:
            print("  -> Analysis: NONE (Null)")
            continue
            
        print(f"  -> Filter Status: {analysis.get('filter_status')}")
        print(f"  -> Relevance: {analysis.get('is_relevant')}")
        print(f"  -> Score: {analysis.get('importance_score')} (Risk Score: {analysis.get('risk_score')})")
        print(f"  -> Analysis Status: {analysis.get('analysis_status')}")
        
        if analysis.get('analysis_status') == 'ANALYZED':
            summary = analysis.get('summary')
            if summary:
                print(f"  -> Summary: Found ({len(summary)} points)")
            else:
                print("  -> Summary: MISSING (but status is analyzed)")
        elif analysis.get('analysis_status') == 'SKIPPED':
            print("  -> Reason: Skipped due to low score")
        elif analysis.get('analysis_status') == 'ANALYSIS_FAILED':
            print("  -> Reason: Analysis FAILED (API Error likely)")

if __name__ == "__main__":
    inspect_moef_analysis()
