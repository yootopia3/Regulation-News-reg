"""Backward-compatible facade for the decomposed scraper modules.

The real implementation now lives in:
  - src.collectors.http
  - src.collectors.date_parser
  - src.collectors.pagination
  - src.collectors.list_scraper
  - src.collectors.content_scraper
  - src.collectors.sanction_scraper

This module preserves the `ContentScraper` class so existing callers
(`src.pipeline.Pipeline`) continue to work unchanged.
"""

from datetime import datetime
from typing import Dict, List, Optional

from src.collectors import content_scraper, list_scraper, sanction_scraper


class ContentScraper:
    """Facade over the decomposed collector modules."""

    def fetch_list_items(
        self,
        agency_config: Dict,
        last_crawled_date: Optional[datetime] = None,
    ) -> List[Dict]:
        return list_scraper.fetch_list_items(agency_config, last_crawled_date)

    def fetch_content(self, url: str, agency_config: Dict) -> Optional[str]:
        return content_scraper.fetch_content(url, agency_config)

    def fetch_sanction_items(self, agency_config: Dict) -> List[Dict]:
        return sanction_scraper.fetch_sanction_items(agency_config)
