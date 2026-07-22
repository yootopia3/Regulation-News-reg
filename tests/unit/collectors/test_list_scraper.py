from types import SimpleNamespace

from src.collectors import list_scraper


def _response(content: str):
    return SimpleNamespace(content=content.encode("utf-8"))


def _agency(code="BOK"):
    return {
        "code": code,
        "category": "press_release",
        "collection_method": "scraper",
        "url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
        "selector": {
            "list": "li.bbsRowCls",
            "title": "a.title",
            "date": "span.date",
        },
    }


def test_bok_recruitment_and_bid_notices_are_excluded(monkeypatch):
    html = """
    <ul>
      <li class="bbsRowCls">
        <a class="title" href="/portal/bbs/view.do?nttId=1">한국은행 신입직원 채용 공고</a>
      </li>
      <li class="bbsRowCls">
        <a class="title" href="/portal/bbs/view.do?nttId=2">업무시스템 구축 용역 입찰 공고</a>
      </li>
      <li class="bbsRowCls">
        <a class="title" href="/portal/bbs/view.do?nttId=3">금융안정보고서 발간</a>
      </li>
    </ul>
    """

    monkeypatch.setattr(list_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(list_scraper, "MAX_PAGES", 1)
    monkeypatch.setattr(list_scraper.http, "fetch", lambda *args, **kwargs: _response(html))

    items = list_scraper.fetch_list_items(_agency())

    assert [item["title"] for item in items] == ["금융안정보고서 발간"]
    assert items[0]["agency"] == "BOK"


def test_bok_rp_buy_sell_notices_are_excluded(monkeypatch):
    html = """
    <ul>
      <li class="bbsRowCls">
        <a class="title" href="/portal/bbs/view.do?nttId=1">2026.7.22(수) RP매입 실시 결과</a>
      </li>
      <li class="bbsRowCls">
        <a class="title" href="/portal/bbs/view.do?nttId=2">2026.7.22(수) RP 매각 실시 정보</a>
      </li>
      <li class="bbsRowCls">
        <a class="title" href="/portal/bbs/view.do?nttId=3">통화정책방향 관련 총재 기자간담회 자료</a>
      </li>
    </ul>
    """

    monkeypatch.setattr(list_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(list_scraper, "MAX_PAGES", 1)
    monkeypatch.setattr(list_scraper.http, "fetch", lambda *args, **kwargs: _response(html))

    items = list_scraper.fetch_list_items(_agency())

    assert [item["title"] for item in items] == ["통화정책방향 관련 총재 기자간담회 자료"]


def test_exclude_keywords_do_not_apply_to_other_agencies(monkeypatch):
    html = """
    <table><tbody>
      <tr>
        <td class="title"><a href="/notice/1">입찰 관련 제도 안내</a></td>
      </tr>
    </tbody></table>
    """
    agency = {
        "code": "FSS",
        "category": "press_release",
        "collection_method": "scraper",
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
        "selector": {
            "list": "table tbody tr",
            "title": "td.title a",
            "date": "td:nth-of-type(4)",
        },
    }

    monkeypatch.setattr(list_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(list_scraper.http, "fetch", lambda *args, **kwargs: _response(html))

    items = list_scraper.fetch_list_items(agency)

    assert [item["title"] for item in items] == ["입찰 관련 제도 안내"]
