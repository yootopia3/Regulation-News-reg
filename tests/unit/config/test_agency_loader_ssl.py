"""Tests for `get_ssl_verify` per-agency opt-out resolution."""

import json

import pytest

from src.config import agency_loader, settings


@pytest.fixture
def fixture_agencies(tmp_path, monkeypatch):
    """Point the loader at a disposable agencies.json fixture."""
    data = {
        "agencies": [
            {"code": "OPTOUT", "name": "opt-out agency", "ssl_verify": False},
            {"code": "DEFAULT", "name": "default agency"},
        ]
    }
    path = tmp_path / "agencies.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(agency_loader, "AGENCIES_JSON_PATH", path)
    agency_loader.load_agencies.cache_clear()
    agency_loader.get_sanction_codes.cache_clear()
    yield
    agency_loader.load_agencies.cache_clear()
    agency_loader.get_sanction_codes.cache_clear()


def test_get_ssl_verify_honors_opt_out(fixture_agencies):
    assert agency_loader.get_ssl_verify("OPTOUT") is False


def test_get_ssl_verify_missing_field_falls_back_to_settings(fixture_agencies):
    assert agency_loader.get_ssl_verify("DEFAULT") is settings.SSL_VERIFY


def test_get_ssl_verify_unknown_code_falls_back_to_settings(fixture_agencies):
    assert agency_loader.get_ssl_verify("NOPE") is settings.SSL_VERIFY


def test_get_ssl_verify_none_code_falls_back_to_settings(fixture_agencies):
    assert agency_loader.get_ssl_verify(None) is settings.SSL_VERIFY
