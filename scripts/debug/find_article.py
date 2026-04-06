
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_ANON_KEY")

if not URL or not KEY:
    print("Error: Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    exit(1)

supabase: Client = create_client(URL, KEY)

def search_article(keyword):
    print(f"\nSearching for keyword: '{keyword}'...")
    try:
        # Search in title
        res = supabase.table("articles").select("*").ilike("title", f"%{keyword}%").execute()
        
        if not res.data:
            print("No articles found.")
            return

        print(f"Found {len(res.data)} articles:")
        for item in res.data:
            result = item.get('analysis_result', {}) or {}
            score = result.get('importance_score')
            print(f"  > Title: {item['title'][:30]}...")
            print(f"  > Score: {score} (Type: {type(score)})")
            import json
            # print(f"  > Full Analysis: {json.dumps(result, ensure_ascii=False)[:300]}...") 
            print("-" * 40)
            
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    # 사용자가 언급한 주요 키워드로 검색
    search_article("자본시장")
    search_article("세제지원")
    search_article("외환시장")
