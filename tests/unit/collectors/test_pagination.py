"""Snapshot tests for `src.collectors.pagination.build_page_url`."""

from src.collectors.pagination import build_page_url


class TestBuildPageUrl:
    def test_fsc_uses_curpage_param(self):
        url = build_page_url("https://www.fsc.go.kr/no010101", 1)
        assert url == "https://www.fsc.go.kr/no010101?curPage=1"

    def test_fsc_replaces_existing_curpage(self):
        url = build_page_url("https://www.fsc.go.kr/no010101?curPage=1&foo=bar", 5)
        assert "curPage=5" in url
        assert "curPage=1" not in url
        assert "foo=bar" in url

    def test_non_fsc_uses_pageindex(self):
        url = build_page_url("https://www.fss.or.kr/list.do", 1)
        assert url == "https://www.fss.or.kr/list.do?pageIndex=1"

    def test_non_fsc_appends_with_existing_query(self):
        url = build_page_url("https://www.fss.or.kr/list.do?cat=a", 3)
        assert url == "https://www.fss.or.kr/list.do?cat=a&pageIndex=3"

    def test_non_fsc_replaces_existing_pageindex(self):
        url = build_page_url("https://www.fss.or.kr/list.do?pageIndex=1&foo=bar", 7)
        assert "pageIndex=7" in url
        assert "pageIndex=1" not in url
        assert "foo=bar" in url
