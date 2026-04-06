import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.db.client import supabase

def check_dec26():
    """Check if Dec 26 articles exist and why they might be filtered"""
    with open('scripts/debug/dec26_check.txt', 'w', encoding='utf-8') as f:
        f.write("=== Checking for December 26 (KST) Articles ===\n\n")
        
        # Get articles from the last 2 days
        response = supabase.table('articles').select('id, title, agency, published_at, analysis_result').order('published_at', desc=True).limit(20).execute()
        data = response.data
        
        if not data:
            f.write("No articles found.\n")
            return
        
        dec26_articles = []
        other_articles = []
        
        for article in data:
            published_at = article.get('published_at', '')
            # UTC 2025-12-25T15:00:00 = KST 2025-12-26 00:00:00
            # So if UTC date is 12-25 and hour >= 15, it's KST 12-26
            # Or if UTC date is 12-26, it's definitely KST 12-26
            
            if '2025-12-26' in published_at or ('2025-12-25T' in published_at and int(published_at.split('T')[1][:2]) >= 15):
                dec26_articles.append(article)
            else:
                other_articles.append(article)
        
        f.write(f"Found {len(dec26_articles)} article(s) for Dec 26 (KST):\n")
        f.write("-" * 60 + "\n")
        
        for article in dec26_articles:
            f.write(f"\nID: {article.get('id')}\n")
            f.write(f"Title: {article.get('title')}\n")
            f.write(f"Agency: {article.get('agency')}\n")
            f.write(f"Published At: {article.get('published_at')}\n")
            
            analysis = article.get('analysis_result')
            if analysis:
                score = analysis.get('importance_score', 'N/A')
                risk = analysis.get('risk_level', 'N/A')
                f.write(f"Importance Score: {score}\n")
                f.write(f"Risk Level: {risk}\n")
                
                # Check if it would be filtered
                if isinstance(score, (int, float)) and score < 3:
                    f.write(f"*** FILTERED OUT: Score {score} < 3 ***\n")
                else:
                    f.write(f"*** VISIBLE: Score {score} >= 3 or not analyzed ***\n")
            else:
                f.write("Analysis Result: None (not analyzed yet)\n")
                f.write("*** VISIBLE: No analysis = shown by default ***\n")
            
            f.write("-" * 60 + "\n")
        
        f.write(f"\nOther recent articles (Dec 25 and earlier): {len(other_articles)}\n")
        for article in other_articles[:5]:
            analysis = article.get('analysis_result')
            score = analysis.get('importance_score', 'N/A') if analysis else 'N/A'
            f.write(f"  [{article.get('agency')}] {article.get('title')[:40]}... (Score: {score})\n")
        
        print("Done. Check scripts/debug/dec26_check.txt")

if __name__ == "__main__":
    check_dec26()
