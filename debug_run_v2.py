
import os
import sys
import runpy

# 1. Load V2 Env vars from web/.env.local
env_path = os.path.join('web', '.env.local')
print(f"Loading env from {env_path}")

try:
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
                
            if 'NEXT_PUBLIC_SUPABASE_URL_V2=' in line:
                val = line.split('=', 1)[1].strip().strip("'").strip('"')
                os.environ['SUPABASE_URL'] = val
                print(f"Set SUPABASE_URL: {val[:10]}...")
                
            if 'NEXT_PUBLIC_SUPABASE_ANON_KEY_V2=' in line:
                val = line.split('=', 1)[1].strip().strip("'").strip('"')
                os.environ['SUPABASE_ANON_KEY'] = val
                print(f"Set SUPABASE_ANON_KEY: {val[:10]}...")
                
            # Also set GEMINI_API_KEY if needed (it might be in .env not .env.local, but let's check)
            if 'GEMINI_API_KEY=' in line:
                val = line.split('=', 1)[1].strip().strip("'").strip('"')
                os.environ['GEMINI_API_KEY'] = val
                print("Set GEMINI_API_KEY from .env.local")

except FileNotFoundError:
    print("Error: web/.env.local not found!")
    sys.exit(1)

# Ensure GEMINI_API_KEY is present (fallback to root .env if not in .env.local)
if 'GEMINI_API_KEY' not in os.environ:
    import dotenv
    dotenv.load_dotenv('.env')
    print("Loaded GEMINI_API_KEY from root .env")

# 2. Add 'src' to sys.path to simulate running from root
current_dir = os.getcwd()
sys.path.append(current_dir)
print(f"Added {current_dir} to PYTHONPATH")

# 3. Run the pipeline
print("\n--- Starting Collector (Debug Mode) ---\n")
try:
    # Execute src/main.py
    runpy.run_module('src.main', run_name='__main__')
except Exception as e:
    print(f"\nExample execution Error: {e}")
