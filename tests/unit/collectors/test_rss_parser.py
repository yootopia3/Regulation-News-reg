"""Unit tests for `src.collectors.rss_parser`.

These tests exercise `parse_date` and `fetch_rss_feed` without touching
the network. `requests.get` and `time.sleep` are monkeypatched; feedparser
runs for real against inline RSS XML so we preserve the real parser path.
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
import requests as real_requests

from src.collectors import rss_parser
from src.collectors.rss_parser import (
    KST,
    RSS_FETCH_MAX_ATTEMPTS,
    RSS_STALE_WARN_DAYS,
    fetch_rss_feed,
    parse_date,
)


RSS_LOGGER = "src.collectors.rss_parser"


def _rss_xml(entries_xml: str) -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rss version="2.0"><channel><title>Test</title>'
        + entries_xml.encode("utf-8")
        + b"</channel></rss>"
    )


def _rfc822(dt: datetime) -> str:
    # e.g. "Tue, 08 Apr 2026 09:00:00 +0900"
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _make_response(content: bytes, status_code: int = 200, raise_exc: Exception = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    if raise_exc is not None:
        resp.raise_for_status = MagicMock(side_effect=raise_exc)
    else:
        resp.raise_for_status = MagicMock(return_value=None)
    return resp


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_parses_rfc822_success(self):
        result = parse_date("Tue, 03 Apr 2026 14:30:00 +0900")
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 3
        assert result.hour == 14
        assert result.tzinfo is not None
        # parse_date returns KST-aware datetime
        assert result.utcoffset() == timedelta(hours=9)

    def test_returns_none_on_empty_string(self):
        assert parse_date("") is None

    def test_returns_none_on_none(self):
        assert parse_date(None) is None

    def test_returns_none_on_garbage(self):
        assert parse_date("not a date") is None


# ---------------------------------------------------------------------------
# fetch_rss_feed
# ---------------------------------------------------------------------------


@pytest.fixture
def no_sleep(monkeypatch):
    """Skip retry backoff to keep test suite fast."""
    monkeypatch.setattr("time.sleep", lambda s: None)


@pytest.fixture
def fresh_agency():
    return {
        "code": "TEST",
        "name": "Test Agency",
        "url": "https://example.com/rss",
        "collection_method": "rss",
    }


def _fresh_rss(now: datetime) -> bytes:
    entries = (
        f"<item><title>Item A</title><link>https://example.com/a</link>"
        f"<pubDate>{_rfc822(now)}</pubDate></item>"
        f"<item><title>Item B</title><link>https://example.com/b</link>"
        f"<pubDate>{_rfc822(now - timedelta(hours=2))}</pubDate></item>"
    )
    return _rss_xml(entries)


class TestFetchRssFeed:
    def test_success_returns_parsed_items(self, monkeypatch, no_sleep, fresh_agency):
        now = datetime.now(KST)
        xml = _fresh_rss(now)

        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return _make_response(xml)

        monkeypatch.setattr("requests.get", fake_get)

        items = fetch_rss_feed(fresh_agency)

        assert len(items) == 2
        assert len(calls) == 1
        titles = [item["title"] for item in items]
        assert "Item A" in titles
        assert "Item B" in titles
        for item in items:
            assert item["agency"] == "TEST"
            assert item["link"].startswith("https://example.com/")
            assert item["published_at"]  # non-empty ISO string

    def test_scraper_method_returns_empty_without_network(self, monkeypatch):
        # Poison requests.get: if it's called the test fails.
        def boom(*a, **kw):
            raise AssertionError("requests.get must not be called for scraper method")

        monkeypatch.setattr("requests.get", boom)

        agency = {
            "code": "SCRP",
            "name": "Scraper Agency",
            "url": "https://example.com/page",
            "collection_method": "scraper",
        }
        assert fetch_rss_feed(agency) == []

    def test_retry_succeeds_after_connection_error(
        self, monkeypatch, no_sleep, fresh_agency
    ):
        now = datetime.now(KST)
        xml = _fresh_rss(now)

        call_count = {"n": 0}

        def fake_get(url, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise real_requests.exceptions.ConnectionError("transient RST")
            return _make_response(xml)

        monkeypatch.setattr("requests.get", fake_get)

        items = fetch_rss_feed(fresh_agency)
        assert len(items) == 2
        assert call_count["n"] == 2

    def test_retry_exhausted_returns_empty(
        self, monkeypatch, no_sleep, fresh_agency
    ):
        call_count = {"n": 0}

        def fake_get(url, **kwargs):
            call_count["n"] += 1
            raise real_requests.exceptions.ConnectionError("always fails")

        monkeypatch.setattr("requests.get", fake_get)

        items = fetch_rss_feed(fresh_agency)
        assert items == []
        assert call_count["n"] == RSS_FETCH_MAX_ATTEMPTS

    def test_http_error_not_retried(self, monkeypatch, no_sleep, fresh_agency):
        call_count = {"n": 0}

        def fake_get(url, **kwargs):
            call_count["n"] += 1
            return _make_response(
                b"<html>404</html>",
                status_code=404,
                raise_exc=real_requests.exceptions.HTTPError("404 Not Found"),
            )

        monkeypatch.setattr("requests.get", fake_get)

        items = fetch_rss_feed(fresh_agency)
        assert items == []
        # HTTP errors are final — exactly one attempt.
        assert call_count["n"] == 1

    def test_stale_warning_triggered(
        self, monkeypatch, no_sleep, caplog, fresh_agency
    ):
        # All entries older than the stale threshold.
        stale_when = datetime.now(KST) - timedelta(days=RSS_STALE_WARN_DAYS + 5)
        entries = (
            f"<item><title>Old A</title><link>https://example.com/a</link>"
            f"<pubDate>{_rfc822(stale_when)}</pubDate></item>"
            f"<item><title>Old B</title><link>https://example.com/b</link>"
            f"<pubDate>{_rfc822(stale_when - timedelta(days=1))}</pubDate></item>"
        )
        xml = _rss_xml(entries)

        def fake_get(url, **kwargs):
            return _make_response(xml)

        monkeypatch.setattr("requests.get", fake_get)

        caplog.set_level(logging.WARNING, logger=RSS_LOGGER)
        items = fetch_rss_feed(fresh_agency)

        assert len(items) == 2
        assert any("[STALE RSS]" in rec.message for rec in caplog.records)

    def test_stale_warning_not_triggered_when_fresh(
        self, monkeypatch, no_sleep, caplog, fresh_agency
    ):
        now = datetime.now(KST)
        xml = _fresh_rss(now)

        def fake_get(url, **kwargs):
            return _make_response(xml)

        monkeypatch.setattr("requests.get", fake_get)

        caplog.set_level(logging.WARNING, logger=RSS_LOGGER)
        items = fetch_rss_feed(fresh_agency)

        assert len(items) == 2
        assert not any("[STALE RSS]" in rec.message for rec in caplog.records)

    def test_fsc_fallback_date_format_parses(
        self, monkeypatch, no_sleep, fresh_agency
    ):
        # FSC-style "YYYY-MM-DD HH:MM:SS" in <pubDate>. parse_date (RFC 822)
        # will fail; fetch_rss_feed's strptime fallback should pick it up.
        entries = (
            "<item><title>FSC</title><link>https://example.com/fsc</link>"
            "<pubDate>2026-04-02 09:00:00</pubDate></item>"
        )
        xml = _rss_xml(entries)

        def fake_get(url, **kwargs):
            return _make_response(xml)

        monkeypatch.setattr("requests.get", fake_get)

        items = fetch_rss_feed(fresh_agency)
        assert len(items) == 1
        published_at = items[0]["published_at"]
        # ISO format starts with the expected date.
        assert published_at.startswith("2026-04-02T09:00:00")
        # KST offset serialized.
        assert "+09:00" in published_at
