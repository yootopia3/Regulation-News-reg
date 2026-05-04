"""FSS sanction notice scraper."""

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from src.config import settings
from src.config.agency_codes import PublishedAtSource
from src.config.agency_loader import get_ssl_verify, is_sanction_agency
from src.collectors import http
from src.collectors.date_parser import KST, has_specific_time, parse_date


logger = logging.getLogger(__name__)


# Hard ceiling on sanction list pagination. FSS 의 검사결과 제재 / 경영유의사항
# 페이지는 한 번의 search window (sdate~edate, default 30 일) 안에서
# 보통 5~10 페이지를 넘지 않는다. 10 으로 캡 두어 사이트 레이아웃 변경이나
# 필터 누락으로 인한 무한 루프를 차단한다 (방어적 ceiling).
MAX_PAGES = 10

# Lookback window for the sanction search query (sdate=today-CUTOFF_DAYS).
# 제재 공시는 저빈도 + 백필이 잦아서 일반 보도자료(7 일) 보다 길게 본다.
# 30 일은 새 게시물을 놓치지 않으면서 전체 아카이브를 매번 다시 긁지 않을
# 수 있는 minimum 윈도다 (round 1 §2 회귀 정책과 일치).
CUTOFF_DAYS = 30


def extract_sanction_key(link: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract ``(examMgmtNo, emOpenSeq)`` from an FSS sanction link.

    FSS sanction URLs contain varying date params so identity must be
    derived from the ``examMgmtNo``/``emOpenSeq`` query pair. Returns
    ``(None, None)`` when either identifier is missing (e.g. PDF links).
    """
    try:
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        exam_id = params.get('examMgmtNo', [None])[0]
        seq = params.get('emOpenSeq', [None])[0]
        return exam_id, seq
    except Exception:
        return None, None


def fetch_sanction_items(agency_config: Dict) -> List[Dict]:
    """Fetch sanction notice items from FSS.

    Specifically for FSS_SANCTION and FSS_MGMT_NOTICE.
    Filters by bank/financial holding/NH keywords and excludes savings banks.

    Returns list of items with `pdf_url` field for direct PDF access.
    """
    code = agency_config.get('code', '')

    if not is_sanction_agency(code):
        return []

    base_url = agency_config.get('url')
    base_domain = agency_config.get('base_url', 'https://www.fss.or.kr')
    filter_keywords = agency_config.get('filter_keywords', [])
    exclude_keywords = agency_config.get('exclude_keywords', [])

    if not base_url:
        logger.error(f"[{code}] Missing URL.")
        return []

    now_kst = datetime.now(KST)
    cutoff_date = now_kst - timedelta(days=CUTOFF_DAYS)

    today_str = now_kst.strftime('%Y-%m-%d')
    week_ago_str = cutoff_date.strftime('%Y-%m-%d')

    sep = "&" if "?" in base_url else "?"
    full_url = f"{base_url}{sep}sdate={week_ago_str}&edate={today_str}"

    logger.info(f"[{code}] Fetching sanction notices from {full_url}")

    all_items: List[Dict] = []
    page = 1

    while page <= MAX_PAGES:
        page_url = f"{full_url}&pageIndex={page}"

        try:
            time.sleep(random.uniform(1.0, 2.0))
            response = http.fetch(page_url, verify=get_ssl_verify(code))

            soup = BeautifulSoup(response.content, 'html.parser')

            items = soup.select('tbody tr')

            if not items:
                logger.info(f"  [{code}] No items found on page {page}. Stopping.")
                break

            page_items: List[Dict] = []

            for item in items:
                try:
                    # Extract institution name (제재대상기관) - 2nd column
                    inst_elem = item.select_one('td:nth-child(2)')
                    if not inst_elem:
                        continue

                    for span in inst_elem.select('span.only-m'):
                        span.decompose()
                    institution = inst_elem.get_text(strip=True)

                    if not institution:
                        continue

                    if filter_keywords:
                        if not any(kw in institution for kw in filter_keywords):
                            continue

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

                    pub_date = parse_date(date_str)
                    if pub_date and has_specific_time(date_str):
                        published_at_source = PublishedAtSource.SOURCE.value
                    else:
                        pub_date = now_kst
                        published_at_source = PublishedAtSource.COLLECTED_FALLBACK.value

                    # 경영유의사항 has direct PDF links
                    if 'hpdownload' in link:
                        pdf_url = link
                    else:
                        # Need to fetch detail page to get PDF (검사결과 제재)
                        pdf_url = extract_pdf_from_detail(link, base_domain)

                    page_items.append({
                        'title': institution,
                        'link': link,
                        'published_at': pub_date.isoformat(),
                        'published_at_source': published_at_source,
                        'agency': code,
                        'category': 'sanction_notice',
                        'pdf_url': pdf_url,
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


def extract_pdf_from_detail(detail_url: str, base_domain: str) -> Optional[str]:
    """Fetch detail page and extract the PDF download link."""
    try:
        time.sleep(random.uniform(0.5, 1.0))
        response = http.fetch(detail_url)

        soup = BeautifulSoup(response.content, 'html.parser')

        pdf_link = soup.select_one('a[href*="hpdownload"]')
        if pdf_link:
            href = pdf_link.get('href', '')
            if not href.startswith('http'):
                return urljoin(base_domain, href)
            return href

        return None

    except Exception as e:
        logger.debug(f"Could not extract PDF from {detail_url}: {e}")
        return None
