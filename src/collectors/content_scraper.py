"""Article content page scraper."""

import logging
import random
import time
from typing import Dict, Optional
from urllib.parse import urljoin

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
        title_selector = scraper_config.get('content_title')
        page_title = soup.select_one(title_selector) if title_selector else None
        if title_selector and (not page_title or not page_title.get_text(strip=True)):
            logger.warning(f"Article title container not found for {url}")
            return None

        container_selector = scraper_config.get('container_selector') or scraper_config.get('content')

        if not container_selector:
            return None

        content_div = soup.select_one(container_selector)
        if not content_div:
            logger.warning(f"Container not found for {url} ({container_selector})")
            return None

        # Remove unwanted elements
        remove_selectors = ['script', 'style', 'noscript', 'nav', 'form'] + scraper_config.get('remove_selectors', [])
        for sel in remove_selectors:
            for match in content_div.select(sel):
                match.decompose()

        text_content = content_div.get_text(separator='\n', strip=True)
        if page_title and text_content.strip() == page_title.get_text(strip=True):
            logger.warning(f"Title-only content rejected for {url}")
            return None

        attachment_selector = scraper_config.get('attachment_links')
        if attachment_selector:
            attachments = []
            for link in soup.select(attachment_selector):
                href = link.get('href')
                if not href:
                    continue
                label = link.get_text(' ', strip=True) or href
                attachments.append(f"{label}: {urljoin(url, href)}")
            if attachments:
                text_content = text_content + "\n\nAttachments:\n" + "\n".join(attachments)

        # Data Integrity Check: Short Content Warning
        if not text_content.strip():
            logger.warning(f"Empty content container for {url}")
            return None
        logger.info('[%s] Body extracted: %s chars (%s)', agency_config.get('code'), len(text_content), url)
        if len(text_content) < 50:
            logger.warning(f"⚠️ Short content detected ({len(text_content)} chars) for {url}")
            return f"[Short Content] {text_content}"

        return text_content

    except Exception as e:
        logger.error(f"Error scraping content from {url}: {e}")
        return None
