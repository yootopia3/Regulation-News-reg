
import os
import sys
import logging
from datetime import datetime, timedelta
import pytz
from supabase import create_client
import requests
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load envs (for local testing, GitHub Actions injects these)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials not missing. Cannot send alert.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

def check_system_health():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase credentials missing.")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Check Data Freshness (Created At)
    # We check if any new row was inserted in the last 6 hours
    # Timestamptz in Supabase is UTC usually
    now_utc = datetime.now(pytz.utc)
    threshold_time = now_utc - timedelta(hours=6)
    
    try:
        # Check latest 'created_at' in articles
        res = supabase.table("articles") \
            .select("created_at, title, agency") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if not res.data:
            send_telegram_alert("🚨 **CRITICAL**: Database is empty!")
            return

        latest_article = res.data[0]
        latest_created_at = datetime.fromisoformat(latest_article['created_at'].replace('Z', '+00:00'))
        
        time_diff = now_utc - latest_created_at
        hours_diff = time_diff.total_seconds() / 3600
        
        logger.info(f"Latest article: {latest_article['title']} ({hours_diff:.1f} hours ago)")
        
        # Dead Man's Switch Logic
        # Only alert if > 6 hours AND it's a weekday business hour (approx)
        # Simply: Alert if > 6 hours old.
        if hours_diff > 6:
            msg = f"⚠️ **Alert**: No new articles collected for {hours_diff:.1f} hours.\n" \
                  f"Last: {latest_article['title']} ({latest_article['agency']})"
            logger.warning(msg)
            send_telegram_alert(msg)
        else:
            logger.info("✅ System is healthy. Data collected recently.")
            # Optional: Send "Healthy" report if run manually or at specific times (e.g. 9am, 6pm)
            # We can check current hour
            kst = pytz.timezone('Asia/Seoul')
            current_hour = datetime.now(kst).hour
            
            # Send 'Alive' report at 09:00 and 18:00 KST
            if current_hour in [9, 18]:
                # Get stats for today
                today_start = datetime.now(kst).replace(hour=0, minute=0, second=0).astimezone(pytz.utc)
                count_res = supabase.table("articles") \
                    .select("id", count="exact") \
                    .gte("created_at", today_start.isoformat()) \
                    .execute()
                
                count = count_res.count if count_res.count is not None else 0
                
                send_telegram_alert(f"✅ **Daily Health Report**\nTime: {datetime.now(kst).strftime('%H:%M')}\nArticles Today: {count}\nStatus: Operational")

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        send_telegram_alert(f"🚨 **WATCHDOG ERROR**: Health check script failed!\nError: {str(e)}")

if __name__ == "__main__":
    check_system_health()
