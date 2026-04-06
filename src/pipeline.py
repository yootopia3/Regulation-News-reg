import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from src.collectors.rss_parser import collect_all_rss
from src.collectors.sanction_scraper import extract_sanction_key
from src.collectors.scraper import ContentScraper
from src.config.agency_codes import AgencyCode, ArticleCategory, SANCTION_AGENCY_CODES
from src.db.client import get_supabase_client

logger = logging.getLogger(__name__)


SanctionKey = Tuple[str, str, str]


class Pipeline:
    def __init__(self, config_path):
        self.config_path = config_path
        self.agency_map = self._load_agency_map()

        # Initialize Services
        self.analyzer = self._init_analyzer()
        self.notifier = self._init_notifier()
        self.supabase = self._init_db()
        self.scraper = ContentScraper()

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def _load_agency_map(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {a.get('code') or a.get('id'): a for a in data['agencies']}
        except Exception as e:
            logger.error(f"Failed to load agency config: {e}")
            return {}

    def _init_analyzer(self):
        try:
            from src.services.analyzer import HybridAnalyzer
            return HybridAnalyzer()
        except Exception as e:
            logger.error(f"Failed to init Analyzer: {e}")
            return None

    def _init_notifier(self):
        try:
            from src.services.notifier import TelegramNotifier
            return TelegramNotifier()
        except Exception:
            return None

    def _init_db(self):
        try:
            return get_supabase_client()
        except Exception as e:
            logger.error(f"Supabase client not available: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    # ------------------------------------------------------------------
    # Cycle-scoped dedup caches
    # ------------------------------------------------------------------
    def _load_existing_links(self) -> Set[str]:
        """Return the set of all ``link`` values already stored in ``articles``."""
        if not self.supabase:
            return set()
        try:
            res = self.supabase.table('articles').select('link').execute()
            return {row['link'] for row in (res.data or []) if row.get('link')}
        except Exception as e:
            logger.error(f"Failed to load existing links: {e}")
            return set()

    def _load_sanction_keys(self) -> Set[SanctionKey]:
        """Load existing sanction identity tuples for all sanction agencies."""
        if not self.supabase:
            return set()
        keys: Set[SanctionKey] = set()
        for agency_code in SANCTION_AGENCY_CODES:
            try:
                res = (
                    self.supabase
                    .table('articles')
                    .select('link')
                    .eq('agency', agency_code)
                    .execute()
                )
            except Exception as e:
                logger.error(f"Failed to load sanction keys for {agency_code}: {e}")
                continue

            for row in (res.data or []):
                link = row.get('link')
                if not link:
                    continue
                exam_id, seq = extract_sanction_key(link)
                if exam_id and seq:
                    keys.add((str(agency_code), exam_id, seq))
        return keys

    def _load_last_crawled(self, scraper_agencies: List[Dict]) -> Dict[str, datetime]:
        """Fetch the most recent ``published_at`` per non-sanction scraper agency."""
        cache: Dict[str, datetime] = {}
        if not self.supabase:
            return cache
        from dateutil import parser
        for agency in scraper_agencies:
            agency_id = agency.get('code') or agency.get('id')
            if not agency_id or agency_id in SANCTION_AGENCY_CODES:
                continue
            try:
                res = (
                    self.supabase
                    .table('articles')
                    .select('published_at')
                    .eq('agency', agency_id)
                    .order('published_at', desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    cache[agency_id] = parser.parse(res.data[0]['published_at'])
            except Exception as e:
                logger.warning(f"Failed to fetch last crawled date for {agency_id}: {e}")
        return cache

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------
    def _collect_rss(self) -> List[Dict]:
        try:
            rss_items = collect_all_rss()
            logger.info(f"Collected {len(rss_items)} items from RSS targets.")
            return rss_items
        except Exception as e:
            logger.error(f"RSS Collection failed: {e}")
            return []

    def _collect_scraper(self, agency: Dict, last_crawled: Dict[str, datetime]) -> List[Dict]:
        agency_id = agency.get('code') or agency.get('id')
        logger.info(f"Starting HTML scraping for {agency_id}...")
        last_date = last_crawled.get(agency_id)
        try:
            scraped_items = self.scraper.fetch_list_items(agency, last_crawled_date=last_date)
            logger.info(f"  > Scraped {len(scraped_items)} new items from {agency_id}.")
            return scraped_items
        except Exception as e:
            logger.error(f"Scraping failed for {agency_id}: {e}")
            return []

    def _collect_sanction(self, agency: Dict) -> List[Dict]:
        agency_id = agency.get('code')
        logger.info(f"Starting sanction notice scraping for {agency_id}...")
        try:
            items = self.scraper.fetch_sanction_items(agency)
            logger.info(f"  > Collected {len(items)} sanction notices from {agency_id}.")
            return items
        except Exception as e:
            logger.error(f"Sanction scraping failed for {agency_id}: {e}")
            return []

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------
    def _is_duplicate(
        self,
        item: Dict,
        existing_links: Set[str],
        sanction_keys: Set[SanctionKey],
    ) -> bool:
        agency_id = item['agency']
        link = item['link']
        if agency_id in SANCTION_AGENCY_CODES:
            exam_id, seq = extract_sanction_key(link)
            if exam_id and seq:
                return (str(agency_id), exam_id, seq) in sanction_keys
            # Fallback to link-level check for PDF/other formats.
            return link in existing_links
        return link in existing_links

    # ------------------------------------------------------------------
    # Per-item processing helpers
    # ------------------------------------------------------------------
    def _fetch_item_content(self, item: Dict, agency_config: Optional[Dict]) -> str:
        title = item['title']
        link = item['link']
        if not agency_config:
            return title + "\n" + item.get('description', '')
        content = self.scraper.fetch_content(link, agency_config)
        if content:
            item['content'] = content
            return content
        return title + "\n" + item.get('description', '')

    def _analyze_item(self, item: Dict, agency_config: Optional[Dict]) -> Optional[Dict]:
        if not self.analyzer:
            return None
        agency_id = item['agency']
        title = item['title']
        content = item.get('content') or (title + "\n" + item.get('description', ''))
        try:
            analysis_result = self.analyzer.process(
                {'title': title, 'content': content, 'description': item.get('description', '')},
                agency_config.get('name', agency_id) if agency_config else agency_id,
                category=item.get('category', ArticleCategory.PRESS_RELEASE),
            )
            item['analysis_result'] = analysis_result
            return analysis_result
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return None

    def _save_item(self, item: Dict) -> None:
        if not self.supabase:
            return
        try:
            data = {
                "agency": item['agency'],
                "title": item['title'],
                "link": item['link'],
                "published_at": item.get('published_at') or datetime.now().isoformat(),
                "content": item.get('content') or "",
                "analysis_result": item.get('analysis_result'),
                "category": item.get('category', ArticleCategory.PRESS_RELEASE),
            }
            self.supabase.table("articles").insert(data).execute()
            logger.info("  > Saved to DB.")
        except Exception as e:
            logger.error(f"  > Failed to save to DB: {e}")

    def _notify_item(
        self,
        item: Dict,
        agency_config: Optional[Dict],
        analysis_result: Optional[Dict],
    ) -> None:
        if not (self.notifier and analysis_result and analysis_result.get('analysis_status') == 'ANALYZED'):
            return
        agency_id = item['agency']
        a_name = agency_config.get('name', agency_id) if agency_config else agency_id
        logger.info("  > Sending Notification...")
        try:
            self.notifier.format_and_send(a_name, item['title'], item['link'], analysis_result)
        except Exception as e:
            logger.error(f"Notification failed: {e}")

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    def run(self):
        logger.info("Starting MarketPulse-Reg Pipeline...")

        # Build per-cycle dedup caches (1 query per cache).
        existing_links = self._load_existing_links()
        sanction_keys = self._load_sanction_keys()

        scraper_agencies = [
            a for a in self.agency_map.values() if a.get('collection_method') == 'scraper'
        ]
        last_crawled = self._load_last_crawled(scraper_agencies)

        all_items: List[Dict] = []

        # 1. RSS Collection
        all_items.extend(self._collect_rss())

        # 2. Scraper Collection (non-sanction)
        for agency in scraper_agencies:
            agency_id = agency.get('code') or agency.get('id')
            if agency_id in SANCTION_AGENCY_CODES:
                continue
            all_items.extend(self._collect_scraper(agency, last_crawled))

        # 3. Sanction Notice Collection (separate handling)
        sanction_targets = [
            a for a in self.agency_map.values() if a.get('code') in SANCTION_AGENCY_CODES
        ]
        for agency in sanction_targets:
            all_items.extend(self._collect_sanction(agency))

        if not all_items:
            logger.warning("No new items found from any source.")
            return

        logger.info(f"Total items to process: {len(all_items)}")

        # 4. Processing
        for item in all_items:
            self._process_single_item(item, existing_links, sanction_keys)

        logger.info("Pipeline cycle completed successfully.")

    def _process_single_item(
        self,
        item: Dict,
        existing_links: Set[str],
        sanction_keys: Set[SanctionKey],
    ) -> None:
        agency_id = item['agency']
        title = item['title']

        if self._is_duplicate(item, existing_links, sanction_keys):
            logger.debug(f"Skipping duplicate: {title[:30]}...")
            return

        logger.info(f"Processing: [{agency_id}] {title}")

        agency_config = self.agency_map.get(agency_id)
        self._fetch_item_content(item, agency_config)
        analysis_result = self._analyze_item(item, agency_config)
        item['analysis_result'] = analysis_result
        self._save_item(item)
        self._notify_item(item, agency_config, analysis_result)
