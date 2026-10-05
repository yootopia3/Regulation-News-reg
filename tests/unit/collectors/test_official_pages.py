"""Recorded official HTML regressions. No external requests."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.collectors import content_scraper, list_scraper
from src.collectors.date_parser import KST
from src.collectors.urls import canonical_article_url

CONFIG = {a['code']: a for a in json.loads(Path('config/agencies.json').read_text())['agencies']}
FIXTURES = Path('tests/fixtures/collectors')


@pytest.mark.parametrize('code,fixture,expected', [
    ('FSC', 'fsc_body', '보안점검'),
    ('FSS', 'fss_236976', '금융감독원'),
    ('FSS', 'fss_237413', '보험회사'),
    ('KFB', 'kfb_2012', '금융감독원'),
])
def test_verified_detail_selectors(monkeypatch, code, fixture, expected):
    monkeypatch.setattr(content_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr(content_scraper.http, 'fetch', lambda *a, **k: SimpleNamespace(
        content=(FIXTURES / (fixture + '.html')).read_bytes()))
    body = content_scraper.fetch_content('https://example.test/detail', CONFIG[code])
    assert body and len(body) > 50
    assert expected in body
    assert '조회수' not in body
    assert '이전글' not in body


@pytest.mark.parametrize('code', ['FSC', 'FSS', 'KFB'])
def test_error_page_not_saved_as_body(monkeypatch, code):
    monkeypatch.setattr(content_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr(content_scraper.http, 'fetch', lambda *a, **k: SimpleNamespace(
        content=b'<html><title>Error</title><div class="content">Service unavailable</div></html>'))
    assert content_scraper.fetch_content('https://example.test/detail', CONFIG[code]) is None


def test_title_only_body_is_rejected(monkeypatch):
    monkeypatch.setattr(content_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr(content_scraper.http, 'fetch', lambda *a, **k: SimpleNamespace(
        content=b'<div class="krds-bd-view"><div class="sub-info"><h3 class="subject">Title</h3></div>'
                b'<div class="n-dbdata">Title</div></div>'))
    assert content_scraper.fetch_content('https://example.test/detail', CONFIG['FSS']) is None


class ProbeDate(datetime):
    @classmethod
    def now(cls, tz=None):
        return KST.localize(datetime(2026, 10, 5, 12))


def test_fsc_official_html_replaces_unavailable_rss(monkeypatch):
    monkeypatch.setattr(list_scraper, 'datetime', ProbeDate)
    monkeypatch.setattr(list_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr(list_scraper.http, 'fetch', lambda *a, **k: SimpleNamespace(
        content=(FIXTURES / 'fsc_list.html').read_bytes()))
    result = list_scraper.fetch_list_items(CONFIG['FSC'])
    assert result.status == 'success'
    assert len(result) == 2
    assert result[0]['link'] == 'https://www.fsc.go.kr/no010101/87869'
    assert result[0]['agency'] == 'FSC'


def test_fss_recent_amendments_is_verified_old_data_not_broken_selector(monkeypatch):
    monkeypatch.setattr(list_scraper, 'datetime', ProbeDate)
    monkeypatch.setattr(list_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr(list_scraper.http, 'fetch', lambda *a, **k: SimpleNamespace(
        content=(FIXTURES / 'fss_reg_info.html').read_bytes()))
    result = list_scraper.fetch_list_items(CONFIG['FSS_REG_INFO'])
    assert result == []
    assert result.status == 'empty'
    assert result.failures == []


def test_fsc_rss_and_html_tracking_links_have_same_identity():
    assert canonical_article_url('http://www.fsc.go.kr/no010101/87869?curPage=1&srchCtgry=') == (
        'https://www.fsc.go.kr/no010101/87869')
    unrelated = 'https://www.fss.or.kr/view.do?nttId=237413'
    assert canonical_article_url(unrelated) == unrelated
