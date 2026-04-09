"""Helpers for preserving selected analysis_result keys across overwrites.

Used by admin scripts (re-analysis, backfill) that need to update an
article's analysis_result without losing fields that were inserted by
other producers (e.g. pdf_url from sanction_scraper -> _save_item).
"""
from typing import Dict, Optional, Tuple

PRESERVED_KEYS: Tuple[str, ...] = ("pdf_url",)


def preserve_selected_keys(
    old: Optional[Dict],
    new: Optional[Dict],
) -> Optional[Dict]:
    """Return ``new`` with ``PRESERVED_KEYS`` carried over from ``old``.

    Behavior:
    - If ``old`` is not a dict, ``new`` is returned unchanged.
    - If ``old`` has none of the preserved keys (or empty values), ``new``
      is returned unchanged.
    - If ``new`` is not a dict, a fresh dict is built containing only the
      carried-over keys.
    - If ``new`` already defines a preserved key, the existing value in
      ``new`` wins (we use ``setdefault``-style merge — "latest analysis
      wins for analysis fields, but never silently drops the carry").

    Pure function, no I/O, no logging.
    """
    if not isinstance(old, dict):
        return new
    carry = {k: old[k] for k in PRESERVED_KEYS if old.get(k)}
    if not carry:
        return new
    if not isinstance(new, dict):
        return dict(carry)
    merged = dict(new)
    for k, v in carry.items():
        merged.setdefault(k, v)
    return merged
