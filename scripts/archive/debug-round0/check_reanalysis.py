from src.db.client import supabase
import json

def check_reanalysis_status():
    print("Fetching sample articles...")
    # Fetch 50 random articles to get a good sample
    res = supabase.table('articles').select('title, analysis_result').limit(50).execute()
    
    analyzed_count = 0
    high_risk_count = 0
    medium_risk_count = 0
    low_risk_count = 0
    
    for item in res.data:
        analysis = item.get('analysis_result')
        if not analysis:
            continue
            
        analyzed_count += 1
        risk = analysis.get('risk_level', 'Low')
        
        if risk == 'High':
            high_risk_count += 1
        elif risk == 'Medium':
            medium_risk_count += 1
        elif risk == 'Low':
            low_risk_count += 1
    
    print(f"Total Checked: {len(res.data)}")
    print(f"Analyzed: {analyzed_count}")
    print(f"High Risk: {high_risk_count}")
    print(f"Medium Risk: {medium_risk_count}")
    print(f"Low Risk: {low_risk_count}")
    
    print("\n--- High Risk Examples ---")
    for item in res.data:
        analysis = item.get('analysis_result')
        if analysis and analysis.get('risk_level') == 'High':
            print(f"- {item['title'][:50]}... (Impact: {analysis.get('impact_analysis')[:50]}...)")

if __name__ == "__main__":
    check_reanalysis_status()
