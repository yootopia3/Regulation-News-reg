import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

def check_duplicates():
    # Initialize Supabase client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_ANON_KEY not found in environment variables.")
        return

    supabase = create_client(url, key)

    print("Checking for IFRS articles...")
    
    # Fetch articles containing 'IFRS' in title
    response = supabase.table("articles").select("*").ilike("title", "%IFRS%").execute()
    
    articles = response.data
    
    if not articles:
        print("No articles found with 'IFRS' in title.")
        return

    with open("debug_ifrs_result.md", "w", encoding="utf-8") as f:
        f.write(f"Found {len(articles)} articles with 'IFRS'. Analyzing for duplicates...\n")
        f.write("-" * 80 + "\n")

        from collections import defaultdict
        title_map = defaultdict(list)
        
        for art in articles:
            title = art['title'].strip()
            title_map[title].append(art)
            
        duplicates = {k: v for k, v in title_map.items() if len(v) > 1}
        
        if not duplicates:
            f.write("No exact title duplicates found.\n")
            f.write("Printing all articles for manual inspection:\n")
            for i, art in enumerate(articles):  # Print ALL to find fuzzy dupes
                f.write(f"[{i+1}] Title: {art['title']}\n")
                f.write(f"    Date: {art['published_at']}\n")
                f.write(f"    Link: {art['link']}\n")
                f.write("-" * 20 + "\n")
        else:
            f.write(f"Found {len(duplicates)} duplicate groups:\n")
            for title, items in duplicates.items():
                f.write(f"\n[Duplicate Group] Title: {title}\n")
                for item in items:
                    f.write(f"  - ID: {item['id']}\n")
                    f.write(f"    Date: {item['published_at']}\n")
                    f.write(f"    Agency: {item['agency']}\n")
                    f.write(f"    Link: {item['link']}\n")
                    f.write(f"    Raw Title: {item['title']}\n")


if __name__ == "__main__":
    check_duplicates()
