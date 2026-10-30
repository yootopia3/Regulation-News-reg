"""Sanction identity and offline list pagination regression tests."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from src.collectors import sanction_scraper
from src.collectors.result import FailureKind
from src.collectors.sanction_scraper import extract_sanction_key
from src.config.agency_loader import load_agencies


# Reconstructed from the observed FSS terminal page, not archived CI HTML.
EMPTY_ROW = (
    '<tr><td colspan="6" class="no">'
    '자료가 없습니다. 다른 검색조건을 선택해주세요.</td></tr>'
)


def list_page(rows):
    return f'<table class="tbl col list-data"><tbody>{rows}</tbody></table>'


def notice_row(institution, number=1):
    return (
        f'<tr><td>{number}</td><td><span class="only-m">제재대상기관</span>'
        f'{institution}</td><td>2026-10-29</td>'
        f'<td><a href="/fss/job/openInfo/view.do?examMgmtNo={number}&amp;emOpenSeq=1">'
        '상세보기</a></td><td></td><td></td></tr>'
    )


@pytest.fixture
def sanction_config():
    return deepcopy(next(a for a in load_agencies() if a['code'] == 'FSS_SANCTION'))


@pytest.fixture
def mock_pages(monkeypatch):
    monkeypatch.setattr(sanction_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr('requests.sessions.Session.request',
                        Mock(side_effect=AssertionError('unexpected network call')))
    detail = Mock(return_value='https://www.fss.or.kr/hpdownload/test.pdf')
    monkeypatch.setattr(sanction_scraper, 'extract_pdf_from_detail', detail)

    def install(*pages):
        fetch = Mock(side_effect=[
            SimpleNamespace(content=page.encode('utf-8')) for page in pages
        ])
        monkeypatch.setattr(sanction_scraper.http, 'fetch', fetch)
        return fetch, detail

    return install


def test_terminal_empty_first_page(sanction_config, mock_pages):
    fetch, detail = mock_pages(list_page(EMPTY_ROW))
    result = sanction_scraper.fetch_sanction_items(sanction_config)
    assert result == []
    assert result.status == 'empty'
    assert result.failures == []
    assert fetch.call_count == 1
    detail.assert_not_called()


@pytest.mark.parametrize('institution,count', [('보험회사', 0), ('테스트은행', 20)])
def test_two_full_pages_then_empty(sanction_config, mock_pages, institution, count):
    pages = [list_page(''.join(notice_row(institution, i) for i in range(start, start + 10)))
             for start in (1, 11)]
    fetch, detail = mock_pages(*pages, list_page(EMPTY_ROW))
    result = sanction_scraper.fetch_sanction_items(sanction_config)
    assert len(result) == count
    assert result.status == ('success' if count else 'empty')
    assert result.failures == []
    assert [parse_qs(urlparse(call.args[0]).query)['pageIndex']
            for call in fetch.call_args_list] == [['1'], ['2'], ['3']]
    assert detail.call_count == count
    assert len({item['link'] for item in result}) == count


@pytest.mark.parametrize('institution,matched', [
    ('테스트은행', True), ('테스트뱅크', True), ('테스트금융지주', True),
    ('농협', True), ('테스트저축은행', False), ('보험회사', False),
])
def test_notice_filters_and_fields(sanction_config, mock_pages, institution, matched):
    fetch, detail = mock_pages(list_page(notice_row(institution)))
    result = sanction_scraper.fetch_sanction_items(sanction_config)
    assert result.failures == []
    assert result.status == ('success' if matched else 'empty')
    assert len(result) == int(matched)
    assert fetch.call_count == 1
    assert detail.call_count == int(matched)
    if matched:
        assert result[0]['title'] == institution
        assert result[0]['agency'] == 'FSS_SANCTION'
        assert result[0]['category'] == 'sanction_notice'
        assert result[0]['link'] == (
            'https://www.fss.or.kr/fss/job/openInfo/view.do?examMgmtNo=1&emOpenSeq=1'
        )
        assert result[0]['pdf_url'] == detail.return_value
        assert result[0]['published_at_source'] == 'collected_fallback'


@pytest.mark.parametrize('html', [
    '<html>Access denied</html>',
    list_page(''),
    list_page('<tr><td>broken row</td></tr>'),
    list_page(EMPTY_ROW.replace('class="no"', 'class="unexpected"')),
    list_page(EMPTY_ROW.replace('colspan="6"', 'colspan="5"')),
    list_page(EMPTY_ROW).replace('tbl col list-data', 'unrelated'),
    list_page(EMPTY_ROW + '<tr><td>broken row</td></tr>'),
    list_page('<tr><td>1</td><td>테스트은행</td><td>2026-10-29</td></tr>'),
])
def test_malformed_pages_remain_errors(sanction_config, mock_pages, html):
    fetch, _ = mock_pages(html)
    result = sanction_scraper.fetch_sanction_items(sanction_config)
    assert result == []
    assert result.status == 'failed'
    assert result.failures == [FailureKind.PARSE]
    assert fetch.call_count == 1


def test_malformed_later_page_preserves_items_and_failure(sanction_config, mock_pages):
    mock_pages(list_page(notice_row('테스트은행') * 10),
               list_page('<tr><td>broken row</td></tr>'))
    result = sanction_scraper.fetch_sanction_items(sanction_config)
    assert len(result) == 10
    assert result.status == 'failed'
    assert result.failures == [FailureKind.PARSE]


def test_empty_marker_is_source_specific(mock_pages):
    config = deepcopy(next(a for a in load_agencies() if a['code'] == 'FSS_MGMT_NOTICE'))
    mock_pages(list_page(EMPTY_ROW))
    result = sanction_scraper.fetch_sanction_items(config)
    assert result.status == 'failed'
    assert result.failures == [FailureKind.PARSE]


class TestExtractSanctionKey:
    def test_extracts_both_ids_from_full_query(self):
        link = (
            "https://www.fss.or.kr/fss/bbs/B0000188/view.do"
            "?examMgmtNo=2024001&emOpenSeq=42&menuNo=200218"
        )
        assert extract_sanction_key(link) == ("2024001", "42")

    def test_returns_none_pair_when_query_missing(self):
        # PDF download link with no examMgmtNo / emOpenSeq pair.
        link = "https://www.fss.or.kr/fss/cmm/fms/FileDown.do?atchFileId=abc"
        assert extract_sanction_key(link) == (None, None)

    def test_partial_query_returns_partial_pair(self):
        # Only examMgmtNo is present — current code returns the missing
        # field as None rather than failing.
        link = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?examMgmtNo=2024001"
        assert extract_sanction_key(link) == ("2024001", None)

    def test_url_with_no_query_returns_none_pair(self):
        link = "https://www.fss.or.kr/fss/bbs/B0000188/view.do"
        assert extract_sanction_key(link) == (None, None)
