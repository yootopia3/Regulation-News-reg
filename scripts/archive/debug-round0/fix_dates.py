from src.db.client import supabase
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FixBOKFSS")

def fix_bok_fss_dates():
    # 1. Select BOK and FSS articles
    # We can't select all at once easily with 'OR' in supabase-py simple client maybe?
    # Let's do loops.
    agencies = ['BOK', 'FSS']
    
    for agency in agencies:
        logger.info(f"Processing {agency}...")
        res = supabase.table('articles').select('*').eq('agency', agency).execute()
        
        for item in res.data:
            original_pub = item['published_at']
            # Parse ISO format
            # Format in DB: "2024-12-19T22:47:22.187858+00:00"
            try:
                dt = datetime.fromisoformat(original_pub)
                
                # If time is NOT 00:00:00, update it.
                if dt.hour != 0 or dt.minute != 0:
                    # Reset time to 00:00:00
                    new_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    new_pub = new_dt.isoformat()
                    
                    logger.info(f"Updating {item['id']}: {original_pub} -> {new_pub}")
                    
                    supabase.table('articles').update({'published_at': new_pub}).eq('id', item['id']).execute()
            except Exception as e:
                logger.error(f"Error parsing date for {item['id']}: {e}")

if __name__ == "__main__":
    fix_bok_fss_dates()
