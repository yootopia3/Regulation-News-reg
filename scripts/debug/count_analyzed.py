import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(url, key)

response = supabase.table("articles").select("*").execute()
articles = response.data

analyzed_count = 0
relevant_true = 0
relevant_false = 0

for a in articles:
    res = a.get('analysis_result')
    if res and 'is_relevant' in res:
        analyzed_count += 1
        if res['is_relevant']:
            relevant_true += 1
        else:
            relevant_false += 1

print(f"Total Articles: {len(articles)}")
print(f"Propberly Analyzed: {analyzed_count}")
print(f"  - Relevant: {relevant_true}")
print(f"  - Not Relevant: {relevant_false}")
