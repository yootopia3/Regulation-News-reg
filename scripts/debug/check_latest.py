from src.db.client import supabase

# Check latest articles
r = supabase.table('articles').select('published_at, agency, title').order('published_at', desc=True).limit(5).execute()

print("=== Latest 5 Articles ===")
for a in r.data:
    print(f"{a['agency']}: {a['published_at'][:10]} - {a['title'][:40]}...")
