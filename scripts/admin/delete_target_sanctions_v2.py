import os
from dotenv import load_dotenv
from supabase import create_client

# Load env
load_dotenv('web/.env.local')
url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL_V2')
# Use Service Role Key if available, otherwise Anon Key
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2')

sb = create_client(url, key)

print("--- Check Items (Wider Range) ---")
# Check sanction notices for wider range to catch UTC offsets
res = sb.table('articles').select('id, title, published_at').in_('agency', ['FSS_SANCTION', 'FSS_MGMT_NOTICE']).order('published_at', desc=True).limit(50).execute()

target_ids = []
for item in res.data:
    pub = item.get('published_at', '')
    title = item.get('title', '')
    
    # Just print everything first to see what dates we have
    print(f"ITEM: {title[:20]}... | {pub}")
    
    # Target specific dates (handling UTC offset)
    # If KST is Dec 22, 23, 24 -> UTC could be Dec 21 15:00 to Dec 24 14:59
    if '2025-12-21' in pub or '2025-12-22' in pub or '2025-12-23' in pub or '2025-12-24' in pub:
         # Double check titles to receive confirmation from user if needed, but for now add to target
         target_ids.append(item['id'])

print(f"\nFound {len(target_ids)} items in wider range.")

# UNCOMMENT TO ACTUALLY DELETE
if target_ids:
    print("Deleting identified items...")
    delete_res = sb.table('articles').delete().in_('id', target_ids).execute()
    print(f"Deleted {len(delete_res.data) if delete_res.data else 0} items.")
else:
    print("No items found.")
