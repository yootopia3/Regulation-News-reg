# Model Configuration for 2-Tier Hybrid Analysis

# Tier 1: Gatekeeper (Fast, cheap filtering)
MODEL_FILTER_ID = "gemini-2.5-flash-lite"

# Tier 2: Analyst (Deep analysis for important news)
MODEL_ANALYZER_ID = "gemini-3-flash-preview"

# Fallback if Tier 2 model unavailable
MODEL_ANALYZER_FALLBACK = "gemini-1.5-pro"

# Importance threshold to trigger Tier 2 analysis
# Only articles with importance_score >= this value get deep analysis
IMPORTANCE_THRESHOLD = 3

# Rate limiting (seconds between API calls)
# With billing enabled, 0.5s is safe and fast
API_CALL_DELAY = 0.5

# --- Scraper Settings ---
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
SCRAPER_TIMEOUT = 20
SCRAPER_RETRY_DELAY_MIN = 2.0
SCRAPER_RETRY_DELAY_MAX = 4.0

# SSL Verification (False is recommended for some KR govt sites)
SSL_VERIFY = False
SUPPRESS_SSL_WARNINGS = True

# --- Scheduler Settings ---
COLLECTION_INTERVAL_MINUTES = 10

# --- Logging Settings ---
LOG_FILE_PATH = "logs/app.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
