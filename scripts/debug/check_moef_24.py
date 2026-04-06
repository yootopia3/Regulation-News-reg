
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(URL, KEY)

# 12월 24일자 MOEF 기사 조회
res = supabase.table("articles").select("title, published_at, analysis_result").eq("agency", "MOEF").gte("published_at", "2025-12-24").execute()

print(f"Found {len(res.data)} MOEF articles on Dec 24+:\n")
for item in res.data:
    result = item.get('analysis_result', {}) or {}
    score = result.get('importance_score', 'N/A')
    risk = result.get('risk_level', 'N/A')
    print(f"Score: {score} | Title: {item['title'][:50]}...")
