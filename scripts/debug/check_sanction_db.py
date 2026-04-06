import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('web/.env.local')
url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL_V2')
key = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2')
sb = create_client(url, key)

# Check sanction notices
res = sb.table('articles').select('agency, title, published_at').in_('agency', ['FSS_SANCTION', 'FSS_MGMT_NOTICE']).order('published_at', desc=True).limit(10).execute()

print(f'Sanction notices in DB: {len(res.data)}')
for r in res.data:
    agency = r.get('agency', '')
    title = r.get('title', '')[:30]
    pub = r.get('published_at', '')[:10]
    print(f'  [{agency}] {title}... ({pub})')
