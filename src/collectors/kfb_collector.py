"""Korea Federation of Banks press-release collector.

KFB does not expose a fixed feed URL in our config. The collector therefore
discovers official RSS/Atom links from the press page first, validates the
candidate XML feed, and falls back to HTML list scraping when no usable feed
or feed entries are available.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from xml.etree import ElementTree

import feedparser
from bs4 import BeautifulSoup

from src.collectors import http
from src.collectors.date_parser import KST, has_specific_time, parse_date
from src.collectors.rss_parser import parse_date as parse_rss_date
from src.config.agency_codes import ArticleCategory, PublishedAtSource
from src.config.agency_loader import get_ssl_verify


logger = logging.getLogger(__name__)

KFB_CODE = "KFB"
KFB_NAME = "은행연합회"
KFB_SUBCATEGORY = "bank_association_press"
FEED_TYPES = {"application/rss+xml", "application/atom+xml"}
MAX_HTML_ITEMS = 30
DEFAULT_HTML_LOOKBACK_DAYS = 30
DEFAULT_FALLBACK_URLS = [
    "https://www.kfb.or.kr/news/info_news.php",
    "http://m.kfb.or.kr/news/info_news.php",
    "http://www.kfb.or.kr/news/info_news.php",
]


def _with_kfb_metadata(item: Dict) -> Dict:
    link = item["link"]
    return {
        **item,
        "agency": KFB_CODE,
        "source_org": KFB_CODE,
        "source_name": KFB_NAME,
        "category": ArticleCategory.PRESS_RELEASE.value,
        "subcategory": KFB_SUBCATEGORY,
        "dedup_key": f"{KFB_CODE}:{link}",
    }


def _feed_root_name(content: bytes) -> Optional[str]:
    try:
        root = ElementTree.fromstring(content.strip())
    except ElementTree.ParseError:
        return None
    return root.tag.rsplit("}", 1)[-1].lower()


def _is_valid_feed_response(content: bytes) -> bool:
    return _feed_root_name(content) in {"rss", "feed"}


def _candidate_feed_urls(page_url: str, html: bytes) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: List[str] = []
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        if isinstance(rel, str):
            rel_values = {rel.lower()}
        else:
            rel_values = {str(value).lower() for value in rel}
        type_value = str(link.get("type") or "").lower()
        href = link.get("href")
        if "alternate" not in rel_values or type_value not in FEED_TYPES or not href:
            continue
        urls.append(urljoin(page_url, href))
    return urls


def discover_rss_feed(page_url: str, html: bytes, agency_config: Dict) -> Tuple[Optional[str], Optional[bytes]]:
    """Return the first valid official RSS/Atom URL discovered from HTML."""
    for candidate_url in _candidate_feed_urls(page_url, html):
        try:
            response = http.fetch(candidate_url, verify=get_ssl_verify(agency_config.get("code")))
        except Exception as exc:
            logger.warning("KFB RSS candidate failed: %s (%s)", candidate_url, exc)
            continue
        if _is_valid_feed_response(response.content):
            logger.info("KFB RSS URL discovered: %s", candidate_url)
            return candidate_url, response.content
        logger.warning("KFB RSS candidate is not RSS/Atom XML: %s", candidate_url)
    return None, None


def _parse_feed_items(feed_content: bytes) -> List[Dict]:
    feed = feedparser.parse(feed_content)
    items: List[Dict] = []
    for entry in feed.entries:
        title = str(entry.get("title") or "").strip()
        link = str(entry.get("link") or "").strip()
        if not title or not link:
            continue
        if link.startswith("http://"):
            link = "https://" + link[7:]

        published = str(entry.get("published") or entry.get("updated") or "")
        published_at = parse_rss_date(published)
        has_source_time = has_specific_time(published)

        if published_at and has_source_time:
            published_at_value = published_at.isoformat()
            source = PublishedAtSource.SOURCE.value
        else:
            published_at_value = datetime.now(KST).isoformat()
            source = PublishedAtSource.COLLECTED_FALLBACK.value

        description = str(entry.get("summary") or entry.get("description") or "").strip()
        items.append(
            _with_kfb_metadata(
                {
                    "title": title,
                    "link": link,
                    "published_at": published_at_value,
                    "published_at_source": source,
                    "source_published_at_str": published,
                    "description": BeautifulSoup(description, "html.parser").get_text(" ", strip=True),
                    "collection_source": "rss",
                }
            )
        )
    return items


def _extract_date_text(row_text: str) -> str:
    match = re.search(r"\d{4}[.-]\d{2}[.-]\d{2}", row_text)
    return match.group(0) if match else ""


def _text_without_date(text: str, date_text: str) -> str:
    if date_text:
        text = text.replace(date_text, "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_javascript_url(page_url: str, script_text: str) -> Optional[str]:
    if not script_text:
        return None
    url_match = re.search(r"""['"]([^'"]+\.php(?:\?[^'"]*)?)['"]""", script_text)
    if url_match:
        return urljoin(page_url, url_match.group(1))

    id_match = re.search(r"""['"]?(\d{2,})['"]?""", script_text)
    if id_match:
        separator = "&" if "?" in page_url else "?"
        return f"{page_url}{separator}idx={id_match.group(1)}"
    return None


def _extract_link(page_url: str, row, anchor) -> Optional[str]:
    href = anchor.get("href") or ""
    if href and not href.startswith("#") and not href.lower().startswith("javascript:"):
        return urljoin(page_url, href)

    for raw in (href, anchor.get("onclick") or "", row.get("onclick") or ""):
        extracted = _extract_javascript_url(page_url, raw)
        if extracted:
            return extracted
    return None


def _parse_html_items(page_url: str, html: bytes, agency_config: Dict, last_crawled_date=None) -> List[Dict]:
    selectors = agency_config.get("selector", {})
    list_selector = selectors.get("list") or "table tbody tr, .board_list li, .bbs-list li, .list li"
    title_selector = selectors.get("title") or "a"
    date_selector = selectors.get("date")
    lookback_days = int(agency_config.get("lookback_days", DEFAULT_HTML_LOOKBACK_DAYS))

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(list_selector)
    if not rows:
        rows = soup.select("a[href]")
    now_kst = datetime.now(KST)
    cutoff_date = now_kst - timedelta(days=lookback_days)
    if last_crawled_date:
        cutoff_date = max(last_crawled_date - timedelta(days=1), cutoff_date)
    logger.info("KFB HTML fallback rows: %s, cutoff: %s", len(rows), cutoff_date.date().isoformat())

    items: List[Dict] = []
    seen_links = set()
    skipped_no_anchor = 0
    skipped_no_link = 0
    skipped_no_date = 0
    skipped_old = 0
    skipped_no_title = 0
    for row in rows:
        anchor = row if getattr(row, "name", None) == "a" else row.select_one(title_selector)
        if not anchor:
            skipped_no_anchor += 1
            continue
        link = _extract_link(page_url, row, anchor)
        if not link:
            skipped_no_link += 1
            continue

        if link in seen_links:
            continue
        seen_links.add(link)

        date_text = ""
        if date_selector:
            date_el = row.select_one(date_selector)
            if date_el:
                date_text = date_el.get_text(" ", strip=True)
        if not date_text:
            row_text = row.get_text(" ", strip=True)
            parent_text = row.parent.get_text(" ", strip=True) if row.parent else ""
            date_text = _extract_date_text(f"{row_text} {parent_text}")
        if getattr(row, "name", None) == "a" and not date_text:
            skipped_no_date += 1
            continue

        title = anchor.get_text(" ", strip=True) or _text_without_date(row.get_text(" ", strip=True), date_text)
        if not title:
            skipped_no_title += 1
            continue

        published_at = parse_date(date_text)
        if published_at and published_at < cutoff_date:
            skipped_old += 1
            continue

        has_source_time = has_specific_time(date_text)
        items.append(
            _with_kfb_metadata(
                {
                    "title": title,
                    "link": link,
                    "published_at": (published_at if published_at and has_source_time else now_kst).isoformat(),
                    "published_at_source": (
                        PublishedAtSource.SOURCE.value
                        if published_at and has_source_time
                        else PublishedAtSource.COLLECTED_FALLBACK.value
                    ),
                    "source_published_at_str": date_text,
                    "collection_source": "html",
                }
            )
        )
        if len(items) >= MAX_HTML_ITEMS:
            break

    logger.info(
        "KFB HTML fallback skipped rows: no_anchor=%s, no_link=%s, no_date=%s, old=%s, no_title=%s",
        skipped_no_anchor,
        skipped_no_link,
        skipped_no_date,
        skipped_old,
        skipped_no_title,
    )
    return items


def _candidate_page_urls(primary_url: str, agency_config: Dict) -> List[str]:
    urls: List[str] = [primary_url]
    for candidate in agency_config.get("fallback_urls", DEFAULT_FALLBACK_URLS):
        if candidate not in urls:
            urls.append(candidate)
    return urls


def _fetch_press_page(agency_config: Dict) -> Tuple[Optional[str], Optional[bytes]]:
    primary_url = agency_config.get("url")
    if not primary_url:
        logger.error("[KFB] Missing base press-release URL.")
        return None, None

    last_error: Optional[Exception] = None
    for candidate_url in _candidate_page_urls(primary_url, agency_config):
        try:
            response = http.fetch(candidate_url, verify=get_ssl_verify(agency_config.get("code")))
            if candidate_url != primary_url:
                logger.info("KFB press page fallback URL used: %s", candidate_url)
            return candidate_url, response.content
        except Exception as exc:
            last_error = exc
            logger.warning("[KFB] Failed to fetch press-release candidate %s: %s", candidate_url, exc)

    logger.error("[KFB] Failed to fetch press-release page: %s", last_error)
    return None, None


def collect_kfb_rss_first(agency_config: Dict, last_crawled_date=None) -> List[Dict]:
    """Collect KFB press releases using RSS/Atom first and HTML as fallback."""
    page_url, page_content = _fetch_press_page(agency_config)
    if not page_url or not page_content:
        return []

    rss_url, rss_content = discover_rss_feed(page_url, page_content, agency_config)
    if rss_url and rss_content:
        items = _parse_feed_items(rss_content)
        logger.info("KFB collection method: rss")
        if items:
            logger.info("KFB collected %s items via RSS.", len(items))
            return items
        logger.info("KFB RSS has no latest entries, fallback to HTML crawling")
    else:
        logger.info("KFB RSS not found, fallback to HTML crawling")

    items = _parse_html_items(page_url, page_content, agency_config, last_crawled_date)
    logger.info("KFB collection method: html")
    logger.info("KFB collected %s items via HTML.", len(items))
    return items
