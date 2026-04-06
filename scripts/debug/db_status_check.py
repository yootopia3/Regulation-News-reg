from src.db.client import supabase
import pandas as pd
import json

def check_db_status():
    # Fetch all articles
    res = supabase.table('articles').select('agency, analysis_result, created_at, title').execute()
    
    if not res.data:
        print("No articles found in DB.")
        return

    df = pd.DataFrame(res.data)
    
    print("=== Agency Count ===")
    print(df['agency'].value_counts())
    
    print("\n=== Analysis Status ===")
    # Check if analysis_result is not null
    df['has_analysis'] = df['analysis_result'].notnull()
    print(df.groupby('agency')['has_analysis'].value_counts())
    
    print("\n=== Latest 5 Articles ===")
    # Sort by created_at desc
    latest = df.sort_values('created_at', ascending=False).head(5)
    for _, row in latest.iterrows():
        print(f"[{row['agency']}] {row['title'][:30]}... (Analyzed: {row['has_analysis']})")

if __name__ == "__main__":
    check_db_status()
