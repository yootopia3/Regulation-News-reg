import os
from dotenv import load_dotenv
from supabase import create_client

# Load env
load_dotenv('web/.env.local')
url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL_V2')
# Use Service Role Key if available, otherwise Anon Key
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2')

sb = create_client(url, key)

print("--- Check Items ---")
# Check sanction notices for 22, 23, 24
res = sb.table('articles').select('id, title, published_at').in_('agency', ['FSS_SANCTION', 'FSS_MGMT_NOTICE']).order('published_at', desc=True).limit(50).execute()

target_ids = []
for item in res.data:
    pub = item.get('published_at', '')
    # Check if date string contains 12-22, 12-23, or 12-24
    if '2025-12-22' in pub or '2025-12-23' in pub or '2025-12-24' in pub:
        print(f"TARGET: {item['title'][:30]}... | {pub} | ID: {item['id']}")
        target_ids.append(item['id'])

print(f"\nFound {len(target_ids)} items to delete.")

if target_ids:
    print("Deleting...")
    delete_res = sb.table('articles').delete().in_('id', target_ids).execute()
    print(f"Deleted {len(delete_res.data) if delete_res.data else 0} items.")
else:
    print("No items found for target dates.")
