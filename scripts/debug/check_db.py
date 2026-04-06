import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(url, key)

# Check a few articles
response = supabase.table("articles").select("title, analysis_result").limit(5).execute()

print("=== Sample Articles ===")
for a in response.data:
    print(f"\nTitle: {a['title'][:50]}...")
    print(f"Analysis Result: {a['analysis_result']}")
    
# Count by analysis_status
response_all = supabase.table("articles").select("analysis_result").execute()
analyzed = sum(1 for a in response_all.data if a.get('analysis_result', {}).get('analysis_status') == 'ANALYZED')
skipped = sum(1 for a in response_all.data if a.get('analysis_result', {}).get('analysis_status') == 'SKIPPED')
print(f"\n=== Counts ===")
print(f"ANALYZED: {analyzed}")
print(f"SKIPPED: {skipped}")
print(f"Total: {len(response_all.data)}")
