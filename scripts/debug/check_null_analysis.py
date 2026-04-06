
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('web/.env.local')
url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL_V2')
key = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2')
sb = create_client(url, key)

# Get MOEF articles with NULL analysis
res = sb.table('articles').select('title, created_at').eq('agency', 'MOEF').is_('analysis_result', 'null').order('created_at', desc=True).execute()

print('MOEF Articles with NULL analysis_result:')
print(f'Count: {len(res.data)}')
for r in res.data:
    created = str(r.get('created_at', 'N/A'))[:19]
    title = str(r.get('title', ''))[:40]
    print(f'  [{created}] {title}')
