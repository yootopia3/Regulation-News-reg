"""Unit tests for ``Pipeline._is_duplicate``.

Scope is intentionally narrow: only the single ``_is_duplicate`` method is
exercised. ``Pipeline.run()`` and other orchestrator-level paths are out of
scope (Round 2 decision #6).
"""

import pytest

from src.config.agency_codes import AgencyCode
from src.config.agency_loader import get_sanction_codes
from src.pipeline import Pipeline


@pytest.fixture
def pipeline():
    """Construct a Pipeline without running ``__init__``.

    ``_is_duplicate`` only reads ``self`` for method dispatch, so we can
    bypass the heavy initialization (Supabase, scraper, analyzer, notifier)
    entirely via ``__new__``.
    """
    return Pipeline.__new__(Pipeline)


@pytest.fixture(autouse=True)
def _clear_loader_caches():
    get_sanction_codes.cache_clear()
    yield
    get_sanction_codes.cache_clear()


def _sanction_link(exam_id="E1", seq="S1"):
    return (
        "https://www.fss.or.kr/fss/job/openInfo/view.do"
        f"?menuNo=200476&examMgmtNo={exam_id}&emOpenSeq={seq}"
    )


def test_sanction_item_matched_by_key_returns_true(pipeline):
    link = _sanction_link("E42", "S7")
    item = {"agency": AgencyCode.FSS_SANCTION, "link": link}
    sanction_keys = {("FSS_SANCTION", "E42", "S7")}
    assert pipeline._is_duplicate(item, existing_links=set(), sanction_keys=sanction_keys) is True


def test_sanction_item_not_in_keys_returns_false(pipeline):
    link = _sanction_link("E1", "S1")
    item = {"agency": AgencyCode.FSS_SANCTION, "link": link}
    assert (
        pipeline._is_duplicate(item, existing_links=set(), sanction_keys=set()) is False
    )


def test_sanction_item_without_key_falls_back_to_links(pipeline):
    # PDF link with no examMgmtNo / emOpenSeq query params.
    pdf_link = "https://www.fss.or.kr/download/some.pdf"
    item = {"agency": AgencyCode.FSS_MGMT_NOTICE, "link": pdf_link}
    # Fallback hit
    assert pipeline._is_duplicate(item, existing_links={pdf_link}, sanction_keys=set()) is True
    # Fallback miss
    assert pipeline._is_duplicate(item, existing_links=set(), sanction_keys=set()) is False


def test_non_sanction_item_uses_existing_links_only(pipeline):
    link = "https://www.fsc.go.kr/news/12345"
    item = {"agency": AgencyCode.FSC, "link": link}
    assert pipeline._is_duplicate(item, existing_links={link}, sanction_keys=set()) is True
    assert pipeline._is_duplicate(item, existing_links=set(), sanction_keys=set()) is False
