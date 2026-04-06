from supabase import create_client, Client

from src.config.settings import load_env, get_supabase_url, get_supabase_anon_key

load_env()

url: str = get_supabase_url()
key: str = get_supabase_anon_key()

supabase: Client = create_client(url, key)
