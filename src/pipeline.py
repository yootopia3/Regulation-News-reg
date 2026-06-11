import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from src.collectors.kfb_collector import collect_kfb_rss_first
from src.collectors.rss_parser import collect_all_rss
from src.collectors.sanction_scraper import extract_sanction_key
from src.collectors.scraper import ContentScraper
from src.collectors.date_parser import KST
from src.config.agency_codes import AgencyCode, ArticleCategory, PublishedAtSource
from src.config.agency_loader import get_sanction_codes, is_sanction_agency
from src.db.client import get_supabase_client

logger = logging.getLogger(__name__)


SanctionKey = Tuple[str, str, str]


class Pipeline:
    def __init__(
        self,
        config_path,
        *,
        analyzer=None,
        notifier=None,
        db=None,
        scraper=None,
    ):
        self.config_path = config_path
        self.agency_map = self._load_agency_map()

        # Initialize Services
        self.analyzer = analyzer if analyzer is not None else self._init_analyzer()
        self.notifier = notifier if notifier is not None else self._init_notifier()
        self.supabase = db if db is not None else self._init_db()
        self.scraper = scraper if scraper is not None else ContentScraper()

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
        from src.config.settings import is_gemini_enabled, load_env

        load_env()
        if not is_gemini_enabled():
            logger.info("Gemini analysis disabled; collector will save articles without analysis_result.")
            return None

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
        """Return the set of all ``link`` values already stored in ``articles``.

        Supabase/PostgREST enforces a server-side ``max-rows`` cap (default
        1000) on every select. A single ``.execute()`` therefore never returns
        the full table once it grows past 1000 rows, which silently broke
        dedup. Page through the table in fixed-size windows until the last
        batch comes back short.
        """
        if not self.supabase:
            return set()
        links: Set[str] = set()
        page_size = 1000
        start = 0
        try:
            while True:
                res = (
                    self.supabase
                    .table('articles')
                    .select('link')
                    .range(start, start + page_size - 1)
                    .execute()
                )
                batch = res.data or []
                for row in batch:
                    link = row.get('link')
                    if link:
                        links.add(link)
                if len(batch) < page_size:
                    break
                start += page_size
        except Exception as e:
            logger.error(f"Failed to load existing links: {e}")
        return links

    def _load_sanction_keys(self) -> Set[SanctionKey]:
        """Load existing sanction identity tuples for all sanction agencies.

        Paginated for the same reason as ``_load_existing_links``.
        """
        if not self.supabase:
            return set()
        keys: Set[SanctionKey] = set()
        page_size = 1000
        for agency_code in get_sanction_codes():
            start = 0
            while True:
                try:
                    res = (
                        self.supabase
                        .table('articles')
                        .select('link')
                        .eq('agency', agency_code)
                        .range(start, start + page_size - 1)
                        .execute()
                    )
                except Exception as e:
                    logger.error(f"Failed to load sanction keys for {agency_code}: {e}")
                    break

                batch = res.data or []
                for row in batch:
                    link = row.get('link')
                    if not link:
                        continue
                    exam_id, seq = extract_sanction_key(link)
                    if exam_id and seq:
                        keys.add((str(agency_code), exam_id, seq))
                if len(batch) < page_size:
                    break
                start += page_size
        return keys

    def _load_last_crawled(self, scraper_agencies: List[Dict]) -> Dict[str, datetime]:
        """Fetch the most recent ``published_at`` per non-sanction scraper agency."""
        cache: Dict[str, datetime] = {}
        if not self.supabase:
            return cache
        from dateutil import parser
        for agency in scraper_agencies:
            agency_id = agency.get('code') or agency.get('id')
            if not agency_id or is_sanction_agency(agency_id):
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

    def _collect_rss_first(self, agency: Dict, last_crawled: Dict[str, datetime]) -> List[Dict]:
        agency_id = agency.get('code') or agency.get('id')
        if agency_id != AgencyCode.KFB.value:
            logger.warning(f"Unsupported rss_first agency: {agency_id}")
            return []
        last_date = last_crawled.get(agency_id)
        try:
            return collect_kfb_rss_first(agency, last_crawled_date=last_date)
        except Exception as e:
            logger.error(f"RSS-first collection failed for {agency_id}: {e}")
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
        if is_sanction_agency(agency_id):
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
            analysis_result = item.get('analysis_result')
            pdf_url = item.get('pdf_url')
            if pdf_url:
                if isinstance(analysis_result, dict):
                    # New dict; do not mutate the original (shared with _notify_item).
                    analysis_result = {**analysis_result, 'pdf_url': pdf_url}
                else:
                    if analysis_result is not None:
                        logger.warning(
                            "  > analysis_result has unexpected type %s; replacing with pdf_url-only dict.",
                            type(analysis_result).__name__,
                        )
                    analysis_result = {'pdf_url': pdf_url}

            published_at = item.get('published_at')
            if published_at:
                published_at_source = item.get('published_at_source')
            else:
                published_at = datetime.now(KST).isoformat()
                published_at_source = PublishedAtSource.COLLECTED_FALLBACK.value

            data = {
                "agency": item['agency'],
                "title": item['title'],
                "link": item['link'],
                "published_at": published_at,
                "published_at_source": published_at_source,
                "content": item.get('content') or "",
                "analysis_result": analysis_result,
                "category": item.get('category', ArticleCategory.PRESS_RELEASE),
            }
            for optional_key in ("source_org", "source_name", "subcategory", "dedup_key"):
                if item.get(optional_key):
                    data[optional_key] = item[optional_key]

            if data.get("dedup_key"):
                self.supabase.table("articles").upsert(data, on_conflict="dedup_key").execute()
            else:
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
        rss_first_agencies = [
            a for a in self.agency_map.values() if a.get('collection_method') == 'rss_first'
        ]
        last_crawled = self._load_last_crawled(scraper_agencies + rss_first_agencies)

        all_items: List[Dict] = []

        # 1. RSS Collection
        all_items.extend(self._collect_rss())

        # 2. RSS-first Collection
        for agency in rss_first_agencies:
            all_items.extend(self._collect_rss_first(agency, last_crawled))

        # 3. Scraper Collection (non-sanction)
        for agency in scraper_agencies:
            agency_id = agency.get('code') or agency.get('id')
            if is_sanction_agency(agency_id):
                continue
            all_items.extend(self._collect_scraper(agency, last_crawled))

        # 4. Sanction Notice Collection (separate handling)
        sanction_codes = get_sanction_codes()
        sanction_targets = [
            a for a in self.agency_map.values() if a.get('code') in sanction_codes
        ]
        for agency in sanction_targets:
            all_items.extend(self._collect_sanction(agency))

        if not all_items:
            logger.warning("No new items found from any source.")
            return

        logger.info(f"Total items to process: {len(all_items)}")

        # 5. Processing
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
