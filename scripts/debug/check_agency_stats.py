import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(url, key)

response = supabase.table("articles").select("agency, analysis_result").execute()

stats = {}
for a in response.data:
    agency = a['agency']
    if agency not in stats:
        stats[agency] = {"total": 0, "analyzed": 0, "skipped": 0}
    
    stats[agency]["total"] += 1
    status = a.get('analysis_result', {}).get('analysis_status')
    if status == 'ANALYZED':
        stats[agency]["analyzed"] += 1
    elif status == 'SKIPPED':
        stats[agency]["skipped"] += 1

import json
with open("agency_stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f)
print("Stats saved to agency_stats.json")
