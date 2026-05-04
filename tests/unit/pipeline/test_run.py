"""End-to-end unit tests for ``Pipeline.run()`` using phase 6 DI.

All tests use local fakes — no real network, Supabase, or Gemini calls.
The fakes are defined inline (not extracted to a module) per phase 7 spec:
one test file fully self-contained.
"""

from types import SimpleNamespace
from typing import Dict, List, Optional, Set

import pytest

from src.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


class FakeAnalyzer:
    """Stand-in for ``HybridAnalyzer``.

    ``process`` returns the pre-seeded ``return_value`` (``dict`` or ``None``)
    and increments a call counter. Arguments are captured for assertions.
    """

    def __init__(self, return_value: Optional[Dict] = None):
        self.return_value = return_value
        self.calls: List[Dict] = []

    def process(self, article, agency_name, category):
        self.calls.append(
            {"article": article, "agency_name": agency_name, "category": category}
        )
        return self.return_value


class FakeNotifier:
    """Stand-in for ``TelegramNotifier``.

    ``format_and_send`` simply records its arguments. ``enabled`` exists to
    mirror the real notifier's attribute surface even though ``_notify_item``
    does not currently consult it.
    """

    enabled = True

    def __init__(self):
        self.sent: List[Dict] = []

    def format_and_send(self, a_name, title, link, analysis_result):
        self.sent.append(
            {
                "a_name": a_name,
                "title": title,
                "link": link,
                "analysis_result": analysis_result,
            }
        )


class FakeScraper:
    """Stand-in for ``ContentScraper``.

    Sanction and listing items are keyed by agency code so that each agency
    only yields its own data — feeding everyone the same rows would cause
    cross-agency duplicate collapse in ``_process_single_item``.
    """

    def __init__(
        self,
        list_items_by_agency: Optional[Dict[str, List[Dict]]] = None,
        sanction_items_by_agency: Optional[Dict[str, List[Dict]]] = None,
        content_by_link: Optional[Dict[str, str]] = None,
    ):
        self.list_items_by_agency = list_items_by_agency or {}
        self.sanction_items_by_agency = sanction_items_by_agency or {}
        self.content_by_link = content_by_link or {}

    def fetch_list_items(self, agency, last_crawled_date=None):
        code = agency.get("code") or agency.get("id")
        return list(self.list_items_by_agency.get(code, []))

    def fetch_content(self, link, agency_config):
        return self.content_by_link.get(link, "")

    def fetch_sanction_items(self, agency):
        code = agency.get("code")
        return list(self.sanction_items_by_agency.get(code, []))


class _Chain:
    """Minimal Supabase query chain.

    Only the paths actually exercised by ``Pipeline.run()`` are modelled:

      * ``select('link').range(...)``                         — existing links
      * ``select('link').eq('agency', X).range(...)``         — sanction keys
      * ``select('published_at').eq('agency', X).order(...).limit(1)`` — last crawled
      * ``insert(payload)``                                   — save_item
    """

    def __init__(self, db: "FakeSupabase"):
        self._db = db
        self._cols: Optional[str] = None
        self._eq: Dict[str, str] = {}
        self._order = None
        self._limit = None
        self._range = None

    def select(self, cols):
        self._cols = cols
        return self

    def eq(self, col, val):
        self._eq[col] = str(val)
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        # Paginated ``_load_existing_links``: single call returns everything,
        # loop in production code breaks on ``len(batch) < page_size``.
        if self._cols == "link" and "agency" not in self._eq:
            if self._range and self._range[0] > 0:
                return SimpleNamespace(data=[])
            return SimpleNamespace(
                data=[{"link": l} for l in self._db.existing_links]
            )

        # ``_load_sanction_keys`` — per-agency paginated query.
        if self._cols == "link" and "agency" in self._eq:
            if self._range and self._range[0] > 0:
                return SimpleNamespace(data=[])
            agency = self._eq["agency"]
            return SimpleNamespace(
                data=[
                    {"link": l}
                    for l in self._db.sanction_links_by_agency.get(agency, [])
                ]
            )

        # ``_load_last_crawled`` — single most-recent row per agency.
        if self._cols == "published_at" and "agency" in self._eq and self._limit:
            agency = self._eq["agency"]
            last = self._db.last_crawled_by_agency.get(agency)
            return SimpleNamespace(
                data=[{"published_at": last}] if last else []
            )

        return SimpleNamespace(data=[])


