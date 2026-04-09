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
#
# Runtime consumers MUST use the getters below (`get_model_filter_id()`,
# `get_model_analyzer_id()`, `get_model_analyzer_fallback()`) so that values
# set by `load_env()` at program entry are actually honored. The getters read
# `os.environ` on every call, so they observe overrides applied after import.

_DEFAULT_FILTER_MODEL = "gemini-2.5-flash-lite"
_DEFAULT_ANALYZER_MODEL = "gemini-3-flash-preview"
_DEFAULT_ANALYZER_FALLBACK_MODEL = "gemini-1.5-pro"


def get_model_filter_id() -> str:
    """Return the Tier 1 gatekeeper model ID, read fresh from env each call."""
    return os.environ.get("GEMINI_FILTER_MODEL", _DEFAULT_FILTER_MODEL)


def get_model_analyzer_id() -> str:
    """Return the Tier 2 analyst model ID, read fresh from env each call."""
    return os.environ.get("GEMINI_ANALYZER_MODEL", _DEFAULT_ANALYZER_MODEL)


def get_model_analyzer_fallback() -> str:
    """Return the Tier 2 fallback model ID, read fresh from env each call."""
    return os.environ.get(
        "GEMINI_ANALYZER_FALLBACK_MODEL", _DEFAULT_ANALYZER_FALLBACK_MODEL
    )

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

# SSL Verification.
# Default: verify TLS. Per-agency opt-out via `config/agencies.json` `ssl_verify: false`.
SSL_VERIFY = True
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
