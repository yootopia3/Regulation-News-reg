import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from src.collectors.kfb_collector import collect_kfb_rss_first
from src.collectors.rss_parser import collect_all_rss
from src.collectors.result import CollectionResult, FailureKind, failure_kind
from src.collectors.urls import canonical_article_url
from src.collectors.sanction_scraper import extract_sanction_key
from src.collectors.scraper import ContentScraper
from src.collectors.date_parser import KST
from src.config.agency_codes import AgencyCode, ArticleCategory, PublishedAtSource
from src.config.agency_loader import get_sanction_codes, is_sanction_agency
from src.db.client import get_supabase_client

logger = logging.getLogger(__name__)


SanctionKey = Tuple[str, str, str]
PDF_URL_RE = re.compile(
    r"https?://[^\s)>\"]+(?:\.pdf|download|file=)[^\s)>\"]*",
    re.IGNORECASE,
)
BODY_RETRY_LIMIT = 5
BODY_RETRY_DAYS = 7
# Restrict automatic repair to the source templates verified in this recovery.
BODY_RETRY_AGENCIES = ('FSC', 'FSS', 'KFB')


class PipelineRunError(RuntimeError):
    """Raised after healthy sources have been processed when a cycle is incomplete."""


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
        self.source_results = {}
        self.setup_failures = []
        self.automation_ready = False
        self.body_attempted = set()

    def _source_result(self, code):
        return self.source_results.setdefault(str(code), {
            'status': 'empty', 'collection_status': 'empty', 'collected': 0, 'failures': [],
            'saved': 0, 'save_failed': 0, 'body_failed': 0, 'duplicates': 0,
            'body_repaired': 0,
        })

    def _record_collection(self, code, items):
        result = self._source_result(code)
        result['collected'] = len(items)
        result['failures'] = list(getattr(items, 'failures', []))
        result['status'] = ('failed' if result['failures'] else
                            ('success' if items else 'empty'))
        result['collection_status'] = result['status']
        return items

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
                        links.add(canonical_article_url(link))
                if len(batch) < page_size:
                    break
                start += page_size
        except Exception as e:
            logger.error(f"Failed to load existing links: {e}")
            self.setup_failures.append('existing_links')
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
                    self.setup_failures.append('sanction_keys')
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
                self.setup_failures.append('last_crawled')
        return cache

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------
    def _collect_rss(self) -> List[Dict]:
        try:
            rss_items = collect_all_rss()
            logger.info(f"Collected {len(rss_items)} items from RSS targets.")
            sources = getattr(rss_items, 'sources', {})
            for code, agency in self.agency_map.items():
                if agency.get('collection_method', 'rss') == 'rss':
                    self._record_collection(code, sources.get(code, [
                        item for item in rss_items if item['agency'] == code
                    ]))
            return rss_items
        except Exception as e:
            logger.error(f"RSS Collection failed: {e}")
            for code, agency in self.agency_map.items():
                if agency.get('collection_method', 'rss') == 'rss':
                    self._record_collection(code, CollectionResult(failures=[failure_kind(e)]))
            return []

    def _collect_scraper(self, agency: Dict, last_crawled: Dict[str, datetime]) -> List[Dict]:
        agency_id = agency.get('code') or agency.get('id')
        logger.info(f"Starting HTML scraping for {agency_id}...")
        last_date = last_crawled.get(agency_id)
        try:
            scraped_items = self.scraper.fetch_list_items(agency, last_crawled_date=last_date)
            logger.info(f"  > Scraped {len(scraped_items)} new items from {agency_id}.")
            return self._record_collection(agency_id, scraped_items)
        except Exception as e:
            logger.error(f"Scraping failed for {agency_id}: {e}")
            return self._record_collection(agency_id, CollectionResult(failures=[failure_kind(e)]))

    def _collect_rss_first(self, agency: Dict, last_crawled: Dict[str, datetime]) -> List[Dict]:
        agency_id = agency.get('code') or agency.get('id')
        if agency_id != AgencyCode.KFB.value:
            logger.warning(f"Unsupported rss_first agency: {agency_id}")
            return self._record_collection(agency_id, CollectionResult(failures=[FailureKind.CONFIG]))
        last_date = last_crawled.get(agency_id)
        try:
            return self._record_collection(agency_id, collect_kfb_rss_first(agency, last_crawled_date=last_date))
        except Exception as e:
            logger.error(f"RSS-first collection failed for {agency_id}: {e}")
            return self._record_collection(agency_id, CollectionResult(failures=[failure_kind(e)]))

    def _collect_sanction(self, agency: Dict) -> List[Dict]:
        agency_id = agency.get('code')
        logger.info(f"Starting sanction notice scraping for {agency_id}...")
        try:
            items = self.scraper.fetch_sanction_items(agency)
            logger.info(f"  > Collected {len(items)} sanction notices from {agency_id}.")
            return self._record_collection(agency_id, items)
        except Exception as e:
            logger.error(f"Sanction scraping failed for {agency_id}: {e}")
            return self._record_collection(agency_id, CollectionResult(failures=[failure_kind(e)]))

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
        if item.get('dedup_key'):
            return False
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
        self.body_attempted.add(link)
        if not agency_config:
            return title + "\n" + item.get('description', '')
        content = self.scraper.fetch_content(link, agency_config)
        if content:
            item['content'] = content
            if item.get('agency') == AgencyCode.KFB.value and not item.get('pdf_url'):
                pdf_match = PDF_URL_RE.search(content)
                if pdf_match:
                    item['pdf_url'] = pdf_match.group(0)
            return content
        return title + "\n" + item.get('description', '')

    def _repair_empty_bodies(self):
        """Retry at most five recently created empty rows; never rewrite metadata.

        The conditional update also protects a body filled concurrently. This
        is a bounded retry of recent failures, not an archive backfill.
        """
        if not self.supabase or self.setup_failures:
            return
        codes = [code for code in BODY_RETRY_AGENCIES if code in self.agency_map]
        try:
            rows = (self.supabase.table('articles').select('agency,title,link')
                    .in_('agency', codes).or_('content.is.null,content.eq.')
                    .gte('created_at', (datetime.now(KST) - timedelta(days=BODY_RETRY_DAYS)).isoformat())
                    .order('created_at', desc=True).limit(BODY_RETRY_LIMIT).execute().data or [])
        except Exception:
            self.setup_failures.append('body_retry_read')
            return
        for item in rows[:BODY_RETRY_LIMIT]:
            link = item['link']
            if link in self.body_attempted:
                continue
            result = self._source_result(item['agency'])
            self._fetch_item_content(item, self.agency_map[item['agency']])
            content = item.get('content')
            if not content or not content.strip():
                result['body_failed'] += 1
                continue
            try:
                saved = (self.supabase.table('articles').update({'content': content})
                         .eq('link', link).or_('content.is.null,content.eq.').execute())
                if saved.data:
                    result['body_repaired'] += 1
                    logger.info('[%s] Empty body repaired: %s', item['agency'], link)
            except Exception:
                result['save_failed'] += 1

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

    def _save_item(self, item: Dict) -> bool:
        if not self.supabase:
            logger.error("  > Failed to save to DB: client unavailable.")
            return False
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
                # Insert new metadata even when the body is unavailable. On a
                # conflict this first request must NEVER replace existing data.
                self.supabase.table("articles").upsert(
                    data, on_conflict="dedup_key", ignore_duplicates=True,
                ).execute()
                # A column-selective update preserves unavailable fields without
                # a read/merge/write race or a new DB function/migration.
                updates = dict(data)
                if not str(item.get('content') or '').strip():
                    updates.pop('content')
                analysis = item.get('analysis_result')
                if not isinstance(analysis, dict) or not analysis or analysis.get('analysis_status') == 'ANALYSIS_FAILED':
                    updates.pop('analysis_result')
                saved = self.supabase.table("articles").update(updates).eq(
                    "dedup_key", data['dedup_key'],
                ).execute()
            else:
                saved = self.supabase.table("articles").insert(data).execute()
            if not saved.data:
                raise RuntimeError("Save returned no rows; persistence was not confirmed")
            logger.info("  > Saved to DB.")
            return True
        except Exception as e:
            logger.error(f"  > Failed to save to DB: {e}")
            return False

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
        self.source_results = {}
        self.setup_failures = []
        self.automation_ready = False
        self.body_attempted = set()
        if not self.supabase:
            self.setup_failures.append('db_unavailable')
        if not self.agency_map:
            self.setup_failures.append('agency_config')
        for code, agency in self.agency_map.items():
            if agency.get('collection_method', 'rss') not in {'rss', 'rss_first', 'scraper'}:
                self._record_collection(code, CollectionResult(failures=[FailureKind.CONFIG]))

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

        logger.info(f"Total items to process: {len(all_items)}")

        # 5. Processing
        for item in all_items:
            self._process_single_item(item, existing_links, sanction_keys)

        self._repair_empty_bodies()

        for result in self.source_results.values():
            if result['save_failed'] or result['body_failed']:
                result['status'] = 'failed'
        # Only database-confirmed sanction candidates can unlock analysis.
        # A source fetch/body failure alone does not invalidate other saved rows;
        # any DB/config uncertainty keeps the gate closed.
        self.automation_ready = (
            not self.setup_failures
            and not any(FailureKind.CONFIG in result['failures'] for result in self.source_results.values())
            and not any(result['save_failed'] for result in self.source_results.values())
            and any(is_sanction_agency(code) and (result['saved'] + result['duplicates'] > 0)
                    for code, result in self.source_results.items())
        )
        summary = {'sources': self.source_results, 'setup_failures': self.setup_failures,
                   'automation_ready': self.automation_ready}
        logger.info("Collection summary: %s", json.dumps(summary, ensure_ascii=False, sort_keys=True))
        failed = [code for code, result in self.source_results.items()
                  if result['failures'] or result['save_failed'] or result['body_failed']]
        if failed or self.setup_failures:
            raise PipelineRunError("Incomplete collection cycle; failed sources: "
                                   + ', '.join(failed) + "; setup failures: "
                                   + ', '.join(self.setup_failures))
        logger.info("Pipeline cycle completed successfully.")
        return summary

    def _process_single_item(
        self,
        item: Dict,
        existing_links: Set[str],
        sanction_keys: Set[SanctionKey],
    ) -> None:
        agency_id = item['agency']
        title = item['title']

        if self._is_duplicate(item, existing_links, sanction_keys):
            self._source_result(agency_id)['duplicates'] += 1
            logger.debug(f"Skipping duplicate: {title[:30]}...")
            return

        logger.info(f"Processing: [{agency_id}] {title}")

        agency_config = self.agency_map.get(agency_id)
        self._fetch_item_content(item, agency_config)
        result = self._source_result(agency_id)
        selectors = (agency_config or {}).get('scraper') or (agency_config or {}).get('selector', {})
        # PDF-based sanction collection and intentionally unconfigured body
        # scrapers retain their existing metadata-only behavior.
        if (not is_sanction_agency(agency_id)
                and (selectors.get('content') or selectors.get('container_selector'))
                and not str(item.get('content') or '').strip()):
            result['body_failed'] += 1
        analysis_result = self._analyze_item(item, agency_config)
        item['analysis_result'] = analysis_result
        if self._save_item(item):
            result['saved'] += 1
            existing_links.add(item['link'])
            if is_sanction_agency(agency_id):
                exam_id, seq = extract_sanction_key(item['link'])
                if exam_id and seq:
                    sanction_keys.add((str(agency_id), exam_id, seq))
            self._notify_item(item, agency_config, analysis_result)
        else:
            result['save_failed'] += 1
