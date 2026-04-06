
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))

# FSS 최신 기사 조회
res = supabase.table('articles').select('title, published_at, analysis_result').eq('agency', 'FSS').order('published_at', desc=True).limit(15).execute()

print(f'FSS 기사 {len(res.data)}건 (최신 15개):')
for item in res.data:
    result = item.get('analysis_result', {}) or {}
    score = result.get('importance_score', 'N/A')
    pub = item['published_at'][:10]
    title = item['title'][:50]
    print(f'Score: {score} | Date: {pub} | {title}...')
