"""Unit tests for ``Pipeline._save_item`` pdf_url merge logic.

Scope is intentionally narrow: only ``_save_item`` is exercised. We bypass
``Pipeline.__init__`` using ``Pipeline.__new__`` following the existing
convention in ``tests/unit/pipeline/test_is_duplicate.py``.

Note: this phase predates DI (phase 6). Proper dependency injection of the
Supabase client into ``Pipeline`` is not yet available, so tests use the
``__new__`` hack to construct a bare instance and inject a fake supabase
client manually.
"""

from unittest.mock import MagicMock

import pytest

from src.config.agency_codes import AgencyCode
from src.pipeline import Pipeline


class _FakeSupabase:
    """Minimal Supabase stand-in that captures the dict passed to ``insert``."""

    def __init__(self):
        self.inserted = None
        self._table = MagicMock()
        self._table.insert.side_effect = self._capture_insert

    def table(self, name):
        assert name == "articles"
        return self._table

    def _capture_insert(self, payload):
        self.inserted = payload
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        return chain


@pytest.fixture
def pipeline_with_fake_db():
    """Bare ``Pipeline`` instance with a fake supabase wired in.

    ``Pipeline.__init__`` is intentionally bypassed via ``__new__`` — see
    module docstring for rationale.
    """
    pipe = Pipeline.__new__(Pipeline)
    pipe.supabase = _FakeSupabase()
    pipe.notifier = None
    pipe.analyzer = None
    pipe.scraper = None
    pipe.agency_map = {}
    return pipe


def _captured_payload(pipe):
    return pipe.supabase.inserted


def test_pdf_url_merged_into_existing_analysis_result(pipeline_with_fake_db):
    pipe = pipeline_with_fake_db
    item = {
        'agency': AgencyCode.FSS_SANCTION,
        'title': 't',
        'link': 'https://fss.or.kr/...',
        'pdf_url': 'https://fss.or.kr/x.pdf',
        'analysis_result': {'risk_level': 'HIGH', 'risk_score': 70},
    }

    pipe._save_item(item)

    payload = _captured_payload(pipe)
    assert payload is not None
    assert payload['analysis_result']['pdf_url'] == 'https://fss.or.kr/x.pdf'
    assert payload['analysis_result']['risk_level'] == 'HIGH'
    assert payload['analysis_result']['risk_score'] == 70


def test_pdf_url_with_none_analysis_result_creates_new_dict(pipeline_with_fake_db):
    pipe = pipeline_with_fake_db
    item = {
        'agency': AgencyCode.FSS_SANCTION,
        'title': 't',
        'link': 'https://fss.or.kr/...',
        'pdf_url': 'https://fss.or.kr/x.pdf',
        'analysis_result': None,
    }

    pipe._save_item(item)

    payload = _captured_payload(pipe)
    assert payload['analysis_result'] == {'pdf_url': 'https://fss.or.kr/x.pdf'}


def test_no_pdf_url_leaves_analysis_result_unchanged(pipeline_with_fake_db):
    pipe = pipeline_with_fake_db
    item = {
        'agency': AgencyCode.FSC,
        'title': 't',
        'link': 'https://fsc.go.kr/news/1',
        'analysis_result': {'risk_level': 'LOW'},
    }

    pipe._save_item(item)

    payload = _captured_payload(pipe)
    assert payload['analysis_result'] == {'risk_level': 'LOW'}
    assert 'pdf_url' not in payload['analysis_result']


def test_no_pdf_url_and_none_analysis_result_stays_none(pipeline_with_fake_db):
    pipe = pipeline_with_fake_db
    item = {
        'agency': AgencyCode.FSC,
        'title': 't',
        'link': 'https://fsc.go.kr/news/2',
        'analysis_result': None,
    }

    pipe._save_item(item)

    payload = _captured_payload(pipe)
    assert payload['analysis_result'] is None


def test_original_analysis_result_not_mutated(pipeline_with_fake_db):
    pipe = pipeline_with_fake_db
    original_ar = {'risk_level': 'HIGH', 'risk_score': 70}
    item = {
        'agency': AgencyCode.FSS_SANCTION,
        'title': 't',
        'link': 'https://fss.or.kr/...',
        'pdf_url': 'https://fss.or.kr/x.pdf',
        'analysis_result': original_ar,
    }

    pipe._save_item(item)

    # Original dict must not have been mutated — _notify_item and other
    # consumers may rely on the pre-merge shape.
    assert 'pdf_url' not in original_ar
    assert item['analysis_result'] is original_ar
    assert 'pdf_url' not in item['analysis_result']
