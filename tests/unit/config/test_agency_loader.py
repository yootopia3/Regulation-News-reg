"""Tests for the runtime-derived agency metadata loader."""

import pytest

from src.config.agency_codes import AgencyCode
from src.config.agency_loader import (
    get_sanction_codes,
    is_sanction_agency,
    load_agencies,
)


@pytest.fixture(autouse=True)
def _clear_loader_caches():
    load_agencies.cache_clear()
    get_sanction_codes.cache_clear()
    yield
    load_agencies.cache_clear()
    get_sanction_codes.cache_clear()


def test_get_sanction_codes_matches_agencies_json():
    assert get_sanction_codes() == frozenset({"FSS_SANCTION", "FSS_MGMT_NOTICE"})


def test_is_sanction_agency_string_true():
    assert is_sanction_agency("FSS_SANCTION") is True


def test_is_sanction_agency_string_false():
    assert is_sanction_agency("FSC") is False


def test_is_sanction_agency_accepts_enum():
    assert is_sanction_agency(AgencyCode.FSS_SANCTION) is True
    assert is_sanction_agency(AgencyCode.FSC) is False


def test_load_agencies_returns_full_list():
    agencies = load_agencies()
    assert len(agencies) == 10
    codes = {a["code"] for a in agencies}
    assert "FSS_SANCTION" in codes
    assert "FSS_MGMT_NOTICE" in codes
    assert "MAFRA" in codes
