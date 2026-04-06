"""
Clean up duplicate sanction notices - Fixed version with proper deletion.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
from supabase import create_client
from urllib.parse import urlparse, parse_qs
from collections import defaultdict

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(url, key)

def clean_duplicates(agency_id):
    print(f"\n=== Cleaning duplicates for {agency_id} ===")
    
    # Fetch all records for this agency
    res = supabase.table('articles').select('id, title, link, published_at').eq('agency', agency_id).order('published_at', desc=False).execute()
    
    print(f"Total records: {len(res.data)}")
    
    # Group by unique sanction ID (examMgmtNo + emOpenSeq)
    sanction_groups = defaultdict(list)
    
    for record in res.data:
        link = record['link']
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        
        exam_id = params.get('examMgmtNo', ['unknown'])[0]
        seq = params.get('emOpenSeq', ['unknown'])[0]
        unique_key = f"{exam_id}-{seq}"
        
        sanction_groups[unique_key].append(record)
    
    print(f"Unique sanctions: {len(sanction_groups)}")
    
    # Find duplicates and delete them (keep the first one)
    ids_to_delete = []
    
    for key, records in sanction_groups.items():
        if len(records) > 1:
            # Keep the first record (oldest), delete the rest
            for duplicate in records[1:]:
                ids_to_delete.append(duplicate['id'])
            print(f"  {key}: keeping 1, deleting {len(records)-1} duplicates")
    
    print(f"\nTotal to delete: {len(ids_to_delete)}")
    
    if ids_to_delete:
        print("Deleting...")
        deleted_count = 0
        for record_id in ids_to_delete:
            try:
                result = supabase.table('articles').delete().eq('id', record_id).execute()
                deleted_count += 1
                if deleted_count % 10 == 0:
                    print(f"  Deleted {deleted_count}/{len(ids_to_delete)}")
            except Exception as e:
                print(f"  Error deleting {record_id}: {e}")
        print(f"Done! Deleted {deleted_count} records.")
    else:
        print("No duplicates to delete.")

if __name__ == "__main__":
    clean_duplicates('FSS_SANCTION')
    clean_duplicates('FSS_MGMT_NOTICE')
    
    # Verify
    print("\n=== Verification ===")
    res = supabase.table('articles').select('id', count='exact').eq('agency', 'FSS_SANCTION').execute()
    print(f'FSS_SANCTION count after cleanup: {res.count}')
    res2 = supabase.table('articles').select('id', count='exact').eq('agency', 'FSS_MGMT_NOTICE').execute()
    print(f'FSS_MGMT_NOTICE count after cleanup: {res2.count}')
