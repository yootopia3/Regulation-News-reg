from src.db.client import supabase
from datetime import datetime

def check_dates():
    # Get High risk items with dates
    res = supabase.table('articles').select('title, published_at').eq('analysis_result->>risk_level', 'High').order('published_at', desc=True).limit(20).execute()
    
    print(f"Found {len(res.data)} High Risk Articles:")
    for item in res.data:
        print(f"[{item['published_at'][:10]}] {item['title'][:40]}...")

if __name__ == "__main__":
    check_dates()
