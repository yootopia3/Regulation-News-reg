import logging
from types import SimpleNamespace

from src.collectors import kfb_collector


def _response(content: str):
    return SimpleNamespace(content=content.encode("utf-8"))


def test_kfb_uses_discovered_rss_feed(monkeypatch, caplog):
    page_html = (
        '<html><head><link rel="alternate" type="application/rss+xml" '
        'href="/rss/news.xml"></head><body></body></html>'
    )
    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        '<item><title>은행권 보도자료</title>'
        '<link>https://m.kfb.or.kr/news/view.php?idx=1</link>'
        '<pubDate>Tue, 09 Jun 2026 09:30:00 +0900</pubDate>'
        '<description><![CDATA[요약]]></description></item>'
        '</channel></rss>'
    )

    calls = []

    def fake_fetch(url, **kwargs):
        calls.append(url)
        if url == "https://m.kfb.or.kr/news/info_news.php":
            return _response(page_html)
        if url == "https://m.kfb.or.kr/rss/news.xml":
            return _response(rss_xml)
        raise AssertionError(url)

    monkeypatch.setattr(kfb_collector.http, "fetch", fake_fetch)

    caplog.set_level(logging.INFO, logger="src.collectors.kfb_collector")
    items = kfb_collector.collect_kfb_rss_first(
        {"code": "KFB", "url": "https://m.kfb.or.kr/news/info_news.php"}
    )

    assert calls == [
        "https://m.kfb.or.kr/news/info_news.php",
        "https://m.kfb.or.kr/rss/news.xml",
    ]
    assert len(items) == 1
    assert items[0]["agency"] == "KFB"
    assert items[0]["source_org"] == "KFB"
    assert items[0]["source_name"] == "은행연합회"
    assert items[0]["category"] == "press_release"
    assert items[0]["subcategory"] == "bank_association_press"
    assert items[0]["dedup_key"] == "KFB:https://m.kfb.or.kr/news/view.php?idx=1"
    assert items[0]["collection_source"] == "rss"
    assert "KFB RSS URL discovered: https://m.kfb.or.kr/rss/news.xml" in caplog.text
    assert "KFB collection method: rss" in caplog.text


def test_kfb_falls_back_to_html_when_rss_missing(monkeypatch, caplog):
    page_html = (
        "<html><body><table><tbody><tr>"
        '<td><a href="/news/view.php?idx=2">HTML 보도자료</a></td>'
        "<td>2026-06-09</td>"
        "</tr></tbody></table></body></html>"
    )

    def fake_fetch(url, **kwargs):
        assert url == "https://m.kfb.or.kr/news/info_news.php"
        return _response(page_html)

    monkeypatch.setattr(kfb_collector.http, "fetch", fake_fetch)

    caplog.set_level(logging.INFO, logger="src.collectors.kfb_collector")
    items = kfb_collector.collect_kfb_rss_first(
        {
            "code": "KFB",
            "url": "https://m.kfb.or.kr/news/info_news.php",
            "selector": {
                "list": "table tbody tr",
                "title": "a",
                "date": "td:nth-of-type(2)",
            },
        }
    )

    assert len(items) == 1
    assert items[0]["title"] == "HTML 보도자료"
    assert items[0]["link"] == "https://m.kfb.or.kr/news/view.php?idx=2"
    assert items[0]["collection_source"] == "html"
    assert "KFB RSS not found, fallback to HTML crawling" in caplog.text
    assert "KFB collection method: html" in caplog.text
