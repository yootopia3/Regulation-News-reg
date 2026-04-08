import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")

print(f"URL: {url}")
print(f"Key: {key[:20]}...")

supabase = create_client(url, key)

# Check if articles exist
try:
    result = supabase.table("articles").select("id, agency, title, published_at").order("published_at", desc=True).limit(5).execute()
    print(f"\n--- Query Result ({len(result.data)} rows) ---")
    if result.data:
        for row in result.data:
            print(f"[{row['agency']}] {row['published_at']} | {row['title'][:40]}...")
    else:
        print("No articles in DB!")
except Exception as e:
    print(f"ERROR: {e}")
