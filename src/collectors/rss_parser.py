import feedparser
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional

from src.config.agency_codes import PublishedAtSource

logger = logging.getLogger(__name__)

# Warn if a feed's most recent entry is older than this many days. Operational
# guard against "looks-alive but dead source" regressions (see Round 2 MOEF).
RSS_STALE_WARN_DAYS = 14

# Conservative retry policy for transient TCP-level failures (e.g. fsc.go.kr
# intermittently sends RST during TLS handshake from datacenter IPs). Designed
# to be friendly to the source so we are not mistaken for a bot:
#   - At most 3 total attempts (1 initial + 2 retries)
#   - Only retry on connection-level errors (ConnectionError/Timeout). HTTP
#     status errors are NOT retried — if the server actually responded, that
#     answer is final.
#   - Backoff between attempts (no rapid hammering).
RSS_FETCH_MAX_ATTEMPTS = 3
RSS_FETCH_RETRY_BACKOFF_SECONDS = (3.0, 5.0)  # sleep before retry #1, retry #2

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'agencies.json')

def load_agencies():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)['agencies']

# Korea Standard Time (KST = UTC+9)
KST = timezone(timedelta(hours=9))

def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        # Try standard RSS format (RFC 822)
        dt = parsedate_to_datetime(date_str)
        # Convert to KST if it's UTC
        return dt.astimezone(KST)
    except Exception:
        return None

def fetch_rss_feed(agency: Dict) -> List[Dict]:
    """
    Fetches and parses RSS feed for a single agency.
    """
    # 1. Check Method
    if agency.get('collection_method') and agency.get('collection_method') != 'rss':
        # If method is explicitly scraper, skip here
        return []
    
    # 2. Get URL (support new 'url' or old 'rss_url')
    target_url = agency.get('url') or agency.get('rss_url')
    if not target_url:
        return []

    logger.info(f"Fetching RSS for {agency.get('name', 'Unknown')}...")
    
    # Use custom headers to avoid blocking
    from src.config import settings
    from src.config.agency_loader import get_ssl_verify
    headers = {
        'User-Agent': settings.USER_AGENT
    }

    import requests

    verify = get_ssl_verify(agency.get('code') or agency.get('id'))

    response = None
    last_err: Optional[Exception] = None
    for attempt in range(1, RSS_FETCH_MAX_ATTEMPTS + 1):
        try:
            response = requests.get(target_url, headers=headers, timeout=settings.SCRAPER_TIMEOUT, verify=verify)
            response.raise_for_status()
            break  # success
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Transient TCP/TLS-level failure — retry with backoff (max 3 total).
            last_err = e
            if attempt < RSS_FETCH_MAX_ATTEMPTS:
                sleep_s = RSS_FETCH_RETRY_BACKOFF_SECONDS[attempt - 1]
                logger.warning(
                    f"  > Transient fetch error for {agency.get('name')} "
                    f"(attempt {attempt}/{RSS_FETCH_MAX_ATTEMPTS}): {type(e).__name__}. "
                    f"Retrying in {sleep_s}s..."
                )
                time.sleep(sleep_s)
                continue
            logger.warning(f"  > Error processing URL {target_url} after {attempt} attempts: {e}")
            return []
        except Exception as e:
            # HTTP errors / parser errors / other — do NOT retry. If the server
            # actually answered with 4xx/5xx that is its final word and hammering
            # the endpoint risks getting blocklisted.
            logger.error(f"  > Error processing URL {target_url}: {e}")
            return []

    if response is None:
        logger.error(f"  > Error processing URL {target_url}: {last_err}")
        return []

    # Parse XML content
    feed = feedparser.parse(response.content)

    if hasattr(feed, 'bozo') and feed.bozo:
        logger.warning(f"  > Warning: Feed parsing issue for {agency.get('name')}: {feed.bozo_exception}")

    parsed_items = []
    real_dates: List[datetime] = []
    if not feed.entries:
        logger.warning(f"  > No entries found in feed.")

    for entry in feed.entries:
        # Extract fields
        title = entry.get('title', '').strip()
        link = entry.get('link', '').strip()
        if link.startswith('http://'):
            link = 'https://' + link[7:]
        
        # Date parsing - try 'published' first, then 'updated' as fallback
        published = entry.get('published', '') or entry.get('updated', '')
        
        # FSC RSS uses 'YYYY-MM-DD HH:MM:SS' format in 'updated' field
        published_at = parse_date(published)
        if not published_at and published:
            # Try parsing FSC format: "2026-01-02 00:00:00"
            try:
                from datetime import datetime as dt
                parsed = dt.strptime(published, '%Y-%m-%d %H:%M:%S')
                published_at = parsed.replace(tzinfo=KST)
            except ValueError:
                pass
        
        # Get ID (support 'code' or 'id')
        agency_id = agency.get('code') or agency.get('id')
        
        if published_at:
            real_dates.append(published_at)
        published_at_source = (
            PublishedAtSource.SOURCE.value
            if published_at
            else PublishedAtSource.COLLECTED_FALLBACK.value
        )

        item = {
            'agency': agency_id,
            'title': title,
            'link': link,
            'published_at': published_at.isoformat() if published_at else datetime.now(KST).isoformat(),
            'published_at_source': published_at_source,
            'source_published_at_str': published
        }
        parsed_items.append(item)

    # Stale-source guard: warn (do not mutate behavior) if the freshest real
    # entry is older than RSS_STALE_WARN_DAYS. Reuses the same parsed datetimes
    # the items carry — including the FSC `%Y-%m-%d %H:%M:%S` fallback path —
    # so it stays in sync with whatever parse logic above accepts. Items that
    # fell through to "now" (parse failure) are excluded so they cannot mask a
    # genuinely dead source. Catches the Round 2 MOEF failure mode where a
    # renamed/abandoned slug keeps responding 200 with old items.
    if real_dates:
        latest = max(real_dates)
        age_days = (datetime.now(KST) - latest).days
        if age_days > RSS_STALE_WARN_DAYS:
            logger.warning(
                f"[STALE RSS] {agency.get('code') or agency.get('id')} "
                f"latest entry is {age_days}d old ({latest.date().isoformat()}); "
                f"source URL may be dead: {target_url}"
            )

    return parsed_items

def collect_all_rss() -> List[Dict]:
    agencies = load_agencies()
    all_items = []
    
    for agency in agencies:
        try:
            items = fetch_rss_feed(agency)
            all_items.extend(items)
            logger.info(f"  > Found {len(items)} items.")
        except Exception as e:
            logger.error(f"  > Error fetching {agency['name']}: {e}")
            
    return all_items

if __name__ == "__main__":
    # Test execution
    items = collect_all_rss()
    logger.info(f"\nTotal collected: {len(items)}")
    for item in items[:5]: # Show top 5
        logger.info(item)