class _InsertChain:
    def __init__(self, db: "FakeSupabase", payload: Dict):
        self._db = db
        self._payload = payload

    def execute(self):
        self._db.inserted.append(self._payload)
        return SimpleNamespace(data=[self._payload])


class _Table:
    def __init__(self, db: "FakeSupabase", name: str):
        self._db = db
        self._name = name

    def select(self, cols):
        return _Chain(self._db).select(cols)

    def insert(self, payload):
        return _InsertChain(self._db, payload)


class FakeSupabase:
    """Ultra-thin Supabase client stand-in.

    State knobs (populate before running ``Pipeline``):

      * ``existing_links``         — global article links set
      * ``sanction_links_by_agency`` — seed sanction identity rows
      * ``last_crawled_by_agency`` — seed per-agency cursor
    """

    def __init__(self):
        self.existing_links: Set[str] = set()
        self.sanction_links_by_agency: Dict[str, List[str]] = {}
        self.last_crawled_by_agency: Dict[str, str] = {}
        self.inserted: List[Dict] = []

    def table(self, name):
        return _Table(self, name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(
    monkeypatch,
    *,
    analyzer,
    notifier,
    db,
    scraper,
    rss_items: Optional[List[Dict]] = None,
):
    """Construct a ``Pipeline`` with all externals stubbed out."""
    monkeypatch.setattr(
        "src.pipeline.collect_all_rss", lambda: list(rss_items or [])
    )
    return Pipeline(
        "config/agencies.json",
        analyzer=analyzer,
        notifier=notifier,
        db=db,
        scraper=scraper,
    )


def _rss_item(agency="MOEF", link="https://korea.kr/news/1"):
    return {
        "agency": agency,
        "title": "t1",
        "link": link,
        "published_at": "2026-04-08T00:00:00+0900",
        "source_published_at_str": "2026-04-08",
        "description": "desc",
    }


def _sanction_link(exam="A", seq="1"):
    return (
        "https://www.fss.or.kr/fss/job/openInfo/view.do"
        f"?menuNo=200476&examMgmtNo={exam}&emOpenSeq={seq}"
    )


def _sanction_item(exam="A", seq="1"):
    return {
        "title": "t",
        "link": _sanction_link(exam, seq),
        "published_at": "2026-04-08T00:00:00+0900",
        "agency": "FSS_SANCTION",
        "category": "sanction_notice",
        "pdf_url": "https://fss.or.kr/x.pdf",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_t1_single_new_rss_item_is_inserted_and_notified(monkeypatch):
    analyzer = FakeAnalyzer(
        return_value={
            "risk_level": "LOW",
            "risk_score": 10,
            "analysis_status": "ANALYZED",
        }
    )
    notifier = FakeNotifier()
    db = FakeSupabase()
    scraper = FakeScraper()

    pipe = _make_pipeline(
        monkeypatch,
        analyzer=analyzer,
        notifier=notifier,
        db=db,
        scraper=scraper,
        rss_items=[_rss_item()],
    )
    pipe.run()

    assert len(db.inserted) == 1
    assert db.inserted[0]["link"] == "https://korea.kr/news/1"
    assert len(analyzer.calls) == 1
    assert len(notifier.sent) == 1


def test_t2_duplicate_rss_item_is_skipped(monkeypatch):
    link = "https://korea.kr/news/1"
    analyzer = FakeAnalyzer(
        return_value={
            "risk_level": "LOW",
            "risk_score": 10,
            "analysis_status": "ANALYZED",
        }
    )
    notifier = FakeNotifier()
    db = FakeSupabase()
    db.existing_links = {link}
    scraper = FakeScraper()

    pipe = _make_pipeline(
        monkeypatch,
        analyzer=analyzer,
        notifier=notifier,
        db=db,
        scraper=scraper,
        rss_items=[_rss_item(link=link)],
    )
    pipe.run()

    assert db.inserted == []
    assert analyzer.calls == []
    assert notifier.sent == []


def test_t3_analyzer_none_saves_but_does_not_notify(monkeypatch):
    analyzer = FakeAnalyzer(return_value=None)
    notifier = FakeNotifier()
    db = FakeSupabase()
    scraper = FakeScraper()

    pipe = _make_pipeline(
        monkeypatch,
        analyzer=analyzer,
        notifier=notifier,
        db=db,
        scraper=scraper,
        rss_items=[_rss_item()],
    )
    pipe.run()

    assert len(db.inserted) == 1
    assert db.inserted[0]["analysis_result"] is None
    assert notifier.sent == []


def test_gemini_disabled_default_pipeline_saves_without_analysis(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "leftover-key")
    monkeypatch.delenv("GEMINI_ENABLED", raising=False)
    monkeypatch.setattr("src.config.settings.load_env", lambda: None)
    monkeypatch.setattr(
        "src.pipeline.collect_all_rss", lambda: [_rss_item()]
    )

    notifier = FakeNotifier()
    db = FakeSupabase()
    scraper = FakeScraper()

    pipe = Pipeline(
        "config/agencies.json",
        notifier=notifier,
        db=db,
        scraper=scraper,
    )
    pipe.run()

    assert pipe.analyzer is None
    assert len(db.inserted) == 1
    assert db.inserted[0]["link"] == "https://korea.kr/news/1"
    assert db.inserted[0]["analysis_result"] is None
    assert notifier.sent == []


def test_t4_sanction_item_preserves_pdf_url_in_analysis_result(monkeypatch):
    analyzer = FakeAnalyzer(
        return_value={
            "risk_level": "HIGH",
            "risk_score": 80,
            "analysis_status": "ANALYZED",
        }
    )
    notifier = FakeNotifier()
    db = FakeSupabase()
    scraper = FakeScraper(
        sanction_items_by_agency={"FSS_SANCTION": [_sanction_item()]}
    )

    pipe = _make_pipeline(
        monkeypatch,
        analyzer=analyzer,
        notifier=notifier,
        db=db,
        scraper=scraper,
    )
    pipe.run()

    assert len(db.inserted) == 1
    result = db.inserted[0]["analysis_result"]
    assert result is not None
    assert result.get("pdf_url") == "https://fss.or.kr/x.pdf"
    assert result.get("risk_level") == "HIGH"


def test_t5_sanction_duplicate_by_identity_key_is_skipped(monkeypatch):
    analyzer = FakeAnalyzer(
        return_value={
            "risk_level": "HIGH",
            "risk_score": 80,
            "analysis_status": "ANALYZED",
        }
    )
    notifier = FakeNotifier()
    db = FakeSupabase()
    # Seed the existing sanction row with the same (examMgmtNo, emOpenSeq).
    db.sanction_links_by_agency = {"FSS_SANCTION": [_sanction_link("A", "1")]}
    scraper = FakeScraper(
        sanction_items_by_agency={"FSS_SANCTION": [_sanction_item("A", "1")]}
    )

    pipe = _make_pipeline(
        monkeypatch,
        analyzer=analyzer,
        notifier=notifier,
        db=db,
        scraper=scraper,
    )
    pipe.run()

    assert db.inserted == []
    assert analyzer.calls == []
    assert notifier.sent == []
