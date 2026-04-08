from src.db.client import supabase

def check_moef_dates():
    print("Fetching MOEF latest articles...")
    res = supabase.table('articles').select('title, published_at').eq('agency', 'MOEF').order('published_at', desc=True).limit(5).execute()
    
    for item in res.data:
        print(f"[{item['published_at']}] {item['title']}")

if __name__ == "__main__":
    check_moef_dates()
