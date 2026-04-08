
import os
import sys
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# Load env variables
load_dotenv('web/.env.local')

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL_V2") or os.environ.get("SUPABASE_URL")
key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY_V2") or os.environ.get("SUPABASE_ANON_KEY")

if not url or not key:
    print("Error: Supabase credentials not found.")
    sys.exit(1)

supabase = create_client(url, key)

def check_dates(agency_code):
    print(f"\nChecking dates for {agency_code}...")
    try:
        # Fetch titles and dates
        res = supabase.table('articles')\
            .select('title, published_at')\
            .eq('agency', agency_code)\
            .order('published_at', desc=True)\
            .limit(100)\
            .execute()
            
        dates = [r['published_at'].split('T')[0] for r in res.data]
        count = Counter(dates)
        
        print("Date Distribution (Top 100 recent):")
        for date, cnt in count.most_common():
            print(f"  {date}: {cnt} items")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_dates("MOEF")
    check_dates("FSC")
