
import os
import asyncio
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials not found in .env")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def check_recent_data():
    print(f"Checking DB data at {datetime.now()}...\n")
    
    # Check counts for last 7 days by agency
    agencies = ['FSC', 'FSS', 'MOEF', 'BOK']
    
    print(f"{'Agency':<10} | {'Latest Article Date':<25} | {'Count (Today)'}")
    print("-" * 55)
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    for agency in agencies:
        # Get latest article
        res = supabase.table("articles") \
            .select("published_at, title") \
            .eq("agency", agency) \
            .order("published_at", desc=True) \
            .limit(1) \
            .execute()
            
        latest_date = "No Data"
        if res.data:
            latest_date = res.data[0]['published_at']
            
        # Get today's count
        res_today = supabase.table("articles") \
            .select("id", count='exact') \
            .eq("agency", agency) \
            .gte("created_at", today_str) \
            .execute()
            
        count_today = res_today.count if res_today.count is not None else 0
        
        print(f"{agency:<10} | {latest_date:<25} | {count_today}")

    print("\n--- Recent 5 Articles (All Agencies) ---")
    res_recent = supabase.table("articles") \
        .select("published_at, agency, title") \
        .order("published_at", desc=True) \
        .limit(5) \
        .execute()
        
    for item in res_recent.data:
        print(f"[{item['published_at']}] {item['agency']}: {item['title']}")

if __name__ == "__main__":
    asyncio.run(check_recent_data())
