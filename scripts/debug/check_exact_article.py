
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(URL, KEY)

# 정확한 기사 제목으로 검색
keyword = "자본시장 활성화"
res = supabase.table("articles").select("title, agency, published_at, analysis_result").ilike("title", f"%{keyword}%").execute()

print(f"Found {len(res.data)} articles matching '{keyword}':\n")
for item in res.data:
    result = item.get('analysis_result', {}) or {}
    score = result.get('importance_score', 'N/A')
    print(f"Agency: {item['agency']}")
    print(f"Published: {item['published_at']}")
    print(f"Score: {score}")
    print(f"Title: {item['title']}")
    print("-" * 50)
