"""Check FSS personnel articles in DB"""
from src.db.client import supabase

# Search for personnel-related articles
result = supabase.table('articles').select('id, title, published_at, analysis_result').eq('agency', 'FSS').ilike('title', '%인사%').order('published_at', desc=True).limit(10).execute()

print('=== FSS 인사 관련 기사 검색 ===')
print(f'검색 결과: {len(result.data)}건\n')
for article in result.data:
    print(f"{article['published_at'][:10]} | {article['title']}")

# Also search for 조직개편
result2 = supabase.table('articles').select('id, title, published_at').eq('agency', 'FSS').ilike('title', '%조직개편%').limit(10).execute()
print(f'\n=== FSS 조직개편 관련 기사 ===')
print(f'검색 결과: {len(result2.data)}건')
for article in result2.data:
    print(f"{article['published_at'][:10]} | {article['title']}")
    
# Search for 부서장
result3 = supabase.table('articles').select('id, title, published_at').eq('agency', 'FSS').ilike('title', '%부서장%').limit(10).execute()
print(f'\n=== FSS 부서장 관련 기사 ===')
print(f'검색 결과: {len(result3.data)}건')
for article in result3.data:
    print(f"{article['published_at'][:10]} | {article['title']}")
