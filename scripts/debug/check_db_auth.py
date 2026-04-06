
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

print(f"URL: {url}")
# Hide key for security, print first/last 5 chars
if key:
    print(f"KEY: {key[:5]}...{key[-5:]}")
else:
    print("KEY: Not Found")

try:
    supabase = create_client(url, key)
    # Simple query to check auth
    res = supabase.table("articles").select("count", count="exact").limit(1).execute()
    print("DB Connection Success!")
    print(f"Total rows: {res.count}")
except Exception as e:
    print(f"DB Connection Failed: {e}")
