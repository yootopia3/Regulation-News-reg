import sys
import os
import logging
import re
import time
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.pipeline import Pipeline
from src.collectors.scraper import ContentScraper
from src.utils.logger import setup_logger
from config import settings

# Setup Logger
logger = setup_logger("Backfill")

class BackfillScraper(ContentScraper):
    def __init__(self, days=60):
        super().__init__()
        self.backfill_days = days

    def fetch_list_items(self, agency_config, last_crawled_date=None):
        """
        Modified fetch_list_items for Deep Backfill (ignores 7-day safeguard)
        """
        base_url = agency_config.get('base_url') or agency_config.get('url')
        selectors = agency_config.get('selector', {})
        list_selector = selectors.get('list')
        
        if not base_url or not list_selector:
            logger.error(f"[{agency_config.get('code')}] Missing URL or list selector.")
            return []

        import pytz
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)

        # BACKFILL SPECIFIC: Set cutoff to X days ago
        cutoff_date = now_kst - timedelta(days=self.backfill_days)
        logger.info(f"[{agency_config.get('code')}] Backfill Target: > {cutoff_date.strftime('%Y-%m-%d')}")

        all_items = []
        page = 1
        max_pages = 50 # Increased for backfill

        while page <= max_pages:
            # URL Construction
            if "fsc.go.kr" in base_url:
                page_param = f"curPage={page}"
                sep = "&" if "?" in base_url else "?"
                if "curPage=" in base_url:
                    current_url = re.sub(r'curPage=\d+', page_param, base_url)
                else:
                    current_url = f"{base_url}{sep}{page_param}"
            else:
                page_param = f"pageIndex={page}"
                sep = "&" if "?" in base_url else "?"
                if "pageIndex=" in base_url:
                    current_url = re.sub(r'pageIndex=\d+', page_param, base_url)
                else:
                    current_url = f"{base_url}{sep}{page_param}"

            logger.info(f"  [{agency_config.get('code')}] Page {page} fetching... {current_url}")

            try:
                time.sleep(random.uniform(1.0, 2.0)) # Polite delay
                response = requests.get(current_url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=False)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                rows = soup.select(list_selector)
                
                if not rows:
                    logger.info(f"  [{agency_config.get('code')}] Page {page} empty. Stopping.")
                    break
                
                page_items = []
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
                                from urllib.parse import urljoin
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

                        pub_date = self._parse_date(date_str)
                        
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
                                # Found an item older than cutoff
                                logger.info(f"    > Hit older item: {pub_date.strftime('%Y-%m-%d')}. Stopping.")
                                reached_cutoff = True
                        else:
                            # If no date, assume new (or skip?) - safeguard: assume today but don't break
                           pass

                    except Exception as e:
                        logger.error(f"Error parsing row: {e}")
                        continue
                
                if page_items:
                    all_items.extend(page_items)
                    logger.info(f"    > Found {len(page_items)} items on Page {page}.")
                
                if reached_cutoff:
                    break
                
                page += 1

            except Exception as e:
                logger.error(f"[{agency_config.get('code')}] Error fetching page {page}: {e}")
                break

        return all_items

import requests
from bs4 import BeautifulSoup
import feedparser

class BackfillPipeline(Pipeline):
    def __init__(self, target_days=60):
        config_path = os.path.join(project_root, 'config', 'agencies.json')
        super().__init__(config_path)
        self.scraper = BackfillScraper(days=target_days)
        self.target_days = target_days
    
    def run(self):
        """
        Run backfill for all agencies
        """
        logger.info(f"Starting {self.target_days}-Day Backfill Pipeline...")
        
        all_articles = []
        
        for code, config in self.agency_map.items():
            logger.info(f"Processing {code}...")
            collected = []
            
            try:
                if config.get('collection_method') == 'rss':
                    # RSS - Just fetch validation, RSS usually limited
                    logger.info(f"  > RSS Mode for {code}")
                    try:
                        url = config.get('url')
                        feed = feedparser.parse(url)
                        logger.info(f"    > RSS Entries found: {len(feed.entries)}")
                        for entry in feed.entries:
                             # Basic parsing
                             collected.append({
                                 'title': entry.title,
                                 'link': entry.link,
                                 'published_at':  datetime.now().isoformat(), # RSS doesn't always have valid date, use NOW or parse
                                 'agency': code,
                                 'category': config.get('category'),
                                 'content': entry.get('description', '')
                             })
                    except Exception as e:
                        logger.error(f"RSS Fetch Error: {e}")

                else:
                    # Scraper Mode - Deep Backfill
                    collected = self.scraper.fetch_list_items(config)
                    
                    # Detail Fetch
                    details = []
                    logger.info(f"  > Fetching details for {len(collected)} items...")
                    for i, item in enumerate(collected):
                       try:
                           if i % 10 == 0: print(f"    ... {i}/{len(collected)}")
                           content = self.scraper.fetch_content(item['link'], config)
                           item['content'] = content if content else ""
                           details.append(item)
                       except Exception as e:
                           logger.error(f"Failed to fetch content for {item['link']}: {e}")
                    collected = details
                
                all_articles.extend(collected)
                logger.info(f"  > {code}: Collected {len(collected)} items.")
                
            except Exception as e:
                logger.error(f"Failed to process {code}: {e}")
        
        logger.info(f"Total Collected: {len(all_articles)} articles.")
        
        # Save & Analyze
        if all_articles:
             logger.info("Saving raw articles to Supabase...")
             new_count = 0
             skip_count = 0
             for article in all_articles:
                 try:
                     link = article.get('link')
                     
                     # Check if article already exists (to avoid overwriting analysis_result)
                     existing = self.supabase.table('articles').select('id').eq('link', link).execute()
                     
                     if existing.data:
                         # Already exists - skip to preserve existing data
                         skip_count += 1
                         continue
                     
                     # New article - insert
                     record = {
                         'agency': article.get('agency'),
                         'title': article.get('title'),
                         'content': article.get('content') or '',
                         'published_at': article.get('published_at'),
                         'link': link,
                         'category': article.get('category'),
                     }
                     self.supabase.table('articles').insert(record).execute()
                     new_count += 1
                 except Exception as e:
                     logger.error(f"DB Save Error: {e}")
             
             logger.info(f"Save Complete. New: {new_count}, Skipped (existing): {skip_count}")
             
             logger.info("Raw Save Complete. Starting Analysis...")
             
             # Re-read from DB to get IDs if needed or just use Analyzer
             for i, article in enumerate(all_articles):
                if i % 10 == 0: logger.info(f"Analyzing {i}/{len(all_articles)}...")
                
                # Check duplication/existing analysis
                # Ideally we check if analyzed already? 
                # For backfill we just run it.
                
                try:
                    if self.analyzer:
                        analysis = self.analyzer.process(
                            {'title': article['title'], 'content': article['content']},
                            article['agency'],
                            category=article.get('category')
                        )
                        if analysis:
                            self.supabase.table('articles').update({
                                'analysis_result': analysis
                            }).eq('link', article['link']).execute()
                except Exception as e:
                    logger.error(f"Analysis Failed for {article.get('title')}: {e}")

        logger.info("Backfill Complete.")

if __name__ == "__main__":
    # Disable verify warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    pipeline = BackfillPipeline(target_days=60)
    pipeline.run()
