"""Exercise real parsers with canned responses; all source I/O is replaced."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from src.collectors import kfb_collector, list_scraper, rss_parser, sanction_scraper
from src.collectors.result import CollectionResult, FailureKind


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr('time.sleep', lambda _: None)
    monkeypatch.setattr('requests.sessions.Session.request',
                        Mock(side_effect=AssertionError('unexpected network call')))


def response(body):
    return SimpleNamespace(content=body.encode('utf-8'), raise_for_status=lambda: None)


def agency(code='FSS'):
    return {'code': code, 'name': code, 'url': 'https://example.test/list',
            'collection_method': 'scraper',
            'selector': {'list': 'table tbody tr', 'title': 'td.title a',
                         'date': 'td.date', 'empty': '.no-results'}}


def rss_agency(code='FSC'):
    return {'code': code, 'name': code, 'url': 'https://example.test/rss',
            'collection_method': 'rss'}


@pytest.mark.parametrize('xml,status', [
    ('<rss version="2.0"><channel><title>Feed</title></channel></rss>', 'empty'),
    ('<feed xmlns="http://www.w3.org/2005/Atom"><title>Feed</title></feed>', 'empty'),
    ('<html><title>Service unavailable</title></html>', 'failed'),
    ('<rss><channel><item>', 'failed'),
    ('<rss version="2.0"><channel><item><title>No link</title></item></channel></rss>', 'failed'),
])
def test_rss_empty_vs_invalid(monkeypatch, xml, status):
    monkeypatch.setattr('requests.get', lambda *a, **k: response(xml))
    result = rss_parser.fetch_rss_feed(rss_agency())
    assert result == []
    assert result.status == status
    assert result.failures == ([FailureKind.PARSE] if status == 'failed' else [])


@pytest.mark.parametrize('error,kind,attempts', [
    (requests.ConnectTimeout(), FailureKind.CONNECTION, 3),
    (requests.ReadTimeout(), FailureKind.CONNECTION, 3),
    (requests.ConnectionError(), FailureKind.CONNECTION, 3),
    (requests.HTTPError('503'), FailureKind.HTTP, 1),
])
def test_rss_failure_retains_category_and_retry_budget(monkeypatch, error, kind, attempts):
    fetch = Mock(side_effect=error)
    monkeypatch.setattr('requests.get', fetch)
    result = rss_parser.fetch_rss_feed(rss_agency())
    assert result == []
    assert result.status == 'failed'
    assert result.failures == [kind]
    assert fetch.call_count == attempts


def test_rss_transient_failure_then_recovery_is_success(monkeypatch):
    fetch = Mock(side_effect=[requests.ConnectTimeout(), response(
        '<rss version="2.0"><channel><item><title>OK</title>'
        '<link>https://example.test/1</link></item></channel></rss>')])
    monkeypatch.setattr('requests.get', fetch)
    result = rss_parser.fetch_rss_feed(rss_agency())
    assert len(result) == 1
    assert result.status == 'success'
    assert result.failures == []


def test_rss_aggregator_keeps_each_source_result_and_skips_html(monkeypatch):
    monkeypatch.setattr(rss_parser, 'load_agencies', lambda: [rss_agency(), rss_agency('MOEF'), agency()])
    failed = CollectionResult(failures=[FailureKind.CONNECTION])
    valid = CollectionResult([{'agency': 'MOEF', 'title': 'OK'}])
    fetch = Mock(side_effect=[failed, valid])
    monkeypatch.setattr(rss_parser, 'fetch_rss_feed', fetch)
    result = rss_parser.collect_all_rss()
    assert len(result) == 1
    assert fetch.call_count == 2
    assert result.sources['FSC'].status == 'failed'
    assert result.sources['MOEF'].status == 'success'


@pytest.mark.parametrize('html,status', [
    ('<div class="no-results">No posts</div>', 'empty'),
    ('<html>Access denied</html>', 'failed'),
    ('<table><tbody><tr><td>Changed structure</td></tr></tbody></table>', 'failed'),
    ('<table><tbody><tr><td class="title"><a href="/1">Old</a></td>'
     '<td class="date">2000-01-01</td></tr></tbody></table>', 'empty'),
    ('<table><tbody><tr><td class="title"><a href="/1">Current</a></td>'
     '</tr></tbody></table>', 'success'),
])
def test_html_normal_empty_vs_structure_failure(monkeypatch, html, status):
    monkeypatch.setattr(list_scraper.http, 'fetch', lambda *a, **k: response(html))
    result = list_scraper.fetch_list_items(agency())
    assert result.status == status


def test_bok_keyword_exclusion_is_normal_empty(monkeypatch):
    html = '<table><tbody><tr><td class="title"><a href="/1">신입직원 채용</a></td></tr></tbody></table>'
    monkeypatch.setattr(list_scraper.http, 'fetch', lambda *a, **k: response(html))
    result = list_scraper.fetch_list_items(agency('BOK'))
    assert result == []
    assert result.status == 'empty'


@pytest.mark.parametrize('tail,kind', [
    (requests.ConnectTimeout(), FailureKind.CONNECTION),
    (requests.HTTPError('503'), FailureKind.HTTP),
    (response('<html>Maintenance</html>'), FailureKind.PARSE),
])
def test_later_page_failure_keeps_items_but_marks_failure(monkeypatch, tail, kind):
    html = '<table><tbody>' + ''.join(
        f'<tr><td class="title"><a href="/{i}">Item {i}</a></td></tr>' for i in range(3)
    ) + '</tbody></table>'
    monkeypatch.setattr(list_scraper.http, 'fetch', Mock(side_effect=[response(html), tail]))
    result = list_scraper.fetch_list_items(agency())
    assert len(result) == 3
    assert result.status == 'failed'
    assert result.failures == [kind]


@pytest.mark.parametrize('error,kind', [
    (requests.ConnectTimeout(), FailureKind.CONNECTION),
    (requests.HTTPError('503'), FailureKind.HTTP),
])
def test_sanction_fetch_failure_is_not_normal_empty(monkeypatch, error, kind):
    monkeypatch.setattr(sanction_scraper.http, 'fetch', Mock(side_effect=error))
    result = sanction_scraper.fetch_sanction_items(agency('FSS_SANCTION'))
    assert result == []
    assert result.failures == [kind]


def test_sanction_filter_exclusion_is_normal_empty(monkeypatch):
    html = '<table><tbody><tr><td>1</td><td>보험회사</td><td>2026-10-05</td></tr></tbody></table>'
    config = agency('FSS_SANCTION')
    config['filter_keywords'] = ['은행']
    monkeypatch.setattr(sanction_scraper.http, 'fetch', lambda *a, **k: response(html))
    result = sanction_scraper.fetch_sanction_items(config)
    assert result == []
    assert result.status == 'empty'


@pytest.mark.parametrize('html,status', [
    ('<div class="no-results">No posts</div>', 'empty'),
    ('<html>Access denied</html>', 'failed'),
])
def test_sanction_zero_rows_requires_empty_evidence(monkeypatch, html, status):
    monkeypatch.setattr(sanction_scraper.http, 'fetch', lambda *a, **k: response(html))
    result = sanction_scraper.fetch_sanction_items(agency('FSS_SANCTION'))
    assert result.status == status


def test_kfb_exhausted_fallback_is_failed(monkeypatch):
    fetch = Mock(side_effect=requests.ConnectTimeout())
    monkeypatch.setattr(kfb_collector.http, 'fetch', fetch)
    result = kfb_collector.collect_kfb_rss_first(agency('KFB'))
    assert result == []
    assert result.failures == [FailureKind.CONNECTION]


def test_kfb_fallback_recovery_is_not_failure(monkeypatch):
    html = ('<table><tbody><tr><td><a href="/view.php?idx=1234">Title</a></td>'
            '<td>2026/10/05</td></tr></tbody></table>')
    config = agency('KFB')
    config['selector']['title'] = 'a'
    # A generous window makes this fixture independent of the wall-clock date.
    config['lookback_days'] = 365000
    monkeypatch.setattr(kfb_collector.http, 'fetch', Mock(side_effect=[
        requests.ConnectTimeout(), response(html),
    ]))
    result = kfb_collector.collect_kfb_rss_first(config)
    assert len(result) == 1
    assert result.status == 'success'


def test_kfb_navigation_only_html_is_parse_failure(monkeypatch):
    monkeypatch.setattr(kfb_collector.http, 'fetch', lambda *a, **k: response(
        '<nav><a href="/home">Home</a></nav>'))
    result = kfb_collector.collect_kfb_rss_first(agency('KFB'))
    assert result == []
    assert result.failures == [FailureKind.PARSE]


def test_kfb_partial_rss_parse_retains_failure():
    xml = (b'<rss version="2.0"><channel>'
           b'<item><title>OK</title><link>https://example.test/1</link></item>'
           b'<item><title>Missing link</title></item></channel></rss>')
    result = kfb_collector._parse_feed_items(xml)
    assert len(result) == 1
    assert result.failures == [FailureKind.PARSE]
    assert result.status == 'failed'


@pytest.mark.parametrize('date', ['2000/01/01', '2999/01/01'])
def test_kfb_bad_row_not_hidden_by_valid_or_old_row(date):
    config = agency('KFB')
    config['selector']['title'] = 'a'
    html = ('<table><tbody><tr><td><a href="/view.php?idx=1234">Title</a></td>'
            f'<td>{date}</td></tr><tr><td>Broken row</td></tr></tbody></table>')
    result = kfb_collector._parse_html_items(config['url'], html.encode(), config)
    assert len(result) == (0 if date.startswith('2000') else 1)
    assert result.failures == [FailureKind.PARSE]
    assert result.status == 'failed'
