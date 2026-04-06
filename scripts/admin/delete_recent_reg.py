
import os
import sys
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.db.client import supabase

def delete_recent_regulations():
    # Load Env
    load_dotenv()
    
    # Target Agencies
    targets = ['FSC_REG', 'FSS_REG', 'FSS_REG_INFO']
    
    # Calculate cutoff for 7 days ago
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    cutoff_date = now_kst - timedelta(days=7)
    cutoff_str = cutoff_date.isoformat()
    
    print(f"Deleting regulation articles ({targets}) published after {cutoff_str}...")
    
    deleted_count = 0
    
    for agency in targets:
        try:
            # 1. Fetch to confirm count
            res = supabase.table('articles')\
                .select('id, title, published_at')\
                .eq('agency', agency)\
                .gte('published_at', cutoff_str)\
                .execute()
                
            items = res.data
            count = len(items)
            print(f"[{agency}] Found {count} items to delete.")
            
            if count > 0:
                # 2. Delete
                del_res = supabase.table('articles')\
                    .delete()\
                    .eq('agency', agency)\
                    .gte('published_at', cutoff_str)\
                    .execute()
                
                # Check deleted count (response usually contains data of deleted rows)
                actual_deleted = len(del_res.data) if del_res.data else 0
                print(f"  -> Deleted {actual_deleted} items.")
                deleted_count += actual_deleted
                
        except Exception as e:
            print(f"Error deleting {agency}: {e}")
            
    print(f"\nTotal Deleted: {deleted_count}")

if __name__ == "__main__":
    delete_recent_regulations()
