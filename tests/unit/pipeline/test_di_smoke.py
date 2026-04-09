"""Minimal smoke tests for ``Pipeline`` dependency injection.

Phase 6 adds keyword-only DI parameters to ``Pipeline.__init__``. These tests
prove the injection points exist and that default construction still succeeds.
Real fake-based run() tests arrive in phase 7.
"""

from src.pipeline import Pipeline


def test_pipeline_di_injects_dependencies():
    p = Pipeline(
        'config/agencies.json',
        analyzer='MARKER_A',
        notifier='MARKER_N',
        db='MARKER_D',
        scraper='MARKER_S',
    )
    assert p.analyzer == 'MARKER_A'
    assert p.notifier == 'MARKER_N'
    assert p.supabase == 'MARKER_D'
    assert p.scraper == 'MARKER_S'


def test_pipeline_default_init_succeeds():
    # Default construction must not raise. Concrete types are environment-
    # dependent (import of analyzer/notifier/db may fail without .env), so we
    # only assert the attributes exist.
    p = Pipeline('config/agencies.json')
    assert hasattr(p, 'analyzer')
    assert hasattr(p, 'notifier')
    assert hasattr(p, 'supabase')
    assert hasattr(p, 'scraper')
