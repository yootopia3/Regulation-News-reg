"""Article content page scraper."""

import logging
import random
import time
from typing import Dict, Optional

from bs4 import BeautifulSoup

from src.config import settings
from src.config.agency_loader import get_ssl_verify
from src.collectors import http


logger = logging.getLogger(__name__)


def fetch_content(url: str, agency_config: Dict) -> Optional[str]:
    """Fetch article content based on agency configuration (selectors)."""
    scraper_config = agency_config.get('scraper') or agency_config.get('selector')
    if not scraper_config:
        logger.debug(f"No scraper/selector config for {agency_config.get('code')}")
        return None

    try:
        time.sleep(random.uniform(settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX))

        response = http.fetch(url, verify=get_ssl_verify(agency_config.get('code')))

        soup = BeautifulSoup(response.content, 'html.parser')

        container_selector = scraper_config.get('container_selector') or scraper_config.get('content')

        if not container_selector:
            return None

        content_div = soup.select_one(container_selector)
        if not content_div:
            logger.warning(f"Container not found for {url} ({container_selector})")
            return None

        # Remove unwanted elements
        remove_selectors = scraper_config.get('remove_selectors', [])
        for sel in remove_selectors:
            for match in content_div.select(sel):
                match.decompose()

        text_content = content_div.get_text(separator='\n', strip=True)

        # Data Integrity Check: Short Content Warning
        if len(text_content) < 50:
            logger.warning(f"⚠️ Short content detected ({len(text_content)} chars) for {url}")
            return f"[Short Content] {text_content}"

        return text_content

    except Exception as e:
        logger.error(f"Error scraping content from {url}: {e}")
        return None
