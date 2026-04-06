
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Explicitly load .env to ensure we get both v1 and v2 vars
load_dotenv()

# --- v1.0 (Source) Configuration ---
V1_URL = os.getenv("SUPABASE_URL")
V1_KEY = os.getenv("SUPABASE_ANON_KEY")

# --- v2.0 (Target) Configuration ---
V2_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL_V2")
V2_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY_V2")

if not V1_URL or not V1_KEY or not V2_URL or not V2_KEY:
    print("Error: Missing environment variables.")
    print(f"V1: {bool(V1_URL)}, {bool(V1_KEY)}")
    print(f"V2: {bool(V2_URL)}, {bool(V2_KEY)}")
    print("Please check .env file.")
    sys.exit(1)

# Initialize Clients
v1_client: Client = create_client(V1_URL, V1_KEY)
v2_client: Client = create_client(V2_URL, V2_KEY)

def seed_data():
    print("--- Starting Data Migration (v1 -> v2) ---")
    
    # 1. Fetch latest 100 articles from v1
    print("Fetching top 100 articles from v1.0 Production DB...")
    try:
        response = v1_client.table('articles')\
            .select('*')\
            .order('published_at', desc=True)\
            .limit(100)\
            .execute()
        
        articles = response.data
        if not articles:
            print("No articles found in v1 DB.")
            return

        print(f"Fetched {len(articles)} articles.")

    except Exception as e:
        print(f"Error fetching from v1: {e}")
        return

    # 2. Prepare data for v2 (Add new columns default values)
    print("Preparing data for v2.0 schema...")
    v2_payload = []
    
    for article in articles:
        # v2 columns: view_count, star_rating, is_trending
        # We preserve the original ID to keep it consistent (optional, but good for debugging)
        new_row = article.copy()
        
        # Ensure v2 default values (though DB has defaults, it's safer to be explicit)
        new_row['view_count'] = 0
        new_row['star_rating'] = None # or 3? Let's leave it null (not rated)
        new_row['is_trending'] = False
        
        v2_payload.append(new_row)

    # 3. Insert into v2
    print(f"Inserting {len(v2_payload)} articles into v2.0 Development DB...")
    try:
        # Upsert allows re-running this script without Unique Constraint errors
        insert_response = v2_client.table('articles').upsert(v2_payload).execute()
        print("Success! Data seeded.")
    except Exception as e:
        print(f"Error inserting into v2: {e}")

if __name__ == "__main__":
    seed_data()
