"""List page scraper: fetches article list items from agency pages."""

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.config import settings
from src.collectors import http
from src.collectors.date_parser import KST, parse_date
from src.collectors.pagination import build_page_url


logger = logging.getLogger(__name__)


MAX_PAGES = 15


def fetch_list_items(
    agency_config: Dict,
    last_crawled_date: Optional[datetime] = None,
) -> List[Dict]:
    """Fetch list of articles using HTML scraping with automatic pagination.

    Loops through pages until it hits data older than cutoff_date.
    """
    if agency_config.get('collection_method') != 'scraper':
        return []

    base_url = agency_config.get('url')
    selectors = agency_config.get('selector', {})
    list_selector = selectors.get('list')

    if not base_url or not list_selector:
        logger.error(f"[{agency_config.get('code')}] Missing URL or list selector.")
        return []

    now_kst = datetime.now(KST)

    if last_crawled_date and last_crawled_date.tzinfo is None:
        last_crawled_date = KST.localize(last_crawled_date)

    # Max cutoff: never collect older than 7 days (even if DB was cleared)
    max_cutoff = now_kst - timedelta(days=7)

    if last_crawled_date:
        cutoff_date = max(last_crawled_date - timedelta(days=1), max_cutoff)
        logger.info(f"[{agency_config.get('code')}] Incremental: > {cutoff_date.strftime('%Y-%m-%d')}")
    else:
        cutoff_date = max_cutoff
        logger.info(f"[{agency_config.get('code')}] Full Scan (7d): > {cutoff_date.strftime('%Y-%m-%d')}")

    all_items: List[Dict] = []
    page = 1

    while page <= MAX_PAGES:
        current_url = build_page_url(base_url, page)

        logger.info(f"  [{agency_config.get('code')}] Page {page} fetching...")

        try:
            time.sleep(random.uniform(settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX))
            response = http.fetch(current_url)

            soup = BeautifulSoup(response.content, 'html.parser')
            rows = soup.select(list_selector)

            if not rows:
                if page == 1:
                    logger.warning(f"[{agency_config.get('code')}] No items found on Page 1 (Selector: {list_selector})")
                else:
                    logger.info(f"  [{agency_config.get('code')}] Page {page} empty. Stopping.")
                break

            page_items: List[Dict] = []
            reached_cutoff = False

            for row in rows:
                try:
                    title_sel = selectors.get('title')
                    title_elem = row.select_one(title_sel) if title_sel else row.select_one('a')

                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link_href = title_elem.get('href')

                    if link_href:
                        if not link_href.startswith('http'):
                            link = urljoin(base_url, link_href)
                        else:
                            link = link_href
                    else:
                        link = base_url

                    date_sel = selectors.get('date')
                    date_str = ""
                    if date_sel:
                        date_elem = row.select_one(date_sel)
                        if date_elem:
                            date_str = date_elem.get_text(strip=True)

                    pub_date = parse_date(date_str)

                    if pub_date:
                        if pub_date >= cutoff_date:
                            page_items.append({
                                'title': title,
                                'link': link,
                                'published_at': pub_date.isoformat(),
                                'agency': agency_config.get('code'),
                                'category': agency_config.get('category', 'press_release')
                            })
                        else:
                            reached_cutoff = True
                    else:
                        page_items.append({
                            'title': title,
                            'link': link,
                            'published_at': now_kst.isoformat(),
                            'agency': agency_config.get('code'),
                            'category': agency_config.get('category', 'press_release')
                        })

                except Exception as e:
                    logger.error(f"Error parsing row: {e}")
                    continue

            if page_items:
                all_items.extend(page_items)
                logger.info(f"    > Found {len(page_items)} items on Page {page}.")

            if reached_cutoff:
                logger.info(f"  [{agency_config.get('code')}] Reached cutoff on Page {page}. Stopping.")
                break

            if len(rows) < 3:
                break

            page += 1

        except Exception as e:
            logger.error(f"[{agency_config.get('code')}] Error fetching page {page}: {e}")
            break

    return all_items
