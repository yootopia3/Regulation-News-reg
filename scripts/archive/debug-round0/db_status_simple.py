from src.db.client import supabase
from collections import Counter

def check_db_status():
    print("Fetching article stats...")
    res = supabase.table('articles').select('agency, analysis_result, title, created_at').execute()
    
    if not res.data:
        print("No articles found in DB.")
        return

    agency_counts = Counter()
    analyzed_counts = Counter()
    
    for item in res.data:
        agency = item['agency']
        agency_counts[agency] += 1
        
        # Check if analysis exists (basic check)
        if item.get('analysis_result'):
             analyzed_counts[agency] += 1

    print("\n=== Reference: Agency Counts ===")
    for agency, count in agency_counts.items():
        analyzed = analyzed_counts[agency]
        print(f"{agency}: Total {count} | Analyzed {analyzed} ({(analyzed/count)*100:.1f}%)")
        
    print("\n=== Latest 5 Articles ===")
    sorted_data = sorted(res.data, key=lambda x: x['created_at'], reverse=True)[:5]
    for item in sorted_data:
        has_analysis = bool(item.get('analysis_result'))
        print(f"[{item['agency']}] {item['title'][:40]}... (Analyzed: {has_analysis})")

if __name__ == "__main__":
    check_db_status()
