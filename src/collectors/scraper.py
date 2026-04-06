import requests
from bs4 import BeautifulSoup
import time
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import re
from config import settings

import urllib3

# Suppress InsecureRequestWarning for verify=False
if settings.SUPPRESS_SSL_WARNINGS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class ContentScraper:
    def __init__(self):
        # Use a very standard Chrome User-Agent
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive'
        }

    def fetch_list_items(self, agency_config: Dict, last_crawled_date: datetime = None) -> List[Dict]:
        """
        Fetches list of articles using HTML scraping with AUTOMATIC PAGINATION.
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

        import pytz
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)

        if last_crawled_date and last_crawled_date.tzinfo is None:
             last_crawled_date = kst.localize(last_crawled_date)

        # Max cutoff: never collect older than 7 days (even if DB was cleared)
        max_cutoff = now_kst - timedelta(days=7)

        if last_crawled_date:
            # Use the more recent of: (last_crawled - 1 day) or (now - 7 days)
            cutoff_date = max(last_crawled_date - timedelta(days=1), max_cutoff)
            logger.info(f"[{agency_config.get('code')}] Incremental: > {cutoff_date.strftime('%Y-%m-%d')}")
        else:
            cutoff_date = max_cutoff
            logger.info(f"[{agency_config.get('code')}] Full Scan (7d): > {cutoff_date.strftime('%Y-%m-%d')}")

        all_items = []
        page = 1
        max_pages = 15

        while page <= max_pages:
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

            logger.info(f"  [{agency_config.get('code')}] Page {page} fetching...")

            try:
                time.sleep(random.uniform(settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX))
                response = requests.get(current_url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=settings.SSL_VERIFY)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                rows = soup.select(list_selector)
                
                if not rows:
                    if page == 1:
                        logger.warning(f"[{agency_config.get('code')}] No items found on Page 1 (Selector: {list_selector})")
                    else:
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

    def fetch_content(self, url: str, agency_config: Dict) -> Optional[str]:
        """
        Fetches article content based on agency configuration (selectors).
        """
        scraper_config = agency_config.get('scraper') or agency_config.get('selector')
        if not scraper_config:
            logger.debug(f"No scraper/selector config for {agency_config.get('code')}")
            return None
        
        try:
            # Random delay
            time.sleep(random.uniform(settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX))
            
            response = requests.get(url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=settings.SSL_VERIFY)
            response.raise_for_status()
            
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
            
            # Extract text
            text_content = content_div.get_text(separator='\n', strip=True)
            
            # 🛡️ Data Integrity Check: Short Content Warning
            # Instead of failing, we tag it so analysis can decide what to do
            if len(text_content) < 50:
                logger.warning(f"⚠️ Short content detected ({len(text_content)} chars) for {url}")
                return f"[Short Content] {text_content}"
                
            return text_content

        except Exception as e:
            logger.error(f"Error scraping content from {url}: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Helper to parse various date formats and ENFORCE KST (UTC+9).
        """
        if not date_str:
            return None
            
        try:
            import pytz
            import re
            
            # KST Timezone Definition
            kst = pytz.timezone('Asia/Seoul')
            
            # Try format: YYYYMMDD (no separator, used by FSS sanction notices)
            match_no_sep = re.search(r'^(\d{8})$', date_str.strip())
            if match_no_sep:
                dt = datetime.strptime(match_no_sep.group(1), '%Y%m%d')
                return kst.localize(dt)
            
            # Try format: YYYY-MM-DD or YYYY.MM.DD
            match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_str)
            
            clean_date_str = ""
            if match:
                clean_date_str = match.group(1).replace('.', '-')
            else:
                clean_date_str = date_str.strip().replace('.', '-')
            
            # Parse naïve datetime
            dt = datetime.strptime(clean_date_str, '%Y-%m-%d')
            
            # Localize to KST (Midnight KST)
            # This ensures 2024-12-25 00:00:00 KST
            dt_kst = kst.localize(dt)
            
            return dt_kst
            
        except ValueError:
            return None

    def fetch_sanction_items(self, agency_config: Dict) -> List[Dict]:
        """
        Fetches sanction notice items from FSS.
        This method is specifically for FSS_SANCTION and FSS_MGMT_NOTICE.
        Filters by bank/financial holding/NH keywords and excludes savings banks.
        
        Returns list of items with pdf_url field for direct PDF access.
        """
        code = agency_config.get('code', '')
        
        # Only process sanction notice agencies
        if code not in ['FSS_SANCTION', 'FSS_MGMT_NOTICE']:
            return []
        
        base_url = agency_config.get('url')
        base_domain = agency_config.get('base_url', 'https://www.fss.or.kr')
        filter_keywords = agency_config.get('filter_keywords', [])
        exclude_keywords = agency_config.get('exclude_keywords', [])
        
        if not base_url:
            logger.error(f"[{code}] Missing URL.")
            return []
        
        import pytz
        from urllib.parse import urljoin
        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        cutoff_date = now_kst - timedelta(days=30)  # Sanctions are less frequent, use 30 days
        
        # Build URL with date parameters
        today_str = now_kst.strftime('%Y-%m-%d')
        week_ago_str = cutoff_date.strftime('%Y-%m-%d')
        
        sep = "&" if "?" in base_url else "?"
        full_url = f"{base_url}{sep}sdate={week_ago_str}&edate={today_str}"
        
        logger.info(f"[{code}] Fetching sanction notices from {full_url}")
        
        all_items = []
        page = 1
        max_pages = 10
        
        while page <= max_pages:
            page_url = f"{full_url}&pageIndex={page}"
            
            try:
                time.sleep(random.uniform(1.0, 2.0))
                response = requests.get(page_url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=settings.SSL_VERIFY)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all list items (table rows)
                items = soup.select('tbody tr')
                
                if not items:
                    logger.info(f"  [{code}] No items found on page {page}. Stopping.")
                    break
                
                page_items = []
                
                for item in items:
                    try:
                        # Extract institution name (제재대상기관) - 2nd column
                        inst_elem = item.select_one('td:nth-child(2)')
                        if not inst_elem:
                            continue
                        
                        # Remove mobile-only spans and get clean text
                        for span in inst_elem.select('span.only-m'):
                            span.decompose()
                        institution = inst_elem.get_text(strip=True)
                        
                        if not institution:
                            continue
                        
                        # Apply filter: must contain at least one filter keyword
                        if filter_keywords:
                            if not any(kw in institution for kw in filter_keywords):
                                continue
                        
                        # Apply exclude: must not contain any exclude keyword
                        if exclude_keywords:
                            if any(kw in institution for kw in exclude_keywords):
                                continue
                        
                        # Extract date (제재조치요구일) - 3rd column
                        date_elem = item.select_one('td:nth-child(3)')
                        date_str = ""
                        if date_elem:
                            for span in date_elem.select('span.only-m'):
                                span.decompose()
                            date_str = date_elem.get_text(strip=True)
                        
                        # Extract link to detail page or PDF - 4th column
                        link_elem = item.select_one('td:nth-child(4) a')
                        if not link_elem:
                            link_elem = item.select_one('a[href*="view.do"]')
                        if not link_elem:
                            link_elem = item.select_one('a[href*="hpdownload"]')
                        
                        if link_elem:
                            href = link_elem.get('href', '')
                            if not href.startswith('http'):
                                link = urljoin(base_domain, href)
                            else:
                                link = href
                        else:
                            continue
                        
                        # Parse date
                        pub_date = self._parse_date(date_str)
                        if not pub_date:
                            pub_date = now_kst
                        
                        # Check if PDF link (경영유의사항 has direct PDF links)
                        pdf_url = None
                        if 'hpdownload' in link:
                            pdf_url = link
                        else:
                            # Need to fetch detail page to get PDF (검사결과 제재)
                            pdf_url = self._extract_pdf_from_detail(link, base_domain)
                        
                        page_items.append({
                            'title': institution,
                            'link': link,
                            'published_at': pub_date.isoformat(),
                            'agency': code,
                            'category': 'sanction_notice',
                            'pdf_url': pdf_url
                        })
                        
                    except Exception as e:
                        logger.error(f"Error parsing sanction item: {e}")
                        continue
                
                if page_items:
                    all_items.extend(page_items)
                    logger.info(f"  [{code}] Found {len(page_items)} matching items on page {page}.")
                
                if len(items) < 5:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"[{code}] Error fetching page {page}: {e}")
                break
        
        logger.info(f"[{code}] Total collected: {len(all_items)} sanction notices.")
        return all_items

    def _extract_pdf_from_detail(self, detail_url: str, base_domain: str) -> Optional[str]:
        """
        Fetches detail page and extracts PDF download link.
        """
        try:
            time.sleep(random.uniform(0.5, 1.0))
            response = requests.get(detail_url, headers=self.headers, timeout=settings.SCRAPER_TIMEOUT, verify=settings.SSL_VERIFY)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find PDF download link
            pdf_link = soup.select_one('a[href*="hpdownload"]')
            if pdf_link:
                href = pdf_link.get('href', '')
                if not href.startswith('http'):
                    from urllib.parse import urljoin
                    return urljoin(base_domain, href)
                return href
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not extract PDF from {detail_url}: {e}")
            return None

if __name__ == "__main__":
    # Test with a real URL (using FSC item if available or hardcoded)
    test_agency = {
        "id": "TestFSC",
        "scraper": {
            "container_selector": "#content", # Example selector, might need adjustment based on real site
            "remove_selectors": [".file_list", ".btn_area"]
        }
    }
    # Note: Using a placeholder URL for test. In real usage, we pass real URLs.
    print("Scraper module ready.")
