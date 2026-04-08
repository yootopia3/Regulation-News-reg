import sys
import os
from datetime import datetime


# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from src.db.client import supabase
except Exception as e:
    print(f"Error importing supabase client: {e}")
    sys.exit(1)

def check_latest():
    try:
        with open('scripts/debug/last_check_result.txt', 'w', encoding='utf-8') as f:
            f.write("Fetching latest articles from Supabase...\n")
            response = supabase.table('articles').select('published_at, created_at, title, agency').order('created_at', desc=True).limit(5).execute()
            data = response.data
            
            if not data:
                f.write("No articles found in the database.\n")
                return

            f.write("\n=== Latest 5 Articles Collected ===\n")
            for i, article in enumerate(data):
                created_at = article.get('created_at')
                published_at = article.get('published_at')
                title = article.get('title')
                agency = article.get('agency')
                f.write(f"[{i+1}] [{agency}] {title}...\n")
                f.write(f"    Collected At (DB): {created_at}\n")
                f.write(f"    Published At:      {published_at}\n")
                f.write("-" * 50 + "\n")
            print("Done writing to file.")
            
    except Exception as e:
        with open('scripts/debug/last_check_result.txt', 'w', encoding='utf-8') as f:
            f.write(f"Error querying database: {e}\n")

if __name__ == "__main__":
    check_latest()
