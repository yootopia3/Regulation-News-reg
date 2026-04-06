from src.db.client import supabase
import json

def check_fss_analysis():
    print("Fetching latest FSS articles...")
    # Fetch title & analysis_result for FSS
    res = supabase.table('articles').select('title, analysis_result').eq('agency', 'FSS').order('published_at', desc=True).limit(5).execute()
    
    for item in res.data:
        title = item['title']
        analysis = item['analysis_result']
        
        print(f"\nTitle: {title}")
        if analysis:
            print("Analysis Result:")
            print(json.dumps(analysis, indent=2, ensure_ascii=False))
        else:
            print("Analysis Result: NULL")

if __name__ == "__main__":
    check_fss_analysis()
