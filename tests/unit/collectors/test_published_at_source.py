"""Collector tests for ``published_at_source`` propagation."""

from datetime import datetime

import pytest

from src.collectors import list_scraper, rss_parser, sanction_scraper
from src.collectors.date_parser import KST
from src.config.agency_codes import PublishedAtSource


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


def _rss_xml(date_text: str) -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rss version="2.0"><channel><title>Test</title>'
        + (
            "<item><title>RSS Item</title>"
            "<link>https://example.com/rss/1</link>"
            f"<pubDate>{date_text}</pubDate></item>"
        ).encode("utf-8")
        + b"</channel></rss>"
    )


def _list_config():
    return {
        "code": "FSC",
        "url": "https://example.com/list",
        "collection_method": "scraper",
        "selector": {"list": "li.item", "title": "a", "date": ".date"},
    }


def _list_html(date_text: str) -> bytes:
    return (
        "<ul><li class='item'>"
        "<a href='/detail/1'>List Item</a>"
        f"<span class='date'>{date_text}</span>"
        "</li></ul>"
    ).encode("utf-8")


def _sanction_config():
    return {
        "code": "FSS_SANCTION",
        "url": "https://www.fss.or.kr/fss/list.do",
        "base_url": "https://www.fss.or.kr",
        "filter_keywords": ["은행"],
        "exclude_keywords": ["저축은행"],
    }


def _sanction_html(date_text: str) -> bytes:
    return (
        "<table><tbody><tr>"
        "<td>1</td><td>국민은행</td>"
        f"<td>{date_text}</td>"
        "<td><a href='/fss/hpdownload?file=1'>PDF</a></td>"
        "</tr></tbody></table>"
    ).encode("utf-8")


def _today_dash() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def _today_compact() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


@pytest.mark.parametrize(
    ("date_text", "expected_source"),
    [
        ("Tue, 05 May 2026 09:00:00 +0900", PublishedAtSource.SOURCE.value),
        ("Tue, 05 May 2026 00:00:00 +0900", PublishedAtSource.COLLECTED_FALLBACK.value),
        ("not a date", PublishedAtSource.COLLECTED_FALLBACK.value),
    ],
)
def test_rss_items_include_published_at_source(
    monkeypatch, date_text, expected_source
):
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: _Response(_rss_xml(date_text)),
    )

    items = rss_parser.fetch_rss_feed(
        {
            "code": "FSC",
            "name": "Financial Services Commission",
            "url": "https://example.com/rss",
            "collection_method": "rss",
        }
    )

    assert len(items) == 1
    assert items[0]["published_at_source"] == expected_source


@pytest.mark.parametrize(
    ("date_text", "expected_source"),
    [
        (_today_dash(), PublishedAtSource.COLLECTED_FALLBACK.value),
        ("not a date", PublishedAtSource.COLLECTED_FALLBACK.value),
    ],
)
def test_list_items_include_published_at_source(
    monkeypatch, date_text, expected_source
):
    monkeypatch.setattr(list_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        list_scraper.http,
        "fetch",
        lambda *args, **kwargs: _Response(_list_html(date_text)),
    )

    items = list_scraper.fetch_list_items(_list_config())

    assert len(items) == 1
    assert items[0]["published_at_source"] == expected_source


@pytest.mark.parametrize(
    ("date_text", "expected_source"),
    [
        (_today_compact(), PublishedAtSource.COLLECTED_FALLBACK.value),
        ("not a date", PublishedAtSource.COLLECTED_FALLBACK.value),
    ],
)
def test_sanction_items_include_published_at_source(
    monkeypatch, date_text, expected_source
):
    monkeypatch.setattr(sanction_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        sanction_scraper.http,
        "fetch",
        lambda *args, **kwargs: _Response(_sanction_html(date_text)),
    )

    items = sanction_scraper.fetch_sanction_items(_sanction_config())

    assert len(items) == 1
    assert items[0]["published_at_source"] == expected_source
