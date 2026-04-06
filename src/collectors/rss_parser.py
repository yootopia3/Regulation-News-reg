import feedparser
import json
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional

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

    print(f"Fetching RSS for {agency.get('name', 'Unknown')}...")
    
    # Use custom headers to avoid blocking
    from config import settings
    headers = {
        'User-Agent': settings.USER_AGENT
    }

    try:
        import requests
        response = requests.get(target_url, headers=headers, timeout=settings.SCRAPER_TIMEOUT)
        response.raise_for_status()
        
        # Parse XML content
        feed = feedparser.parse(response.content)
        
        if hasattr(feed, 'bozo') and feed.bozo:
             print(f"  > Warning: Feed parsing issue for {agency.get('name')}: {feed.bozo_exception}")

    except Exception as e:
        print(f"  > Error processing URL {target_url}: {e}")
        return []
    
    parsed_items = []
    if not feed.entries:
        print(f"  > No entries found in feed.")

    for entry in feed.entries:
        # Extract fields
        title = entry.get('title', '').strip()
        link = entry.get('link', '').strip()
        
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
        
        item = {
            'agency': agency_id,
            'title': title,
            'link': link,
            'published_at': published_at.isoformat() if published_at else datetime.now(KST).isoformat(), 
            'source_published_at_str': published
        }
        parsed_items.append(item)
        
    return parsed_items

def collect_all_rss() -> List[Dict]:
    agencies = load_agencies()
    all_items = []
    
    for agency in agencies:
        try:
            items = fetch_rss_feed(agency)
            all_items.extend(items)
            print(f"  > Found {len(items)} items.")
        except Exception as e:
            print(f"  > Error fetching {agency['name']}: {e}")
            
    return all_items

if __name__ == "__main__":
    # Test execution
    items = collect_all_rss()
    print(f"\nTotal collected: {len(items)}")
    for item in items[:5]: # Show top 5
        print(item)
