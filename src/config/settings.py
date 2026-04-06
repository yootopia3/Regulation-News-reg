"""Central settings module.

- Defines project constants (migrated from root `config/settings.py`).
- Provides a single explicit `load_env()` entry point for `.env` loading.
- Exposes getter functions for environment-backed secrets.

Importing this module has no side effects. Callers must invoke `load_env()`
explicitly (typically at program entry).
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# --- Paths ---
CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"
AGENCIES_JSON_PATH: Path = CONFIG_DIR / "agencies.json"
SAFEGUARD_KEYWORDS_PATH: Path = CONFIG_DIR / "safeguard_keywords.json"

# --- Model Configuration for 2-Tier Hybrid Analysis ---

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


# --- Env loading ---
_ENV_LOADED = False


def load_env(path: Optional[Path] = None) -> None:
    """Load .env file exactly once (idempotent).

    If `path` is not provided, defaults to the repository root `.env`.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if path is None:
        path = CONFIG_DIR.parent / ".env"
    load_dotenv(str(path))
    _ENV_LOADED = True


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value


def get_supabase_url() -> str:
    return _require("SUPABASE_URL")


def get_supabase_anon_key() -> str:
    return _require("SUPABASE_ANON_KEY")


def get_gemini_api_key() -> str:
    return _require("GEMINI_API_KEY")


def get_telegram_bot_token() -> Optional[str]:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def get_telegram_chat_id() -> Optional[str]:
    return os.environ.get("TELEGRAM_CHAT_ID")
