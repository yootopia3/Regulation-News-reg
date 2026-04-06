import logging
import json
import os
from datetime import datetime
from src.collectors.rss_parser import collect_all_rss
from src.collectors.scraper import ContentScraper
from src.utils.logger import setup_logger

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self, config_path):
        self.config_path = config_path
        self.agency_map = self._load_agency_map()
        
        # Initialize Services
        self.analyzer = self._init_analyzer()
        self.notifier = self._init_notifier()
        self.supabase = self._init_db()
        self.scraper = ContentScraper()

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
            from src.db.client import supabase
            return supabase
        except Exception as e:
            logger.error(f"Supabase client not available: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _get_last_crawled_date(self, agency_id):
        if not self.supabase:
            return None
        try:
            res = self.supabase.table('articles').select('published_at').eq('agency', agency_id).order('published_at', desc=True).limit(1).execute()
            if res.data and len(res.data) > 0:
                last_raw = res.data[0]['published_at']
                from dateutil import parser
                return parser.parse(last_raw)
        except Exception as e:
            logger.warning(f"Failed to fetch last crawled date for {agency_id}: {e}")
        return None

    def _is_duplicate(self, link):
        if not self.supabase:
            return False
        try:
            existing = self.supabase.table('articles').select('id').eq('link', link).execute()
            return bool(existing.data and len(existing.data) > 0)
        except Exception as e:
            logger.error(f"DB Check failed: {e}")
            return False

    def _is_sanction_duplicate(self, link, agency_id):
        """
        Sanction-specific duplicate check using examMgmtNo and emOpenSeq.
        FSS sanction URLs have varying date params, so we extract the unique IDs.
        """
        if not self.supabase:
            return False
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            exam_id = params.get('examMgmtNo', [None])[0]
            seq = params.get('emOpenSeq', [None])[0]
            
            if exam_id and seq:
                # Check if this exact sanction already exists
                existing = self.supabase.table('articles').select('id, link').eq('agency', agency_id).execute()
                for record in existing.data:
                    existing_parsed = urlparse(record['link'])
                    existing_params = parse_qs(existing_parsed.query)
                    existing_exam = existing_params.get('examMgmtNo', [None])[0]
                    existing_seq = existing_params.get('emOpenSeq', [None])[0]
                    if existing_exam == exam_id and existing_seq == seq:
                        return True
                return False
            else:
                # Fallback to standard link check for PDF links or other formats
                return self._is_duplicate(link)
        except Exception as e:
            logger.error(f"Sanction duplicate check failed: {e}")
            return False

    def _save_to_db(self, item):
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
                "category": item.get('category', 'press_release')
            }
            self.supabase.table("articles").insert(data).execute()
            logger.info("  > Saved to DB.")
        except Exception as e:
            logger.error(f"  > Failed to save to DB: {e}")

    def run(self):
        logger.info("Starting MarketPulse-Reg Pipeline...")
        all_items = []

        # 1. RSS Collection
        try:
            rss_items = collect_all_rss()
            logger.info(f"Collected {len(rss_items)} items from RSS targets.")
            all_items.extend(rss_items)
        except Exception as e:
            logger.error(f"RSS Collection failed: {e}")

        # 2. Scraper Collection
        scraper_targets = [a for a in self.agency_map.values() if a.get('collection_method') == 'scraper']
        for agency in scraper_targets:
            agency_id = agency.get('code') or agency.get('id')
            
            # Skip sanction notice agencies here (they use a different method)
            if agency_id in ['FSS_SANCTION', 'FSS_MGMT_NOTICE']:
                continue
            
            logger.info(f"Starting HTML scraping for {agency_id}...")
            
            last_date = self._get_last_crawled_date(agency_id)
            try:
                scraped_items = self.scraper.fetch_list_items(agency, last_crawled_date=last_date)
                logger.info(f"  > Scraped {len(scraped_items)} new items from {agency_id}.")
                all_items.extend(scraped_items)
            except Exception as e:
                logger.error(f"Scraping failed for {agency_id}: {e}")

        # 3. Sanction Notice Collection (separate handling)
        sanction_targets = [a for a in self.agency_map.values() if a.get('code') in ['FSS_SANCTION', 'FSS_MGMT_NOTICE']]
        for agency in sanction_targets:
            agency_id = agency.get('code')
            logger.info(f"Starting sanction notice scraping for {agency_id}...")
            try:
                sanction_items = self.scraper.fetch_sanction_items(agency)
                logger.info(f"  > Collected {len(sanction_items)} sanction notices from {agency_id}.")
                all_items.extend(sanction_items)
            except Exception as e:
                logger.error(f"Sanction scraping failed for {agency_id}: {e}")

        if not all_items:
            logger.warning("No new items found from any source.")
            return

        logger.info(f"Total items to process: {len(all_items)}")

        # 3. Processing
        for item in all_items:
            self._process_single_item(item)

        logger.info("Pipeline cycle completed successfully.")

    def _process_single_item(self, item):
        agency_id = item['agency']
        title = item['title']
        link = item['link']
        
        # Deduplication (use sanction-specific check for sanction agencies)
        if agency_id in ['FSS_SANCTION', 'FSS_MGMT_NOTICE']:
            if self._is_sanction_duplicate(link, agency_id):
                logger.debug(f"Skipping duplicate sanction: {title[:30]}...")
                return
        else:
            if self._is_duplicate(link):
                logger.debug(f"Skipping duplicate: {title[:30]}...")
                return

        logger.info(f"Processing: [{agency_id}] {title}")

        # Content Fetching
        agency_config = self.agency_map.get(agency_id)
        content = None
        if agency_config:
            content = self.scraper.fetch_content(link, agency_config)
            if content:
                item['content'] = content
            else:
                content = title + "\n" + item.get('description', '')

        # Analysis
        analysis_result = None
        if self.analyzer:
            try:
                analysis_result = self.analyzer.process(
                    {'title': title, 'content': content, 'description': item.get('description', '')},
                    agency_config.get('name', agency_id) if agency_config else agency_id,
                    category=item.get('category', 'press_release')
                )
                item['analysis_result'] = analysis_result
            except Exception as e:
                logger.error(f"Analysis failed: {e}")

        # Save
        item['analysis_result'] = analysis_result # Ensure it's set
        self._save_to_db(item)

        # Notify
        if self.notifier and analysis_result and analysis_result.get('analysis_status') == 'ANALYZED':
            a_name = agency_config.get('name', agency_id) if agency_config else agency_id
            logger.info("  > Sending Notification...")
            try:
                self.notifier.format_and_send(a_name, title, link, analysis_result)
            except Exception as e:
                logger.error(f"Notification failed: {e}")
