"""Runtime-derived agency metadata loader.

Round 2 refactor: ``SANCTION_AGENCY_CODES`` used to be a hardcoded frozenset
in ``src/config/agency_codes.py``. It is now derived from ``agencies.json``
at load time so that adding a new sanction agency only requires editing
the JSON, not Python source.

Import has no side effects beyond caching. The JSON file is read lazily
on first call.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, FrozenSet, List

from src.config.settings import AGENCIES_JSON_PATH


@lru_cache(maxsize=1)
def load_agencies() -> List[Dict]:
    with open(AGENCIES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("agencies", []))


@lru_cache(maxsize=1)
def get_sanction_codes() -> FrozenSet[str]:
    """Return the set of agency codes whose category is ``sanction_notice``."""
    return frozenset(
        a["code"]
        for a in load_agencies()
        if a.get("category") == "sanction_notice" and a.get("code")
    )


def is_sanction_agency(code) -> bool:
    """Whether the given agency code represents a sanction-notice source.

    Accepts ``str`` and ``AgencyCode`` (which subclasses ``str``).
    """
    return str(code) in get_sanction_codes()


def get_ssl_verify(code) -> bool:
    """Return the effective TLS-verify flag for the given agency code.

    Per-agency opt-out is expressed as ``"ssl_verify": false`` in
    ``config/agencies.json``. When the field is absent (or the code is
    unknown) we fall back to the module-level default
    ``src.config.settings.SSL_VERIFY``. Deliberately uncached so that a
    runtime override of ``settings.SSL_VERIFY`` (e.g. from tests) is
    observed on the next call.
    """
    from src.config import settings

    if code is None:
        return settings.SSL_VERIFY
    code_str = str(code)
    for agency in load_agencies():
        if agency.get("code") == code_str:
            if "ssl_verify" in agency:
                return bool(agency["ssl_verify"])
            break
    return settings.SSL_VERIFY
