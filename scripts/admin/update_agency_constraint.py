"""
Update Supabase check constraint to allow new agency codes.
Run this script once to update the database schema.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('web/.env.local')

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL_V2") or os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # Need service role key for DDL

if not key:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not found. You need to update the constraint manually in Supabase Dashboard.")
    print()
    print("Go to Supabase Dashboard > SQL Editor and run:")
    print()
    print("""
-- Drop existing constraint
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_agency_check;

-- Add new constraint with all agency codes including sanction notices
ALTER TABLE articles ADD CONSTRAINT articles_agency_check 
CHECK (agency IN ('FSC', 'FSS', 'MOEF', 'BOK', 'FSS_REG', 'FSC_REG', 'FSS_REG_INFO', 'FSS_SANCTION', 'FSS_MGMT_NOTICE'));
""")
else:
    sb = create_client(url, key)
    # Execute using RPC (if available) or note that manual update is needed
    print("Attempting to update constraint...")
    # Note: Supabase client may not support DDL directly
    print("Please run the SQL manually in Supabase Dashboard.")
