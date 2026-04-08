import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(URL, KEY)

# Search for specific articles
keywords = ['다크패턴', '통화신용정책']

for kw in keywords:
    res = supabase.table("articles") \
        .select("id, title, published_at, created_at, agency") \
        .ilike("title", f"%{kw}%") \
        .execute()
    
    print(f"\n=== Search: {kw} ===")
    for item in res.data:
        print(f"ID: {item['id']}")
        print(f"Title: {item['title'][:60]}...")
        print(f"published_at: {item['published_at']}")
        print(f"created_at: {item['created_at']}")
        print(f"agency: {item['agency']}")
        print("-" * 40)
