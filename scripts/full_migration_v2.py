
import os
import sys
import time
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

V1_URL = os.getenv("SUPABASE_URL")
V1_KEY = os.getenv("SUPABASE_ANON_KEY")
V2_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL_V2")
V2_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY_V2")

if not V1_URL or not V1_KEY or not V2_URL or not V2_KEY:
    print("Error: Missing env vars.")
    sys.exit(1)

v1 = create_client(V1_URL, V1_KEY)
v2 = create_client(V2_URL, V2_KEY)

def clean_row(row):
    """Prepare row for v2 insertion"""
    # Ensure v2 columns
    if 'view_count' not in row: row['view_count'] = 0
    if 'star_rating' not in row: row['star_rating'] = None
    if 'is_trending' not in row: row['is_trending'] = False
    return row

def full_migration():
    print("=== Starting FULL Migration (v1 -> v2) ===")
    
    BATCH_SIZE = 1000
    start = 0
    total_migrated = 0
    
    while True:
        print(f"Fetching rows {start} to {start + BATCH_SIZE - 1} from v1...")
        try:
            # Fetch from v1
            res = v1.table('articles')\
                .select('*')\
                .order('published_at', desc=True)\
                .range(start, start + BATCH_SIZE - 1)\
                .execute()
            
            rows = res.data
            if not rows:
                print("No more rows found based on range.")
                break
                
            print(f"Fetched {len(rows)} rows. Preparing insert...")
            
            # Prepare for v2
            v2_rows = [clean_row(r) for r in rows]
            
            # Insert to v2 (Upsert to prevent duplicates)
            v2.table('articles').upsert(v2_rows).execute()
            
            count = len(rows)
            total_migrated += count
            print(f"✅ Migrated {count} rows (Total: {total_migrated})")
            
            if count < BATCH_SIZE:
                print("End of table reached.")
                break
                
            start += BATCH_SIZE
            time.sleep(1) # Gentle rate limit
            
        except Exception as e:
            print(f"❌ Error during migration batch {start}: {e}")
            break

    print(f"=== Migration Complete. Total: {total_migrated} articles. ===")

if __name__ == "__main__":
    full_migration()
