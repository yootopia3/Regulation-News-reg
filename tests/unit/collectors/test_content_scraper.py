from types import SimpleNamespace

from src.collectors import content_scraper


def test_fetch_content_appends_attachment_links(monkeypatch):
    html = (
        "<html><body>"
        "<div class='view'>본문 내용입니다. 은행권 규제 변경 관련 상세 설명입니다.</div>"
        "<a class='file' href='/files/report.pdf'>첨부 PDF</a>"
        "</body></html>"
    )

    monkeypatch.setattr(content_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        content_scraper.http,
        "fetch",
        lambda *args, **kwargs: SimpleNamespace(content=html.encode("utf-8")),
    )

    content = content_scraper.fetch_content(
        "https://m.kfb.or.kr/news/view.php?idx=1",
        {
            "code": "KFB",
            "selector": {
                "content": ".view",
                "attachment_links": "a.file",
            },
        },
    )

    assert "본문 내용입니다." in content
    assert "Attachments:" in content
    assert "첨부 PDF: https://m.kfb.or.kr/files/report.pdf" in content
