from src.db.client import supabase

def check_counts():
    # Count High Risk
    res_high = supabase.table('articles').select('id', count='exact').eq('analysis_result->>risk_level', 'High').execute()
    count_high = res_high.count
    
    # Count Medium Risk
    res_med = supabase.table('articles').select('id', count='exact').eq('analysis_result->>risk_level', 'Medium').execute()
    count_med = res_med.count

    print(f"High Risk: {count_high}")
    print(f"Medium Risk: {count_med}")

if __name__ == "__main__":
    check_counts()
