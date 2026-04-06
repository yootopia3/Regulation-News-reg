import os
from dotenv import load_dotenv
from supabase import create_client

# Load envs
load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_ANON_KEY")

if not URL or not KEY:
    print("Error: Missing credentials")
    exit(1)

supabase = create_client(URL, KEY)

# Query all articles from Dec 24, 2025 (KST)
# Note: DB is UTC-ish or correct offset? Code typically uses +09:00.
# We'll just check >= 2025-12-23 to be safe and filter in python if needed, 
# but user specifically said "24th". Let's query >= '2025-12-23T15:00:00' (which is Dec 24 00:00 KST)

target_date_iso = "2025-12-23T15:00:00+00:00" 

print(f"Querying articles since {target_date_iso} (KST 24th)...")

res = supabase.table("articles") \
    .select("id, title, agency, published_at, analysis_result") \
    .gte("published_at", target_date_iso) \
    .order("published_at", desc=True) \
    .execute()

articles = res.data
print(f"Total found: {len(articles)}")

missing_analysis = 0
low_score = 0
analyzed = 0

for a in articles:
    res = a.get('analysis_result')
    pub = a.get('published_at')
    title = a.get('title')
    
    if not res:
        print(f"[MISSING] {pub} | {title} (No Analysis Result)")
        missing_analysis += 1
    else:
        score = res.get('importance_score')
        rel = res.get('is_relevant')
        
        if score is None:
            print(f"[NULL SCORE] {pub} | {title} | Res: {res}")
        else:
            print(f"[SCORE {score}] {pub} | {title} (Rel: {rel})")
            if score < 3:
                low_score += 1
            else:
                analyzed += 1

print("-" * 30)
print(f"Summary for Dec 24th:")
print(f"Total: {len(articles)}")
print(f"Missing Analysis (NULL): {missing_analysis}")
print(f"Low Score (<3): {low_score}")
print(f"Analyzed (3+): {analyzed}")
